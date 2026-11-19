"""Data-quality checks: pass on good data, catch broken data."""

from pathlib import Path

import pytest
from pyspark.sql import functions as F

from calendly_insights.pipeline import run
from calendly_insights.quality import DataQualityError, check, find_problems

LANDING = str(Path(__file__).parent / "data" / "landing")


@pytest.fixture(scope="module")
def lake(spark, tmp_path_factory):
    root = str(tmp_path_factory.mktemp("lake"))
    run(spark, LANDING, root)  # run() itself calls check(); it must not raise on good data
    return root


def test_good_data_has_no_problems(spark, lake):
    assert find_problems(spark, f"{lake}/silver", f"{lake}/gold") == []


def test_lost_gold_rows_and_negative_spend_are_caught(spark, lake, tmp_path):
    # Copy the lake, then break it: drop one Gold row and make one spend negative.
    broken = str(tmp_path / "broken")
    for layer, name in [("silver", "bookings"), ("silver", "spend_daily")]:
        spark.read.format("delta").load(f"{lake}/{layer}/{name}").write.format("delta").save(
            f"{broken}/{layer}/{name}"
        )
    spend = spark.read.format("delta").load(f"{broken}/silver/spend_daily")
    spend.withColumn("spend_usd", -F.col("spend_usd")).write.format("delta").mode(
        "overwrite"
    ).save(f"{broken}/silver/spend_daily")
    for name in ["daily_bookings_by_channel", "daily_spend_bookings_by_channel",
                 "weekly_bookings_by_channel", "bookings_by_campaign", "bookings_by_time_slot"]:
        df = spark.read.format("delta").load(f"{lake}/gold/{name}")
        if name == "daily_bookings_by_channel":
            df = df.limit(1)
        df.write.format("delta").save(f"{broken}/gold/{name}")

    problems = find_problems(spark, f"{broken}/silver", f"{broken}/gold")
    assert "silver.spend_daily has a missing or negative spend_usd" in problems
    assert any(p.startswith("gold.daily_bookings_by_channel adds up to") for p in problems)
    with pytest.raises(DataQualityError):
        check(spark, f"{broken}/silver", f"{broken}/gold")
