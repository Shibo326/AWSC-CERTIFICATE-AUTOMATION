"""Unit tests for AppStateManager (SharedPreferences persistence).

Tests use a mock Flet page with a mock client_storage to verify
save, load_all, clear, and clear_all behavior.
"""

import os
import sys
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.app_state_manager import AppStateManager


class MockClientStorage:
    """In-memory mock of Flet's client_storage for testing."""

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    async def set_async(self, key: str, value: str) -> None:
        """Store a key-value pair."""
        self._store[key] = value

    async def get_async(self, key: str) -> Optional[str]:
        """Retrieve a value by key, or None if not found."""
        return self._store.get(key)

    async def remove_async(self, key: str) -> None:
        """Remove a key from storage."""
        self._store.pop(key, None)


@pytest.fixture
def mock_page() -> MagicMock:
    """Create a mock Flet page with in-memory client_storage."""
    page = MagicMock()
    page.client_storage = MockClientStorage()
    return page


@pytest.fixture
def manager(mock_page: MagicMock) -> AppStateManager:
    """Create an AppStateManager with mock page."""
    return AppStateManager(mock_page)


class TestAppStateManagerKeys:
    """Tests for the KEYS class attribute."""

    def test_keys_contains_all_required_settings(self) -> None:
        """All required persisted settings are present in KEYS."""
        expected_keys = [
            "template_path",
            "template_format",
            "attendee_path",
            "font_family",
            "font_size",
            "font_color",
            "vertical_position",
            "email_subject",
            "email_body",
        ]
        assert AppStateManager.KEYS == expected_keys

    def test_keys_count(self) -> None:
        """KEYS contains exactly 9 entries."""
        assert len(AppStateManager.KEYS) == 9


class TestSave:
    """Tests for the save method."""

    @pytest.mark.asyncio
    async def test_save_valid_key_stores_value(
        self, manager: AppStateManager, mock_page: MagicMock
    ) -> None:
        """Saving a valid key persists the value in storage."""
        await manager.save("font_family", "Roboto")

        stored = await mock_page.client_storage.get_async("certflow_font_family")
        assert stored == "Roboto"

    @pytest.mark.asyncio
    async def test_save_overwrites_existing_value(
        self, manager: AppStateManager, mock_page: MagicMock
    ) -> None:
        """Saving the same key again overwrites the previous value."""
        await manager.save("font_size", "40")
        await manager.save("font_size", "60")

        stored = await mock_page.client_storage.get_async("certflow_font_size")
        assert stored == "60"

    @pytest.mark.asyncio
    async def test_save_invalid_key_raises_value_error(
        self, manager: AppStateManager
    ) -> None:
        """Saving with an invalid key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid key 'invalid_key'"):
            await manager.save("invalid_key", "value")

    @pytest.mark.asyncio
    async def test_save_all_valid_keys(
        self, manager: AppStateManager, mock_page: MagicMock
    ) -> None:
        """All keys in KEYS can be saved without error."""
        for key in AppStateManager.KEYS:
            await manager.save(key, f"test_value_{key}")

        for key in AppStateManager.KEYS:
            stored = await mock_page.client_storage.get_async(f"certflow_{key}")
            assert stored == f"test_value_{key}"

    @pytest.mark.asyncio
    async def test_save_empty_string_value(
        self, manager: AppStateManager, mock_page: MagicMock
    ) -> None:
        """Saving an empty string is valid and persists."""
        await manager.save("email_subject", "")

        stored = await mock_page.client_storage.get_async("certflow_email_subject")
        assert stored == ""


class TestLoadAll:
    """Tests for the load_all method."""

    @pytest.mark.asyncio
    async def test_load_all_empty_storage_returns_none_values(
        self, manager: AppStateManager
    ) -> None:
        """Loading from empty storage returns None for all keys."""
        result = await manager.load_all()

        assert len(result) == len(AppStateManager.KEYS)
        for key in AppStateManager.KEYS:
            assert result[key] is None

    @pytest.mark.asyncio
    async def test_load_all_returns_saved_values(
        self, manager: AppStateManager
    ) -> None:
        """Loading after saving returns the correct values."""
        await manager.save("font_family", "Montserrat")
        await manager.save("font_size", "24")
        await manager.save("font_color", "#FF0000")

        result = await manager.load_all()

        assert result["font_family"] == "Montserrat"
        assert result["font_size"] == "24"
        assert result["font_color"] == "#FF0000"

    @pytest.mark.asyncio
    async def test_load_all_partial_storage_returns_mixed(
        self, manager: AppStateManager
    ) -> None:
        """When only some keys are saved, others return None."""
        await manager.save("template_path", "/path/to/template.png")

        result = await manager.load_all()

        assert result["template_path"] == "/path/to/template.png"
        assert result["attendee_path"] is None
        assert result["font_family"] is None

    @pytest.mark.asyncio
    async def test_load_all_returns_all_keys(
        self, manager: AppStateManager
    ) -> None:
        """load_all always returns a dict with every key from KEYS."""
        result = await manager.load_all()

        assert set(result.keys()) == set(AppStateManager.KEYS)


class TestClear:
    """Tests for the clear method."""

    @pytest.mark.asyncio
    async def test_clear_removes_stored_value(
        self, manager: AppStateManager
    ) -> None:
        """Clearing a key removes it from storage."""
        await manager.save("email_body", "Hello {name}")
        await manager.clear("email_body")

        result = await manager.load_all()
        assert result["email_body"] is None

    @pytest.mark.asyncio
    async def test_clear_nonexistent_key_does_not_raise(
        self, manager: AppStateManager
    ) -> None:
        """Clearing a key that was never saved does not raise."""
        await manager.clear("vertical_position")  # Should not raise

    @pytest.mark.asyncio
    async def test_clear_invalid_key_raises_value_error(
        self, manager: AppStateManager
    ) -> None:
        """Clearing an invalid key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid key 'nonexistent'"):
            await manager.clear("nonexistent")

    @pytest.mark.asyncio
    async def test_clear_does_not_affect_other_keys(
        self, manager: AppStateManager
    ) -> None:
        """Clearing one key leaves other stored values intact."""
        await manager.save("font_family", "Arial")
        await manager.save("font_size", "36")
        await manager.clear("font_family")

        result = await manager.load_all()
        assert result["font_family"] is None
        assert result["font_size"] == "36"


