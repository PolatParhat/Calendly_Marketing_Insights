import io
import json
import urllib.error

import pytest
import spend_copy
from fakes import FakeS3

BASE = "https://example.test/calendly_spend_data"
FILES = {
    "file_index.json": json.dumps(
        {"files": ["spend_data_2026-10-01.json", "spend_data_2026-11-17.json", "spend_data_2026-11-18.json"]}
    ),
    "spend_data_2026-11-17.json": json.dumps([{"date": "2026-11-17", "channel": "x", "spend": 1}]),
    "spend_data_2026-11-18.json": json.dumps([{"date": "2026-11-18", "channel": "x", "spend": 2}]),
}


def fake_fetch(url: str) -> bytes:
    name = url.rsplit("/", 1)[-1]
    if name not in FILES:  # old files vanish from the source with HTTP 403
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO())
    return FILES[name].encode()


def test_target_key_uses_publish_day():
    assert spend_copy.target_key("spend_data_2026-11-18.json") == (
        "landing/spend/dt=2026-11-19/spend_data_2026-11-18.json"
    )
    with pytest.raises(ValueError):
        spend_copy.target_key("../evil.json")


def test_copies_all_available_files_and_rerun_adds_nothing():
    s3 = FakeS3()
    first = spend_copy.copy_spend_files(s3, "lake", BASE, fetch=fake_fetch)
    assert first == {
        "listed": 3,
        "copied": 2,
        "skipped_already_copied": 0,
        "unavailable": ["spend_data_2026-10-01.json"],
    }
    assert ("lake", "landing/spend/dt=2026-11-19/spend_data_2026-11-18.json") in s3.objects

    second = spend_copy.copy_spend_files(s3, "lake", BASE, fetch=fake_fetch)
    assert second["copied"] == 0 and second["skipped_already_copied"] == 2
    assert len(s3.objects) == 2  # no duplicates


def test_nothing_available_is_an_error():
    def nothing(url):
        if url.endswith("file_index.json"):
            return json.dumps({"files": ["spend_data_2026-10-01.json"]}).encode()
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO())

    with pytest.raises(RuntimeError):
        spend_copy.copy_spend_files(FakeS3(), "lake", BASE, fetch=nothing)
