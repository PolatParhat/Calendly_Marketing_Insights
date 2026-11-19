import json

import pytest
import retry_replay
from botocore.exceptions import ClientError
from fakes import FakeS3, FakeSQS


def test_replay_writes_each_event_then_empties_queue():
    sqs = FakeSQS()
    for i in range(12):  # more than one batch of 10
        sqs.send_message("q", json.dumps({"key": f"landing/calendly/dt=2026-11-19/{i}.json", "body": "{}"}))
    s3 = FakeS3()
    assert retry_replay.replay(s3, sqs, "lake", "q") == {"replayed": 12}
    assert len(s3.objects) == 12 and sqs.messages == []


def test_failed_write_keeps_message_in_queue():
    sqs = FakeSQS()
    sqs.send_message("q", json.dumps({"key": "k.json", "body": "{}"}))
    with pytest.raises(ClientError):  # the run fails, so Step Functions alerts us
        retry_replay.replay(FakeS3(fail_puts=True), sqs, "lake", "q")
    assert len(sqs.messages) == 1  # still there for the next run
