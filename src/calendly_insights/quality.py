"""Data-quality checks, run at the end of every pipeline run (docs/02_design/solution_design.md 4.3).

If any check fails, the job raises DataQualityError. On AWS that fails the EMR Serverless job, so
the Step Functions workflow stops and sends the SNS (Simple Notification Service) email alert.
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from calendly_insights.channels import EVENT_TYPE_TO_CHANNEL

CHANNELS = sorted(EVENT_TYPE_TO_CHANNEL.values())

# Gold tables whose "bookings" column must add up to the number of Silver bookings.
GOLD_BOOKING_TABLES = [
    "daily_bookings_by_channel",
    "daily_spend_bookings_by_channel",
    "weekly_bookings_by_channel",
    "bookings_by_campaign",
    "bookings_by_time_slot",
]


class DataQualityError(Exception):
    """Raised when the data breaks one of the rules below."""


def find_problems(spark: SparkSession, silver_root: str, gold_root: str) -> list[str]:
    """Return a list of human-readable problems (empty list = all good)."""

    def read(path: str) -> DataFrame:
        return spark.read.format("delta").load(path)

    problems = []
    bookings = read(f"{silver_root}/bookings")
    spend = read(f"{silver_root}/spend_daily")

    # Required keys present, one row per booking.
    if bookings.where(F.col("booking_id").isNull()).count():
        problems.append("silver.bookings has rows without booking_id")
    if bookings.groupBy("booking_id").count().where("count > 1").count():
        problems.append("silver.bookings has duplicate booking_id values")
    if bookings.where(~F.col("channel").isin(CHANNELS)).count():
        problems.append("silver.bookings has a channel outside the 3 marketing channels")

    # Spend: date and channel present, channel known, amount a number >= 0.
    if spend.where(F.col("spend_date").isNull() | F.col("channel").isNull()).count():
        problems.append("silver.spend_daily has rows without spend_date or channel")
    if spend.where(~F.col("channel").isin(CHANNELS)).count():
        problems.append("silver.spend_daily has an unknown channel")
    if spend.where(F.col("spend_usd").isNull() | (F.col("spend_usd") < 0)).count():
        problems.append("silver.spend_daily has a missing or negative spend_usd")

    # No rows lost between Silver and Gold.
    expected = bookings.count()
    for name in GOLD_BOOKING_TABLES:
        total = read(f"{gold_root}/{name}").agg(F.sum("bookings")).first()[0] or 0
        if total != expected:
            problems.append(f"gold.{name} adds up to {total} bookings, silver has {expected}")
    return problems


def check(spark: SparkSession, silver_root: str, gold_root: str) -> None:
    """Raise DataQualityError listing every problem found."""
    problems = find_problems(spark, silver_root, gold_root)
    if problems:
        raise DataQualityError("Data-quality checks failed:\n- " + "\n- ".join(problems))
    print("Data-quality checks passed")
