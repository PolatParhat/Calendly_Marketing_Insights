"""Landing -> Bronze: load raw landing files into Delta tables, unchanged, plus load metadata.

Bronze keeps everything (also duplicates and non-marketing events), so every later layer can be
rebuilt from it. Each landing file is loaded once: the MERGE key includes the file path.
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from calendly_insights.delta_io import merge_into

SPEND_SCHEMA = "date string, channel string, spend string"  # typed later, in Silver


def read_calendly_landing(spark: SparkSession, landing_path: str) -> DataFrame:
    """One row per webhook file: the whole JSON body as text, plus a few fields pulled out."""
    raw = spark.read.option("recursiveFileLookup", "true").text(
        landing_path, wholetext=True  # one row per file, not one row per line
    )
    return raw.select(
        F.col("_metadata.file_path").alias("source_file"),
        F.get_json_object("value", "$.event").alias("event"),
        F.try_to_timestamp(
            F.get_json_object("value", "$.created_at"),
            F.lit("yyyy-MM-dd'T'HH:mm:ss.SSSSSSX"),
        ).alias("webhook_created_at"),
        F.get_json_object("value", "$.payload.uri").alias("invitee_uri"),
        F.col("value").alias("raw_json"),
        F.current_timestamp().alias("ingested_at"),
    )


def read_spend_landing(spark: SparkSession, landing_path: str) -> DataFrame:
    """One row per (file, date, channel) from the spend JSON files."""
    raw = (
        spark.read.option("recursiveFileLookup", "true")
        .option("multiLine", "true")  # each file is one JSON array spread over many lines
        .schema(SPEND_SCHEMA)
        .json(landing_path)
    )
    return raw.select(
        F.col("_metadata.file_path").alias("source_file"),
        "date",
        "channel",
        "spend",
        F.to_date(
            F.regexp_extract("_metadata.file_name", r"spend_data_(\d{4}-\d{2}-\d{2})\.json", 1)
        ).alias("file_date"),
        F.current_timestamp().alias("ingested_at"),
    )


def load_bronze(spark: SparkSession, landing_root: str, bronze_root: str) -> None:
    """Load both landing folders into their Bronze Delta tables (insert new rows only)."""
    merge_into(
        spark,
        read_calendly_landing(spark, f"{landing_root}/calendly"),
        f"{bronze_root}/calendly_events_raw",
        keys=["source_file"],
        update_existing=False,
    )
    merge_into(
        spark,
        read_spend_landing(spark, f"{landing_root}/spend"),
        f"{bronze_root}/spend_raw",
        keys=["source_file", "date", "channel"],
        update_existing=False,
    )
