"""Gold tests: every metric must equal the hand calculation in tests/data/README.md."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pyspark.sql import functions as F

from calendly_insights.pipeline import run

LANDING = str(Path(__file__).parent / "data" / "landing")


@pytest.fixture(scope="module")
def gold(spark, tmp_path_factory):
    """Run the whole pipeline once into a fresh folder; return a Gold table reader."""
    lake = str(tmp_path_factory.mktemp("lake"))
    run(spark, LANDING, lake)
    return lambda name: spark.read.format("delta").load(f"{lake}/gold/{name}")


def test_1_1_daily_bookings_by_channel(gold):
    rows = gold("daily_bookings_by_channel").collect()
    got = sorted((r.booking_date, r.channel, r.bookings, r.cumulative_bookings) for r in rows)
    assert got == [
        (date(2026, 11, 2), "facebook_paid_ads", 2, 2),
        (date(2026, 11, 3), "youtube_paid_ads", 1, 1),
        (date(2026, 11, 4), "tiktok_paid_ads", 1, 1),
    ]


def test_1_2_cpb_by_channel(gold):
    """CPB = total spend / total bookings over the period (the dashboard does this sum)."""
    per_channel = {
        r.channel: (r.spend, r.bookings)
        for r in gold("daily_spend_bookings_by_channel")
        .groupBy("channel")
        .agg(F.sum("spend_usd").alias("spend"), F.sum("bookings").alias("bookings"))
        .collect()
    }
    assert per_channel == {
        "facebook_paid_ads": (Decimal("335.50"), 2),
        "youtube_paid_ads": (Decimal("240.00"), 1),
        "tiktok_paid_ads": (Decimal("150.00"), 1),
    }
    cpb = {ch: spend / n for ch, (spend, n) in per_channel.items()}
    assert cpb == {
        "facebook_paid_ads": Decimal("167.75"),
        "youtube_paid_ads": Decimal(240),
        "tiktok_paid_ads": Decimal(150),
    }
    total_spend = sum(s for s, _ in per_channel.values())
    total_bookings = sum(n for _, n in per_channel.values())
    assert total_spend / total_bookings == Decimal("181.375")


def test_1_2_booking_day_without_spend_is_kept(gold):
    # TikTok booked on 11-04, but no spend file covers 11-04 yet: row kept, spend unknown (null)
    row = gold("daily_spend_bookings_by_channel").where(
        "date = '2026-11-04' AND channel = 'tiktok_paid_ads'"
    )
    assert [(r.spend_usd, r.bookings) for r in row.collect()] == [(None, 1)]
    assert gold("daily_spend_bookings_by_channel").count() == 10  # 9 spend rows + this one


def test_1_3_weekly_bookings(gold):
    rows = gold("weekly_bookings_by_channel").collect()
    got = sorted((r.week_start, r.channel, r.bookings, r.is_partial_week) for r in rows)
    assert got == [
        # sample data covers only Mon 11-02 to Wed 11-04, so the week is partial
        (date(2026, 11, 2), "facebook_paid_ads", 2, True),
        (date(2026, 11, 2), "tiktok_paid_ads", 1, True),
        (date(2026, 11, 2), "youtube_paid_ads", 1, True),
    ]


def test_1_4_bookings_by_campaign(gold):
    rows = gold("bookings_by_campaign").collect()
    got = sorted((r.channel, r.campaign, r.bookings) for r in rows)
    assert got == [
        ("facebook_paid_ads", "Unknown", 1),
        ("facebook_paid_ads", "fall_promo", 1),
        ("tiktok_paid_ads", "Unknown", 1),
        ("youtube_paid_ads", "yt_webinar", 1),
    ]


def test_1_5_bookings_by_time_slot(gold):
    rows = gold("bookings_by_time_slot").collect()
    got = sorted((r.channel, r.meeting_day_of_week, r.meeting_hour_et, r.bookings) for r in rows)
    assert got == [
        ("facebook_paid_ads", "Thursday", 14, 1),
        ("facebook_paid_ads", "Wednesday", 10, 1),
        ("tiktok_paid_ads", "Friday", 16, 1),
        ("youtube_paid_ads", "Tuesday", 9, 1),
    ]


def test_1_6_weekly_meetings_by_host(gold):
    rows = gold("weekly_meetings_by_host").collect()
    got = sorted((r.week_start, r.host_name, r.meetings) for r in rows)
    assert got == [
        (date(2026, 11, 2), "Alice Host", 2),  # bookings 1, 4
        (date(2026, 11, 2), "Bob Host", 2),  # bookings 2, 4
        (date(2026, 11, 9), "Alice Host", 1),  # booking 3
    ]


def test_gold_has_no_pii(gold):
    tables = [
        "daily_bookings_by_channel",
        "daily_spend_bookings_by_channel",
        "weekly_bookings_by_channel",
        "bookings_by_campaign",
        "bookings_by_time_slot",
        "weekly_meetings_by_host",
    ]
    for name in tables:
        cols = set(gold(name).columns)
        assert not cols & {"invitee_name", "invitee_email", "invitee_phone"}, name


def test_pipeline_twice_changes_nothing(spark, tmp_path):
    lake = str(tmp_path)
    run(spark, LANDING, lake)
    run(spark, LANDING, lake)  # e.g. a re-run after a failure
    read = lambda name: spark.read.format("delta").load(f"{lake}/gold/{name}")
    assert read("daily_bookings_by_channel").agg(F.sum("bookings")).first()[0] == 4
    assert read("daily_spend_bookings_by_channel").count() == 10
    assert read("weekly_meetings_by_host").count() == 3


def test_gold_drops_rows_that_disappear_from_silver(spark, tmp_path):
    """delete_missing: if a group vanishes from the new calculation, its old Gold row goes too."""
    from calendly_insights.delta_io import merge_into

    path = str(tmp_path / "t")
    old = spark.createDataFrame([("a", 1), ("b", 2)], "k string, v int")
    new = spark.createDataFrame([("a", 5)], "k string, v int")
    merge_into(spark, old, path, keys=["k"], update_existing=True, delete_missing=True)
    merge_into(spark, new, path, keys=["k"], update_existing=True, delete_missing=True)
    assert [tuple(r) for r in spark.read.format("delta").load(path).collect()] == [("a", 5)]
