import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest
import webhook
from fakes import FakeS3, FakeSecrets, FakeSQS

KEY = "test-signing-key"
NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)
ENV = {"LAKE_BUCKET": "lake", "RETRY_QUEUE_URL": "q", "SIGNING_KEY_SECRET_ARN": "arn:secret"}
BODY = json.dumps(
    {"event": "invitee.created", "payload": {"uri": "https://api.calendly.com/x/invitees/abc-123"}}
)


def signed_headers(body: str, ts: int | None = None, key: str = KEY) -> dict:
    ts = int(NOW.timestamp()) if ts is None else ts
    sig = hmac.new(key.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    return {"Calendly-Webhook-Signature": f"t={ts},v1={sig}"}


@pytest.fixture(autouse=True)
def clear_key_cache():
    webhook._signing_key_cache.clear()


def call(event, s3=None, sqs=None):
    s3, sqs = s3 or FakeS3(), sqs or FakeSQS()
    result = webhook.handle(event, s3, sqs, FakeSecrets(KEY), ENV, NOW)
    return result, s3, sqs


def test_valid_booking_is_saved_to_landing():
    result, s3, _ = call({"body": BODY, "headers": signed_headers(BODY)})
    assert result["statusCode"] == 200
    assert s3.objects == {
        ("lake", "landing/calendly/dt=2026-11-19/abc-123.json"): BODY.encode()
    }


def test_base64_body_from_api_gateway_is_decoded():
    event = {
        "body": base64.b64encode(BODY.encode()).decode(),
        "isBase64Encoded": True,
        "headers": signed_headers(BODY),
    }
    result, s3, _ = call(event)
    assert result["statusCode"] == 200 and len(s3.objects) == 1


@pytest.mark.parametrize(
    "headers",
    [
        {},  # no signature
        signed_headers(BODY, key="wrong-key"),  # not signed by Calendly
        signed_headers(BODY, ts=int(NOW.timestamp()) - 600),  # 10 minutes old: replay
        {"Calendly-Webhook-Signature": "garbage"},
    ],
)
def test_bad_signature_is_rejected_and_nothing_stored(headers):
    result, s3, sqs = call({"body": BODY, "headers": headers})
    assert result["statusCode"] == 401
    assert s3.objects == {} and sqs.messages == []


def test_other_events_are_ignored():
    body = json.dumps({"event": "invitee.canceled", "payload": {}})
    result, s3, _ = call({"body": body, "headers": signed_headers(body)})
    assert result["statusCode"] == 200 and s3.objects == {}


def test_s3_failure_sends_event_to_retry_queue():
    result, _, sqs = call({"body": BODY, "headers": signed_headers(BODY)}, s3=FakeS3(fail_puts=True))
    assert result["statusCode"] == 200
    message = json.loads(sqs.messages[0]["Body"])
    assert message == {"key": "landing/calendly/dt=2026-11-19/abc-123.json", "body": BODY}


def test_s3_and_queue_failure_returns_500_so_calendly_knows():
    result, _, _ = call(
        {"body": BODY, "headers": signed_headers(BODY)},
        s3=FakeS3(fail_puts=True),
        sqs=FakeSQS(fail=True),
    )
    assert result["statusCode"] == 500


def test_test_script_signature_is_accepted_by_the_lambda():
    import send_test_webhook

    body = send_test_webhook.test_body()
    header = send_test_webhook.sign(body, KEY, int(NOW.timestamp()))
    result, s3, _ = call({"body": body, "headers": {"Calendly-Webhook-Signature": header}})
    assert result["statusCode"] == 200 and len(s3.objects) == 1
