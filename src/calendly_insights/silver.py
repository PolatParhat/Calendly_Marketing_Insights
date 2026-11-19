"""Bronze -> Silver: turn raw rows into clean, typed, de-duplicated tables.

silver.bookings       one row per marketing booking (3 channels only), duplicates collapsed
silver.booking_hosts  one row per (booking, host), because a meeting can have several hosts
silver.spend_daily    one row per (date, channel): the spend from the newest file that has it

Rules (docs/02_design/data_model.md, SME-confirmed): channel comes from the event type; campaign is
utm_campaign or "Unknown"; timestamps stay in UTC and get US Eastern copies (suffix _et).
"""

from itertools import chain

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from calendly_insights.channels import EVENT_TYPE_TO_CHANNEL
from calendly_insights.delta_io import merge_into

REPORTING_TZ = "America/New_York"  # US Eastern, handles daylight saving automatically
CALENDLY_TS_FORMAT = "yyyy-MM-dd'T'HH:mm:ss.SSSSSSX"  # e.g. 2026-11-02T14:30:00.000000Z

# Only the parts of the webhook body we use. Fields not listed here are ignored by from_json.
PAYLOAD_SCHEMA = """
payload struct<
  uri: string,
  created_at: string,
  name: string,
  email: string,
  status: string,
  timezone: string,
  rescheduled: boolean,
  questions_and_answers: array<struct<question: string, answer: string>>,
  tracking: struct<utm_campaign: string, utm_source: string, utm_medium: string,
                   utm_content: string, utm_term: string>,
  scheduled_event: struct<
    uri: string,
    name: string,
    event_type: string,
    start_time: string,
    end_time: string,
    event_memberships: array<struct<user: string, user_name: string, user_email: string>>
  >
>
"""


def _ts(col: Column) -> Column:
    """Calendly timestamp text -> Spark timestamp (UTC). Bad text becomes null instead of failing."""
    return F.try_to_timestamp(col, F.lit(CALENDLY_TS_FORMAT))


def _channel(event_type_uri: Column) -> Column:
    """Map the event type URI to its channel name; null when it is not one of the 3 marketing types."""
    mapping = F.create_map(*[F.lit(x) for x in chain(*EVENT_TYPE_TO_CHANNEL.items())])
    return mapping[F.trim(event_type_uri)]


def _phone(questions: Column) -> Column:
    """The answer to the first question that mentions 'phone' (null if there is none)."""
    phone_answers = F.filter(questions, lambda q: F.lower(q["question"]).contains("phone"))
    return F.get(phone_answers, 0)["answer"]  # get() returns null for an empty list


