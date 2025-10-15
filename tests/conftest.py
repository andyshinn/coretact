"""Pytest configuration for Coretact tests.

Test storage is configured via pytest-env in pyproject.toml:
    [tool.pytest_env]
    STORAGE_PATH = "tests/storage"

This ensures all test data is isolated in the tests/storage directory.
"""

from pathlib import Path

import datafiles
import pytest


def pytest_runtest_setup(item):
    """Configure datafiles for testing."""
    # Disable automatic hooks for better performance
    datafiles.settings.HOOKS_ENABLED = False
    # Show detailed tracebacks for debugging
    datafiles.settings.HIDDEN_TRACEBACK = False


@pytest.fixture(autouse=True)
def clean_storage_between_tests():
    """Clean storage between each test for isolation.

    This ensures each test starts with a clean slate by removing
    all JSON files from the test storage directory after each test.
    """
    yield

    # Clean up after test
    from coretact.models import STORAGE_BASE_PATH

    storage_path = Path(STORAGE_BASE_PATH)

    if storage_path.exists():
        # Remove all .json files recursively
        for json_file in storage_path.rglob("*.json"):
            try:
                json_file.unlink()
            except Exception:
                pass  # Ignore errors during cleanup
