"""Shared test setup. pytest loads this file automatically before the tests."""

import os
import time

import pytest

from calendly_insights.spark import get_spark

# collect() turns Spark timestamps into Python datetimes in the *machine's* time zone.
# Use UTC (like the Spark session and EMR) so tests give the same result on any laptop or CI runner.
os.environ["TZ"] = "UTC"
time.tzset()


@pytest.fixture(scope="session")
def spark():
    """One Spark session for the whole test run (starting Spark takes a few seconds)."""
    session = get_spark("calendly_insights_tests")
    yield session
    session.stop()