def build_bookings(bronze_events: DataFrame) -> DataFrame:
    """Bronze webhook rows -> one row per marketing booking, latest delivery wins."""
    parsed = bronze_events.select(
        "source_file",
        "webhook_created_at",
        F.from_json("raw_json", PAYLOAD_SCHEMA)["payload"].alias("p"),
    )
    p, ev, tr = F.col("p"), F.col("p.scheduled_event"), F.col("p.tracking")

    bookings = parsed.select(
        p["uri"].alias("booking_id"),
        ev["uri"].alias("scheduled_event_id"),
        ev["event_type"].alias("event_type_uri"),
        ev["name"].alias("event_name"),
        _channel(ev["event_type"]).alias("channel"),
        # null or "" (or only spaces) -> "Unknown"
        F.coalesce(F.nullif(F.trim(tr["utm_campaign"]), F.lit("")), F.lit("Unknown")).alias(
            "campaign"
        ),
        tr["utm_source"].alias("utm_source"),
        tr["utm_medium"].alias("utm_medium"),
        tr["utm_content"].alias("utm_content"),
        tr["utm_term"].alias("utm_term"),
        _ts(p["created_at"]).alias("booked_at_utc"),
        _ts(ev["start_time"]).alias("meeting_start_utc"),
        _ts(ev["end_time"]).alias("meeting_end_utc"),
        p["name"].alias("invitee_name"),
        p["email"].alias("invitee_email"),
        _phone(p["questions_and_answers"]).alias("invitee_phone"),
        p["timezone"].alias("invitee_timezone"),
        p["status"].alias("invitee_status"),
        p["rescheduled"].alias("rescheduled"),
        ev["event_memberships"].alias("hosts"),  # used for booking_hosts, dropped from bookings
        "webhook_created_at",
        "source_file",
    ).where(F.col("channel").isNotNull())  # marketing only; other events stay in Bronze

    # Derived US Eastern columns. Session time zone is UTC, so the result shows Eastern wall-clock time.
    bookings = (
        bookings.withColumn("booked_at_et", F.from_utc_timestamp("booked_at_utc", REPORTING_TZ))
        .withColumn("booking_date", F.to_date("booked_at_et"))
        .withColumn("meeting_start_et", F.from_utc_timestamp("meeting_start_utc", REPORTING_TZ))
        .withColumn("meeting_hour_et", F.hour("meeting_start_et"))
        .withColumn("meeting_day_of_week", F.date_format("meeting_start_et", "EEEE"))  # "Monday"
        .withColumn("updated_at", F.current_timestamp())
    )

    # Calendly may deliver the same booking twice: keep the latest delivery per booking_id.
    latest_first = Window.partitionBy("booking_id").orderBy(
        F.col("webhook_created_at").desc(),
        F.col("source_file").desc(),  # file name breaks ties
    )
    return bookings.withColumn("rn", F.row_number().over(latest_first)).where("rn = 1").drop("rn")


def build_booking_hosts(bookings: DataFrame) -> DataFrame:
    """One row per (booking, host) from the hosts list of each booking."""
    return bookings.select(
        "booking_id",
        "meeting_start_et",
        F.explode("hosts").alias("h"),  # explode: one output row per list item
    ).select(
        "booking_id",
        F.col("h.user").alias("host_user_id"),
        F.col("h.user_name").alias("host_name"),
        F.col("h.user_email").alias("host_email"),
        "meeting_start_et",
    )


def build_spend_daily(spend_raw: DataFrame) -> DataFrame:
    """Bronze spend rows -> one row per (date, channel), newest file wins.

    Each spend file holds a rolling 30-day window, so the same (date, channel) is in many files.
    If a newer file restates a value (a late correction), the newer value is the true one.
    """
    newest_first = Window.partitionBy("date", "channel").orderBy(F.col("file_date").desc())
    return (
        spend_raw.withColumn("rn", F.row_number().over(newest_first))
        .where("rn = 1")
        .select(
            F.to_date("date").alias("spend_date"),
            "channel",
            # text -> exact money type (12 digits, 2 after the point); float would round badly
            F.col("spend").cast("decimal(12,2)").alias("spend_usd"),
            "source_file",
            F.current_timestamp().alias("updated_at"),
        )
    )


def load_silver(spark: SparkSession, bronze_root: str, silver_root: str) -> None:
    """Rebuild all Silver tables from Bronze and MERGE them in (re-running changes nothing)."""
    bronze_events = spark.read.format("delta").load(f"{bronze_root}/calendly_events_raw")
    bookings = build_bookings(bronze_events)

    merge_into(
        spark,
        bookings.drop("hosts"),
        f"{silver_root}/bookings",
        keys=["booking_id"],
        update_existing=True,
    )
    merge_into(
        spark,
        build_booking_hosts(bookings),
        f"{silver_root}/booking_hosts",
        keys=["booking_id", "host_user_id"],
        update_existing=True,
    )
    merge_into(
        spark,
        build_spend_daily(spark.read.format("delta").load(f"{bronze_root}/spend_raw")),
        f"{silver_root}/spend_daily",
        keys=["spend_date", "channel"],
        update_existing=True,
    )
