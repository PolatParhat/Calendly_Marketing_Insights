"""Silver tests. Expected numbers come from tests/data/README.md."""

from datetime import date, datetime
from pathlib import Path

import pytest

from calendly_insights.bronze import load_bronze
from calendly_insights.silver import load_silver

LANDING = str(Path(__file__).parent / "data" / "landing")


@pytest.fixture(scope="module")
def silver(spark, tmp_path_factory):
    """Run Bronze then Silver once into a fresh folder; return a table reader."""
    root = tmp_path_factory.mktemp("lake")
    load_bronze(spark, LANDING, f"{root}/bronze")
    load_silver(spark, f"{root}/bronze", f"{root}/silver")
    return lambda name: spark.read.format("delta").load(f"{root}/silver/{name}")


@pytest.fixture(scope="module")
def bookings(silver):
    """silver.bookings as {booking number: row}."""
    rows = silver("bookings").collect()
    return {int(r.booking_id[-1]): r for r in rows}


def test_four_marketing_bookings(bookings):
    # 6 files: the duplicate collapses, the non-marketing booking 6 is dropped
    assert sorted(bookings) == [1, 2, 3, 4]


def test_channel_from_event_type(bookings):
    assert bookings[1].channel == "facebook_paid_ads"
    assert bookings[2].channel == "facebook_paid_ads"
    assert bookings[3].channel == "youtube_paid_ads"
    assert bookings[4].channel == "tiktok_paid_ads"


def test_campaign_unknown_when_null_or_empty(bookings):
    assert bookings[1].campaign == "fall_promo"
    assert bookings[2].campaign == "Unknown"  # null
    assert bookings[3].campaign == "yt_webinar"
    assert bookings[4].campaign == "Unknown"  # ""


def test_booking_date_is_us_eastern(bookings):
    # booking 2 was made 11-03 03:30 UTC = 11-02 22:30 Eastern
    assert bookings[2].booked_at_utc == datetime(2026, 11, 3, 3, 30)
    assert bookings[2].booked_at_et == datetime(2026, 11, 2, 22, 30)
    assert bookings[2].booking_date == date(2026, 11, 2)


def test_meeting_slot_is_us_eastern(bookings):
    slots = {n: (r.meeting_day_of_week, r.meeting_hour_et) for n, r in bookings.items()}
    assert slots == {
        1: ("Wednesday", 10),
        2: ("Thursday", 14),
        3: ("Tuesday", 9),
        4: ("Friday", 16),
    }


def test_phone_from_questions(bookings):
    assert bookings[1].invitee_phone == "+1 555 0101"
    assert bookings[2].invitee_phone is None  # no questions answered


def test_booking_hosts(silver):
    rows = silver("booking_hosts").collect()
    pairs = sorted((int(r.booking_id[-1]), r.host_name) for r in rows)
    assert pairs == [
        (1, "Alice Host"),
        (2, "Bob Host"),
        (3, "Alice Host"),
        (4, "Alice Host"),
        (4, "Bob Host"),
    ]


def test_running_twice_adds_nothing(spark, tmp_path):
    root = str(tmp_path)
    load_bronze(spark, LANDING, f"{root}/bronze")
    load_silver(spark, f"{root}/bronze", f"{root}/silver")
    load_silver(spark, f"{root}/bronze", f"{root}/silver")  # e.g. a re-run after a failure

    assert spark.read.format("delta").load(f"{root}/silver/bookings").count() == 4
    assert spark.read.format("delta").load(f"{root}/silver/booking_hosts").count() == 5
