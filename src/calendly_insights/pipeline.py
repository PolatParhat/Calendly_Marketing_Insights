"""Run the whole pipeline: landing -> Bronze -> Silver -> Gold.

Every step MERGEs, so running it again (e.g. after a failure) never creates duplicates.

Local:   PYTHONPATH=src python -m calendly_insights.pipeline --landing tests/data/landing --lake lake
AWS:     jobs/run_pipeline.py runs the same code on EMR Serverless with s3:// paths and --cloud.
"""

import argparse

from calendly_insights.bronze import load_bronze
from calendly_insights.gold import load_gold
from calendly_insights.quality import check
from calendly_insights.silver import load_silver
from calendly_insights.spark import get_spark


def run(spark, landing_root: str, lake_root: str) -> None:
    """Load all three layers, then run the data-quality checks.

    lake_root gets bronze/, silver/ and gold/ sub-folders.
    """
    load_bronze(spark, landing_root, f"{lake_root}/bronze")
    load_silver(spark, f"{lake_root}/bronze", f"{lake_root}/silver")
    load_gold(spark, f"{lake_root}/silver", f"{lake_root}/gold")
    check(spark, f"{lake_root}/silver", f"{lake_root}/gold")  # raises if the data looks wrong


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--landing", required=True, help="folder with calendly/ and spend/")
    parser.add_argument("--lake", required=True, help="folder for the bronze/silver/gold tables")
    parser.add_argument("--cloud", action="store_true", help="running on EMR (Spark provided)")
    args = parser.parse_args(argv)

    spark = get_spark("calendly_insights_pipeline", local=not args.cloud)
    run(spark, args.landing, args.lake)
    print(f"Pipeline finished: {args.landing} -> {args.lake}/{{bronze,silver,gold}}")


if __name__ == "__main__":
    main()
