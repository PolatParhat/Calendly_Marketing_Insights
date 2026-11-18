"""Write a DataFrame into a Delta table with MERGE, so re-running never creates duplicates."""

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession


def merge_into(
    spark: SparkSession,
    df: DataFrame,
    path: str,
    keys: list[str],
    update_existing: bool,
) -> None:
    """MERGE df into the Delta table at path, matching rows on the key columns.

    update_existing=False -> only insert rows whose key is new (Bronze: raw data never changes).
    update_existing=True  -> also overwrite rows whose key already exists (Silver/Gold: latest wins).
    The first run creates the table.
    """
    if not DeltaTable.isDeltaTable(spark, path):
        df.write.format("delta").save(path)
        return

    condition = " AND ".join(f"t.{k} <=> s.{k}" for k in keys)  # <=> also matches NULL = NULL
    merge = DeltaTable.forPath(spark, path).alias("t").merge(df.alias("s"), condition)
    if update_existing:
        merge = merge.whenMatchedUpdateAll()
    merge.whenNotMatchedInsertAll().execute()
