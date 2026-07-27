"""Unit tests for AppStateManager — canonical test file per design document.

This module re-exports all tests from test_app_state_manager.py and serves as
the test file referenced by the design document's test organization.

Tests cover: save, load_all, clear, clear_all operations with mocked
page.client_storage.
"""

# Re-export all tests from the detailed test module so that
# `pytest tests/test_app_state.py` runs the full suite.
from tests.test_app_state_manager import (  # noqa: F401
    MockClientStorage,
    TestAppStateManagerKeys,
    TestClear,
    TestClearAll,
    TestLoadAll,
    TestPrefixedKey,
    TestRoundTrip,
    TestSave,
    mock_page,
    manager,
)
