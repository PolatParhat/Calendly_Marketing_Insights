"""Retry-queue replay Lambda: first step of the daily workflow.

Webhook events whose S3 write failed wait in the SQS retry queue as {"key": ..., "body": ...}.
This Lambda writes each one to S3 and only then deletes it from the queue, so nothing is lost:
if the write fails again, the message stays in the queue for the next run.

Environment variables (set by CDK): LAKE_BUCKET, RETRY_QUEUE_URL.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_BATCHES = 100  # 100 x 10 messages per run is far more than this pipeline will ever need


def replay(s3, sqs, bucket: str, queue_url: str) -> dict:
    replayed = 0
    for _ in range(MAX_BATCHES):
        messages = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=1
        ).get("Messages", [])
        if not messages:
            break
        for message in messages:
            item = json.loads(message["Body"])
            s3.put_object(
                Bucket=bucket,
                Key=item["key"],
                Body=item["body"].encode("utf-8"),
                ContentType="application/json",
            )
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
            replayed += 1
            logger.info("Replayed %s", item["key"])
    return {"replayed": replayed}


def handler(event, context):
    return replay(
        boto3.client("s3"),
        boto3.client("sqs"),
        os.environ["LAKE_BUCKET"],
        os.environ["RETRY_QUEUE_URL"],
    )
