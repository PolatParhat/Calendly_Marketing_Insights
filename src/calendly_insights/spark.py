"""Start a Spark session with Delta Lake switched on.

Used by the pipeline job and by the tests, so both run Spark the same way.
"""

import os
import platform
import subprocess
import sys

from pyspark.sql import SparkSession

DELTA_CONFIG = {
    # Turn on Delta Lake: SQL commands like MERGE, and Delta as a table format.
    "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
    "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
    # Store and compare all timestamps in UTC; we convert to US Eastern explicitly in the code.
    "spark.sql.session.timeZone": "UTC",
}


def _prepare_local_environment() -> None:
    """Fix the two things that break local Spark on this Mac (see STATUS.md, Environment gotchas)."""
    # 1. Spark's Python helper processes must use this same Python (the venv's 3.11).
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    # 2. Spark 4 needs Java 17. On macOS, always point JAVA_HOME at Java 17 for this process,
    #    even if the shell profile sets another version (this Mac's profile sets Java 11).
    if platform.system() == "Darwin":
        java_home = subprocess.run(
            ["/usr/libexec/java_home", "-v", "17"],
            check=False,  # if Java 17 is missing, carry on; Spark then shows a clear error
            capture_output=True,
            text=True,
        ).stdout.strip()
        if java_home:
            os.environ["JAVA_HOME"] = java_home


def get_spark(app_name: str = "calendly_insights", local: bool = True) -> SparkSession:
    """Return a Spark session with Delta Lake enabled.

    local=True  -> runs on this machine; Delta's Java files are downloaded once by delta-spark.
    local=False -> runs on EMR Serverless, which already provides Spark and Delta.
    """
    builder = SparkSession.builder.appName(app_name)
    for key, value in DELTA_CONFIG.items():
        builder = builder.config(key, value)

    if not local:
        return builder.getOrCreate()

    _prepare_local_environment()
    from delta import configure_spark_with_delta_pip

    builder = (
        builder.master("local[2]")  # use 2 CPU cores on this machine
        .config("spark.sql.shuffle.partitions", "2")  # small data: fewer partitions = faster
        .config("spark.ui.enabled", "false")  # no web UI needed
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark
