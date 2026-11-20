"""Dashboard maths on the real Gold output of the sample data (hand calculation: tests/data/README.md)."""

from datetime import date
from pathlib import Path

import data_source
import metrics
import pandas as pd
import pytest

from calendly_insights.pipeline import run

LANDING = str(Path(__file__).parent / "data" / "landing")


@pytest.fixture(scope="module")
def gold(spark, tmp_path_factory):
    lake = str(tmp_path_factory.mktemp("lake"))
    run(spark, LANDING, lake)
    return {t: data_source.read_local(t, lake) for t in data_source.GOLD_TABLES}


def test_cpb_by_channel_and_overall(gold):
    cpb = metrics.cpb_by_channel(gold["daily_spend_bookings_by_channel"])
    assert dict(zip(cpb["channel"], cpb["cpb_usd"])) == {
        "tiktok_paid_ads": 150.0,
        "facebook_paid_ads": 167.75,
        "youtube_paid_ads": 240.0,
    }
    assert metrics.overall_cpb(gold["daily_spend_bookings_by_channel"]) == 181.375


def test_channel_with_spend_but_no_bookings_shows_none():
    df = pd.DataFrame({"channel": ["x"], "spend_usd": [10.0], "bookings": [0]})
    cpb = metrics.cpb_by_channel(df)
    assert cpb["cpb_usd"].tolist() == [None] and cpb["note"].tolist() == ["no bookings"]
    assert metrics.overall_cpb(df) is None


def test_unknown_spend_is_not_free_spend():
    """Today: bookings exist, spend file comes tomorrow. Must not show $0 spend or $0 CPB."""
    df = pd.DataFrame({"channel": ["x", "y"], "spend_usd": [None, None], "bookings": [2, 1]})
    assert metrics.total_spend(df) is None
    assert metrics.overall_cpb(df) is None
    cpb = metrics.cpb_by_channel(df)
    assert cpb["cpb_usd"].tolist() == [None, None]
    assert set(cpb["note"]) == {"spend not published yet"}


def test_date_filter_and_cumulative(gold):
    days = metrics.filter_days(
        gold["daily_bookings_by_channel"], "booking_date", date(2026, 11, 2), date(2026, 11, 3),
        ["facebook_paid_ads", "youtube_paid_ads"],
    )
    trend = metrics.daily_with_cumulative(days)
    assert trend["bookings"].sum() == 3
    assert trend["cumulative_bookings"].max() == 2


def test_weeks_in_period():
    assert metrics.weeks_in_period(date(2026, 11, 2), date(2026, 11, 8)) == 1  # Mon-Sun
    assert metrics.weeks_in_period(date(2026, 11, 8), date(2026, 11, 9)) == 2  # Sun-Mon


def test_meeting_load_divides_by_weeks_in_period(gold):
    load = metrics.meeting_load(
        gold["weekly_meetings_by_host"], date(2026, 11, 2), date(2026, 11, 15)
    )
    assert set(load["weeks"]) == {2}
    assert (load["avg_meetings_per_week"] == (load["meetings"] / 2).round(2)).all()


def test_leaderboard_sorted_best_first(gold):
    board = metrics.campaign_leaderboard(gold["bookings_by_campaign"])
    assert board["bookings"].is_monotonic_decreasing
    assert board["bookings"].sum() == 4


def test_athena_rows_are_typed():
    page = {
        "ResultSet": {
            "ResultSetMetadata": {
                "ColumnInfo": [
                    {"Name": "date", "Type": "date"},
                    {"Name": "spend_usd", "Type": "decimal"},
                    {"Name": "bookings", "Type": "bigint"},
                    {"Name": "is_partial_week", "Type": "boolean"},
                ]
            },
            "Rows": [
                {"Data": [{"VarCharValue": h} for h in ["date", "spend_usd", "bookings", "is_partial_week"]]},
                {"Data": [{"VarCharValue": "2026-11-02"}, {"VarCharValue": "125.50"},
                          {"VarCharValue": "2"}, {"VarCharValue": "true"}]},
                {"Data": [{"VarCharValue": "2026-11-03"}, {}, {"VarCharValue": "0"},
                          {"VarCharValue": "false"}]},
            ],
        }
    }
    df = data_source.rows_to_frame([page])
    assert df["date"].tolist() == [date(2026, 11, 2), date(2026, 11, 3)]
    assert df["spend_usd"].iloc[0] == 125.5 and pd.isna(df["spend_usd"].iloc[1])
    assert df["bookings"].tolist() == [2, 0]
    assert df["is_partial_week"].tolist() == [True, False]


def test_time_slot_grid_keeps_every_weekday_from_gold(gold):
    """1.5: the weekday names Silver writes must match the dashboard's order, or the grid comes out empty."""
    slots = gold["bookings_by_time_slot"]
    grid = metrics.time_slot_grid(slots)
    assert len(grid) == slots["meeting_day_of_week"].nunique() > 0
    assert int(grid.to_numpy().sum()) == int(slots["bookings"].sum())
    assert list(grid.index) == [d for d in metrics.DAY_ORDER if d in set(grid.index)]
