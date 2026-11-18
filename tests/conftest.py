"""Shared test setup. pytest loads this file automatically before the tests."""

import pytest

from calendly_insights.spark import get_spark


@pytest.fixture(scope="session")
def spark():
    """One Spark session for the whole test run (starting Spark takes a few seconds)."""
    session = get_spark("calendly_insights_tests")
    yield session
    session.stop()
