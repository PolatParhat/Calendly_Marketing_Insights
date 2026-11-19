"""Spend ingestion Lambda: copy every file listed in file_index.json into the landing zone.

Source: https://dea-data-bucket.s3.us-east-1.amazonaws.com/calendly_spend_data/
Target: s3://<lake bucket>/landing/spend/dt=<publish day>/spend_data_<day>.json

Failure reload: the index lists the last ~30 files, and every run copies all files it does not
have yet. A day missed because of an outage is filled in by the next run automatically.
No duplicates: the target key depends only on the file name, and files already copied are skipped.
publish day = file day + 1 (the file for Day-1 is published at 06:00 US Eastern on Day).

Environment variables (set by CDK): LAKE_BUCKET, SPEND_BASE_URL.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import date, timedelta

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DEFAULT_BASE_URL = "https://dea-data-bucket.s3.us-east-1.amazonaws.com/calendly_spend_data"
FILE_NAME = re.compile(r"^spend_data_(\d{4}-\d{2}-\d{2})\.json$")


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def target_key(file_name: str) -> str:
    match = FILE_NAME.match(file_name)
    if not match:
        raise ValueError(f"unexpected spend file name: {file_name}")
    publish_day = date.fromisoformat(match.group(1)) + timedelta(days=1)
    return f"landing/spend/dt={publish_day.isoformat()}/{file_name}"


def already_copied(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def copy_spend_files(s3, bucket: str, base_url: str, fetch=fetch) -> dict:
    index = json.loads(fetch(f"{base_url}/file_index.json"))
    copied, skipped, unavailable = [], [], []
    for file_name in index["files"]:
        key = target_key(file_name)
        if already_copied(s3, bucket, key):
            skipped.append(file_name)
            continue
        try:
            content = fetch(f"{base_url}/{file_name}")
        except urllib.error.HTTPError as error:
            # Files older than ~30 days disappear from the source (HTTP 403); not an error for us.
            logger.warning("Could not download %s: HTTP %s", file_name, error.code)
            unavailable.append(file_name)
            continue
        json.loads(content)  # check it is valid JSON before it reaches the lake
        s3.put_object(Bucket=bucket, Key=key, Body=content, ContentType="application/json")
        copied.append(file_name)
        logger.info("Copied %s -> %s", file_name, key)
    if not copied and not skipped:
        raise RuntimeError("No spend files available: index empty or every download failed")
    return {
        "listed": len(index["files"]),
        "copied": len(copied),
        "skipped_already_copied": len(skipped),
        "unavailable": unavailable,
    }


def handler(event, context):
    return copy_spend_files(
        boto3.client("s3"),
        os.environ["LAKE_BUCKET"],
        os.environ.get("SPEND_BASE_URL", DEFAULT_BASE_URL),
    )
