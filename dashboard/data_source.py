"""Where the dashboard reads the Gold tables from.

athena (default): SQL through Amazon Athena on the Gold Delta tables in S3 (the real setup).
local:            read a local lake folder with Spark (made by `calendly_insights.pipeline`), for
                  development and demos without AWS.
"""

import sys
import time
from pathlib import Path

import pandas as pd

GOLD_TABLES = [
    "daily_bookings_by_channel",
    "daily_spend_bookings_by_channel",
    "weekly_bookings_by_channel",
    "bookings_by_campaign",
    "bookings_by_time_slot",
    "weekly_meetings_by_host",
]


def _convert(values: list, athena_type: str) -> pd.Series:
    """Athena returns every value as text; turn it back into the right Python type."""
    series = pd.Series(values, dtype="object")
    if athena_type == "date":
        return pd.to_datetime(series).dt.date
    if athena_type in ("integer", "bigint", "smallint", "tinyint"):
        return pd.to_numeric(series).astype("Int64")
    if athena_type in ("decimal", "double", "float", "real"):
        return pd.to_numeric(series)
    if athena_type == "boolean":
        return series.map({"true": True, "false": False})
    return series


def rows_to_frame(pages: list[dict]) -> pd.DataFrame:
    """Turn Athena get_query_results pages into a DataFrame (first row of page 1 = header)."""
    columns = pages[0]["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
    rows = []
    for i, page in enumerate(pages):
        page_rows = page["ResultSet"]["Rows"]
        rows += page_rows[1:] if i == 0 else page_rows
    data = {
        col["Name"]: _convert(
            [r["Data"][j].get("VarCharValue") for r in rows], col["Type"].split("(")[0]
        )
        for j, col in enumerate(columns)
    }
    return pd.DataFrame(data)


def read_athena(table: str, database: str, workgroup: str, region: str | None) -> pd.DataFrame:
    import boto3

    athena = boto3.client("athena", region_name=region)
    query_id = athena.start_query_execution(
        QueryString=f'SELECT * FROM "{database}"."{table}"',
        WorkGroup=workgroup,  # the workgroup sets the encrypted results location
    )["QueryExecutionId"]
    while True:
        state = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        if state["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(0.5)
    if state["State"] != "SUCCEEDED":
        raise RuntimeError(f"Athena query on {table} {state['State']}: {state.get('StateChangeReason')}")
    pages = list(athena.get_paginator("get_query_results").paginate(QueryExecutionId=query_id))
    return rows_to_frame(pages)


def read_local(table: str, lake: str) -> pd.DataFrame:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from calendly_insights.spark import get_spark

    pdf = get_spark("dashboard").read.format("delta").load(f"{lake}/gold/{table}").toPandas()
    for col in pdf.columns:  # Spark decimals arrive as Python Decimal objects
        if pdf[col].dtype == object and col in ("spend_usd",):
            pdf[col] = pd.to_numeric(pdf[col])
    return pdf
