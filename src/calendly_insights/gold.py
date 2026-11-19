"""Silver -> Gold: one small table per dashboard metric (docs/02_design/data_model.md).

Gold holds counts and sums per day or week, never ratios. The dashboard adds them up over the period
the user picks, so CPB is always total spend / total bookings, never an average of daily CPBs.
Gold has no PII (Personally Identifiable Information): no invitee names, emails or phones.

Every Gold table is recalculated in full from Silver on each run and MERGEd in with delete_missing,
so the table always mirrors the latest Silver data and re-running changes nothing.
"""

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from calendly_insights.delta_io import merge_into


def _week_start(col: str) -> Column:
    """Monday of the week the date/timestamp falls in (weeks run Monday-Sunday)."""
    return F.to_date(F.date_trunc("week", F.col(col)))


def daily_bookings_by_channel(bookings: DataFrame) -> DataFrame:
    """1.1 + 1.3: bookings per booking day (US Eastern) and channel, with a running total."""
    running = (
        Window.partitionBy("channel")
        .orderBy("booking_date")
        .rowsBetween(Window.unboundedPreceding, Window.currentRow)
    )
    return (
        bookings.groupBy("booking_date", "channel")
        .agg(F.count("*").alias("bookings"))
        .withColumn("cumulative_bookings", F.sum("bookings").over(running))
    )


def daily_spend_bookings_by_channel(bookings: DataFrame, spend_daily: DataFrame) -> DataFrame:
    """1.2: spend and bookings per day and channel, the inputs for CPB (Cost Per Booking).

    Full outer join: a day with spend but no bookings, or bookings but no spend file yet, still
    appears. Missing bookings count as 0; missing spend stays null (not known yet, not "free").
    """
    daily_bookings = bookings.groupBy(F.col("booking_date").alias("date"), "channel").agg(
        F.count("*").alias("bookings")
    )
    spend = spend_daily.select(F.col("spend_date").alias("date"), "channel", "spend_usd")
    return spend.join(daily_bookings, ["date", "channel"], "full_outer").select(
        "date",
        "channel",
        "spend_usd",
        F.coalesce("bookings", F.lit(0)).alias("bookings"),
    )


def weekly_bookings_by_channel(bookings: DataFrame) -> DataFrame:
    """1.3: bookings per week (Monday start) and channel.

    is_partial_week = the week is not fully covered by the data (first or last week of the range),
    so the dashboard can label it instead of showing a fake dip.
    """
    first_day, last_day = bookings.agg(F.min("booking_date"), F.max("booking_date")).first()
    weekly = bookings.groupBy(_week_start("booking_date").alias("week_start"), "channel").agg(
        F.count("*").alias("bookings")
    )
    return weekly.withColumn(
        "is_partial_week",
        (F.col("week_start") < F.lit(first_day)) | (F.date_add("week_start", 6) > F.lit(last_day)),
    )


def bookings_by_campaign(bookings: DataFrame) -> DataFrame:
    """1.4: bookings per day, channel and campaign (UTM, Urchin Tracking Module, tags)."""
    return bookings.groupBy("booking_date", "channel", "campaign", "utm_source", "utm_medium").agg(
        F.count("*").alias("bookings")
    )


def bookings_by_time_slot(bookings: DataFrame) -> DataFrame:
    """1.5: bookings per meeting weekday and hour (US Eastern) and channel."""
    return bookings.groupBy("meeting_day_of_week", "meeting_hour_et", "channel").agg(
        F.count("*").alias("bookings")
    )


def weekly_meetings_by_host(booking_hosts: DataFrame) -> DataFrame:
    """1.6: marketing meetings per host per week of the meeting start (US Eastern)."""
    return booking_hosts.groupBy(
        _week_start("meeting_start_et").alias("week_start"), "host_user_id"
    ).agg(
        F.max("host_name").alias("host_name"),  # one name per host; max() just picks it
        F.countDistinct("booking_id").alias("meetings"),
    )


def load_gold(spark: SparkSession, silver_root: str, gold_root: str) -> None:
    """Recalculate all six Gold tables from Silver and MERGE them in."""

    def read(name: str) -> DataFrame:
        return spark.read.format("delta").load(f"{silver_root}/{name}")

    bookings, hosts, spend = read("bookings"), read("booking_hosts"), read("spend_daily")

    tables = {
        "daily_bookings_by_channel": (
            daily_bookings_by_channel(bookings),
            ["booking_date", "channel"],
        ),
        "daily_spend_bookings_by_channel": (
            daily_spend_bookings_by_channel(bookings, spend),
            ["date", "channel"],
        ),
        "weekly_bookings_by_channel": (
            weekly_bookings_by_channel(bookings),
            ["week_start", "channel"],
        ),
        "bookings_by_campaign": (
            bookings_by_campaign(bookings),
            ["booking_date", "channel", "campaign", "utm_source", "utm_medium"],
        ),
        "bookings_by_time_slot": (
            bookings_by_time_slot(bookings),
            ["meeting_day_of_week", "meeting_hour_et", "channel"],
        ),
        "weekly_meetings_by_host": (
            weekly_meetings_by_host(hosts),
            ["week_start", "host_user_id"],
        ),
    }
    for name, (df, keys) in tables.items():
        merge_into(
            spark,
            df,
            f"{gold_root}/{name}",
            keys=keys,
            update_existing=True,
            delete_missing=True,
        )
