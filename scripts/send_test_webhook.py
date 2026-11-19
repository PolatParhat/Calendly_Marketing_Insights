"""Send one signed test webhook to the deployed API, the same way Calendly does.

The test booking uses an event type that is NOT one of the 3 marketing channels, so it lands in
landing/ and Bronze but never reaches Silver, Gold or the dashboard.

Usage (values come from the `cdk deploy` outputs):
  python scripts/send_test_webhook.py --url <WebhookUrl> --secret-arn <SigningKeySecretArn>
  python scripts/send_test_webhook.py --url <WebhookUrl> --secret-arn <...> --bad-signature
"""

import argparse
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime


def sign(body: str, signing_key: str, timestamp: int) -> str:
    """Calendly-Webhook-Signature header value: t=<unix time>,v1=<HMAC-SHA256 hex>."""
    digest = hmac.new(signing_key.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256)
    return f"t={timestamp},v1={digest.hexdigest()}"


def test_body() -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    invitee_id = f"test-{uuid.uuid4()}"
    return json.dumps(
        {
            "event": "invitee.created",
            "created_at": now,
            "payload": {
                "uri": f"https://api.calendly.com/scheduled_events/test/invitees/{invitee_id}",
                "created_at": now,
                "name": "Pipeline Test",
                "email": "test@example.com",
                "scheduled_event": {
                    "uri": "https://api.calendly.com/scheduled_events/test",
                    "event_type": "https://api.calendly.com/event_types/pipeline-test-not-marketing",
                    "start_time": now,
                    "end_time": now,
                },
            },
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a signed test webhook")
    parser.add_argument("--url", required=True)
    parser.add_argument("--secret-arn", required=True)
    parser.add_argument("--bad-signature", action="store_true", help="expect HTTP 401")
    args = parser.parse_args()

    import boto3

    key = boto3.client("secretsmanager").get_secret_value(SecretId=args.secret_arn)["SecretString"]
    if args.bad_signature:
        key = "not-the-real-key"
    body = test_body()
    request = urllib.request.Request(
        args.url,
        data=body.encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Calendly-Webhook-Signature": sign(body, key.strip(), int(time.time())),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as error:
        print(error.code, error.read().decode())


if __name__ == "__main__":
    main()
