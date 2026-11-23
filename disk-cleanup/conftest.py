"""Fails the run below 85% line coverage (cleanup_coverage.py)."""
from cleanup_coverage import cov


def pytest_sessionfinish(session, exitstatus):
    cov.finish(session)
