"""Webhook receiver Lambda: Calendly POSTs every new booking here (through API Gateway).

1. Check the Calendly signature, so only Calendly can add data (else HTTP 401, nothing stored).
2. Save the body unchanged to s3://<lake bucket>/landing/calendly/dt=<today UTC>/<invitee id>.json
3. If that S3 write fails, put the event on the SQS retry queue; the daily workflow replays it.
   If the queue also fails, return HTTP 500 so Calendly knows the delivery did not succeed.

Environment variables (set by CDK): LAKE_BUCKET, RETRY_QUEUE_URL, SIGNING_KEY_SECRET_ARN.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import UTC, datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SIGNATURE_HEADER = "calendly-webhook-signature"  # API Gateway gives header names in lower case
MAX_SIGNATURE_AGE_SECONDS = 180  # Calendly's advice: reject old signatures (replay attacks)

_signing_key_cache: dict[str, str] = {}  # survives between calls while the Lambda stays warm


def verify_signature(header: str | None, body: str, signing_key: str, now: float) -> bool:
    """Calendly header looks like 't=1700000000,v1=<hex>'.

    v1 = HMAC-SHA256(key=signing_key, message=f"{t}.{body}") as hex. Valid only if it matches
    and t is at most MAX_SIGNATURE_AGE_SECONDS old.
    """
    if not header:
        return False
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    timestamp, signature = parts.get("t"), parts.get("v1")
    if not timestamp or not signature or not timestamp.isdigit():
        return False
    if abs(now - int(timestamp)) > MAX_SIGNATURE_AGE_SECONDS:
        return False
    expected = hmac.new(
        signing_key.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)  # constant time: no timing leaks


def landing_key(event: dict, received_at: datetime) -> str:
    """landing/calendly/dt=YYYY-MM-DD/<invitee uuid>.json (dt = day received, UTC).

    The file name is the invitee id, so a duplicate delivery on the same day overwrites the
    same file instead of adding a second one (Silver also de-duplicates on booking_id).
    """
    invitee_uri = (event.get("payload") or {}).get("uri") or ""
    invitee_id = invitee_uri.rstrip("/").rsplit("/", 1)[-1] or f"unknown-{int(time.time() * 1000)}"
    return f"landing/calendly/dt={received_at:%Y-%m-%d}/{invitee_id}.json"


def _response(status: int, message: str) -> dict:
    return {"statusCode": status, "body": json.dumps({"message": message})}


def _signing_key(secrets_client, secret_arn: str) -> str:
    if secret_arn not in _signing_key_cache:
        value = secrets_client.get_secret_value(SecretId=secret_arn)["SecretString"]
        _signing_key_cache[secret_arn] = value.strip()
    return _signing_key_cache[secret_arn]


def handle(event: dict, s3, sqs, secrets, env: dict, now: datetime) -> dict:
    """The real logic, with AWS clients passed in so tests can use fakes."""
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

    key = _signing_key(secrets, env["SIGNING_KEY_SECRET_ARN"])
    if not verify_signature(headers.get(SIGNATURE_HEADER), body, key, now.timestamp()):
        logger.warning("Rejected request: missing or invalid Calendly signature")
        return _response(401, "invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return _response(400, "body is not JSON")
    if payload.get("event") != "invitee.created":
        logger.info("Ignored event %s (only invitee.created is used)", payload.get("event"))
        return _response(200, "ignored")

    s3_key = landing_key(payload, now)
    try:
        s3.put_object(
            Bucket=env["LAKE_BUCKET"],
            Key=s3_key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )  # the bucket encrypts it with the KMS key by default
        logger.info("Saved %s", s3_key)
        return _response(200, "stored")
    except Exception:
        logger.exception("S3 write failed for %s; sending to retry queue", s3_key)

    try:
        sqs.send_message(
            QueueUrl=env["RETRY_QUEUE_URL"],
            MessageBody=json.dumps({"key": s3_key, "body": body}),
        )
        return _response(200, "queued for retry")
    except Exception:
        logger.exception("Retry queue also failed for %s", s3_key)
        return _response(500, "could not store event")


def handler(event, context):  # entry point AWS Lambda calls
    return handle(
        event,
        s3=boto3.client("s3"),
        sqs=boto3.client("sqs"),
        secrets=boto3.client("secretsmanager"),
        env=os.environ,
        now=datetime.now(UTC),
    )