class TestClearAll:
    """Tests for the clear_all method."""

    @pytest.mark.asyncio
    async def test_clear_all_removes_all_stored_values(
        self, manager: AppStateManager
    ) -> None:
        """clear_all removes every persisted key."""
        for key in AppStateManager.KEYS:
            await manager.save(key, f"value_{key}")

        await manager.clear_all()

        result = await manager.load_all()
        for key in AppStateManager.KEYS:
            assert result[key] is None

    @pytest.mark.asyncio
    async def test_clear_all_on_empty_storage_does_not_raise(
        self, manager: AppStateManager
    ) -> None:
        """clear_all on empty storage completes without error."""
        await manager.clear_all()  # Should not raise

        result = await manager.load_all()
        for key in AppStateManager.KEYS:
            assert result[key] is None


class TestPrefixedKey:
    """Tests for the _prefixed_key helper method."""

    def test_prefixed_key_adds_certflow_prefix(
        self, manager: AppStateManager
    ) -> None:
        """Keys are prefixed with 'certflow_' for namespace isolation."""
        assert manager._prefixed_key("font_size") == "certflow_font_size"
        assert manager._prefixed_key("template_path") == "certflow_template_path"


class TestRoundTrip:
    """Tests for save-then-load round-trip correctness."""

    @pytest.mark.asyncio
    async def test_round_trip_all_settings(
        self, manager: AppStateManager
    ) -> None:
        """Persisting all settings and loading them back produces identical values."""
        settings = {
            "template_path": "/home/user/cert_template.png",
            "template_format": "png",
            "attendee_path": "/home/user/attendees.csv",
            "font_family": "GreatVibes",
            "font_size": "72",
            "font_color": "#1A2B3C",
            "vertical_position": "65",
            "email_subject": "Your Certificate, {name}!",
            "email_body": "Dear {name},\n\nCongratulations!\n\nBest regards",
        }

        for key, value in settings.items():
            await manager.save(key, value)

        result = await manager.load_all()

        for key, value in settings.items():
            assert result[key] == value, f"Mismatch for key '{key}'"

    @pytest.mark.asyncio
    async def test_round_trip_special_characters(
        self, manager: AppStateManager
    ) -> None:
        """Round-trip preserves special characters in values."""
        special_values = {
            "email_subject": "Hello World - Certificate",
            "email_body": "Line1\nLine2\tTabbed\r\nWindows line",
            "template_path": "C:\\Users\\User\\Documents\\template.png",
            "font_color": "#FFFFFF",
        }

        for key, value in special_values.items():
            await manager.save(key, value)

        result = await manager.load_all()

        for key, value in special_values.items():
            assert result[key] == value


