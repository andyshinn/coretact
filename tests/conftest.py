"""Pytest configuration for Coretact tests."""

import os

import datafiles
import pytest


def pytest_runtest_setup(item):
    """Configure datafiles for testing."""
    # Disable automatic hooks for better performance
    datafiles.settings.HOOKS_ENABLED = False
    # Show detailed tracebacks for debugging
    datafiles.settings.HIDDEN_TRACEBACK = False


@pytest.fixture(autouse=True)
def clean_storage():
    """Clean up storage directory after each test."""
    yield
    # Clean up any test files created in the actual storage directory
    storage_path = os.path.join(os.path.dirname(__file__), "..", "storage")
    if os.path.exists(storage_path):
        for root, dirs, files in os.walk(storage_path):
            for file in files:
                if file.endswith(".json"):
                    os.remove(os.path.join(root, file))
