"""Bronze tests. Expected numbers come from tests/data/README.md."""

from pathlib import Path

import pytest

from calendly_insights.bronze import load_bronze

LANDING = str(Path(__file__).parent / "data" / "landing")


@pytest.fixture
def bronze(spark, tmp_path):
    """Run the Bronze load once into a fresh temporary folder; return a table reader."""
    root = str(tmp_path / "bronze")
    load_bronze(spark, LANDING, root)
    return lambda name: spark.read.format("delta").load(f"{root}/{name}")


def test_every_webhook_file_is_one_row(bronze):
    # 6 files, including the duplicate delivery and the non-marketing event
    assert bronze("calendly_events_raw").count() == 6


def test_every_spend_row_is_kept(bronze):
    # 6 rows in the first file + 9 in the second (overlaps are resolved in Silver)
    assert bronze("spend_raw").count() == 15


def test_webhook_fields_are_extracted(bronze):
    rows = bronze("calendly_events_raw").collect()
    assert {r.event for r in rows} == {"invitee.created"}
    assert all(r.webhook_created_at is not None for r in rows)
    assert all(r.invitee_uri.startswith("https://api.calendly.com/") for r in rows)
    assert all('"payload"' in r.raw_json for r in rows)


def test_spend_file_date_comes_from_the_file_name(bronze):
    dates = {str(r.file_date) for r in bronze("spend_raw").select("file_date").distinct().collect()}
    assert dates == {"2026-11-02", "2026-11-03"}


def test_running_twice_adds_nothing(spark, tmp_path):
    root = str(tmp_path / "bronze")
    load_bronze(spark, LANDING, root)
    load_bronze(spark, LANDING, root)  # e.g. a re-run after a failure

    assert spark.read.format("delta").load(f"{root}/calendly_events_raw").count() == 6
    assert spark.read.format("delta").load(f"{root}/spend_raw").count() == 15