class TestRestoreSession:
    """Tests for the restore_session method."""

    @pytest.mark.asyncio
    async def test_restore_with_all_valid_settings(
        self, manager: AppStateManager, mock_page: MagicMock, tmp_path
    ) -> None:
        """Restore with all valid settings returns correct PersistedState."""
        # Create real files for path validation
        template_file = tmp_path / "template.png"
        template_file.write_bytes(b"fake png")
        attendee_file = tmp_path / "attendees.csv"
        attendee_file.write_text("name,email")

        await manager.save("template_path", str(template_file))
        await manager.save("template_format", "png")
        await manager.save("attendee_path", str(attendee_file))
        await manager.save("font_family", "Roboto")
        await manager.save("font_size", "72")
        await manager.save("font_color", "#FF5500")
        await manager.save("vertical_position", "30")
        await manager.save("email_subject", "Congrats {name}!")
        await manager.save("email_body", "Dear {name},\n\nWell done.")

        state, warnings = await manager.restore_session()

        assert warnings == []
        assert state.template_path == str(template_file)
        assert state.template_format == "png"
        assert state.attendee_path == str(attendee_file)
        assert state.font_family == "Roboto"
        assert state.font_size == 72
        assert state.font_color == "#FF5500"
        assert state.vertical_position == 30
        assert state.email_subject == "Congrats {name}!"
        assert state.email_body == "Dear {name},\n\nWell done."

    @pytest.mark.asyncio
    async def test_restore_with_stale_template_path(
        self, manager: AppStateManager
    ) -> None:
        """Restore with stale template_path clears it and adds warning."""
        await manager.save("template_path", "/nonexistent/path/template.png")
        await manager.save("template_format", "png")
        await manager.save("font_family", "Arial")

        state, warnings = await manager.restore_session()

        assert state.template_path is None
        assert len(warnings) == 1
        assert "Template file not found: /nonexistent/path/template.png" in warnings[0]
        # template_format should still be restored
        assert state.template_format == "png"
        assert state.font_family == "Arial"

    @pytest.mark.asyncio
    async def test_restore_with_stale_attendee_path(
        self, manager: AppStateManager
    ) -> None:
        """Restore with stale attendee_path clears it and adds warning."""
        await manager.save("attendee_path", "/nonexistent/path/attendees.csv")
        await manager.save("font_size", "60")

        state, warnings = await manager.restore_session()

        assert state.attendee_path is None
        assert len(warnings) == 1
        assert "Attendee file not found: /nonexistent/path/attendees.csv" in warnings[0]
        assert state.font_size == 60

    @pytest.mark.asyncio
    async def test_restore_from_empty_storage_returns_defaults(
        self, manager: AppStateManager
    ) -> None:
        """Restore from empty storage returns defaults with no warnings."""
        state, warnings = await manager.restore_session()

        assert warnings == []
        assert state.template_path is None
        assert state.template_format is None
        assert state.attendee_path is None
        assert state.font_family == "Arial"
        assert state.font_size == 40
        assert state.font_color == "#000000"
        assert state.vertical_position == 50
        assert state.email_subject == "Your Certificate of Achievement"
        assert state.email_body == (
            "Hi {name},\n\nPlease find your certificate attached."
            "\n\nBest regards,\nThe Team"
        )

    @pytest.mark.asyncio
    async def test_restore_with_corrupted_font_size_returns_default(
        self, manager: AppStateManager
    ) -> None:
        """Restore with non-integer font_size uses default gracefully."""
        await manager.save("font_family", "Montserrat")
        await manager.save("font_size", "not_a_number")
        await manager.save("vertical_position", "abc")

        state, warnings = await manager.restore_session()

        assert state.font_family == "Montserrat"
        assert state.font_size == 40  # default
        assert state.vertical_position == 50  # default

    @pytest.mark.asyncio
    async def test_restore_with_load_all_exception_returns_defaults(
        self, manager: AppStateManager, mock_page: MagicMock
    ) -> None:
        """Restore returns defaults gracefully when load_all raises."""
        # Replace client_storage with one that raises on get_async
        original_storage = mock_page.client_storage

        class BrokenStorage:
            async def get_async(self, key):
                raise RuntimeError("Storage corrupted")

            async def set_async(self, key, value):
                pass

            async def remove_async(self, key):
                pass

        mock_page.client_storage = BrokenStorage()

        state, warnings = await manager.restore_session()

        assert warnings == []
        assert state.font_family == "Arial"
        assert state.font_size == 40
        assert state.template_path is None

        # Restore original storage for cleanup
        mock_page.client_storage = original_storage

    @pytest.mark.asyncio
    async def test_restore_with_both_stale_paths(
        self, manager: AppStateManager
    ) -> None:
        """Both stale paths produce two warnings and both are cleared."""
        await manager.save("template_path", "/gone/template.pdf")
        await manager.save("attendee_path", "/gone/list.csv")
        await manager.save("font_family", "GreatVibes")

        state, warnings = await manager.restore_session()

        assert state.template_path is None
        assert state.attendee_path is None
        assert len(warnings) == 2
        assert any("Template file not found" in w for w in warnings)
        assert any("Attendee file not found" in w for w in warnings)
        assert state.font_family == "GreatVibes"

    @pytest.mark.asyncio
    async def test_restore_valid_path_is_preserved(
        self, manager: AppStateManager, tmp_path
    ) -> None:
        """A file path that exists is preserved in the restored state."""
        real_file = tmp_path / "real_template.png"
        real_file.write_bytes(b"PNG content")

        await manager.save("template_path", str(real_file))
        await manager.save("font_family", "Arial")

        state, warnings = await manager.restore_session()

        assert state.template_path == str(real_file)
        assert warnings == []

    @pytest.mark.asyncio
    async def test_restore_clears_stale_path_from_storage(
        self, manager: AppStateManager, mock_page: MagicMock
    ) -> None:
        """Stale paths are cleared from underlying storage."""
        await manager.save("template_path", "/vanished/file.png")
        await manager.save("font_family", "Arial")

        await manager.restore_session()

        # Verify the path was cleared in storage
        stored = await mock_page.client_storage.get_async("certflow_template_path")
        assert stored is None
