"""Property-based tests for app state persistence.

# Feature: offline-cross-platform-app, Property 14: Settings persistence round-trip
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from hypothesis import given, settings, strategies as st

from utils.app_state_manager import AppStateManager


# Available font families (from FontManager.BUNDLED_FONTS)
AVAILABLE_FONTS = ["Arial", "Roboto", "Montserrat", "PlayfairDisplay", "GreatVibes"]

# Strategy for valid hex color strings
_hex_color_strategy = st.from_regex(r"#[0-9A-Fa-f]{6}", fullmatch=True)


def _create_mock_page_with_storage() -> MagicMock:
    """Create a mock Flet page with a dict-backed client_storage.

    The mock stores values in a dictionary and properly handles
    set_async, get_async, and remove_async calls.
    """
    page = MagicMock()
    storage_dict: dict = {}

    async def set_async(key: str, value: str) -> None:
        storage_dict[key] = value

    async def get_async(key: str):
        return storage_dict.get(key)

    async def remove_async(key: str) -> None:
        storage_dict.pop(key, None)

    page.client_storage = MagicMock()
    page.client_storage.set_async = AsyncMock(side_effect=set_async)
    page.client_storage.get_async = AsyncMock(side_effect=get_async)
    page.client_storage.remove_async = AsyncMock(side_effect=remove_async)

    return page


class TestProperty14SettingsPersistenceRoundTrip:
    """Property 14: For random valid settings (font family from known list,
    size 10-120, hex color, position 0-100, arbitrary strings for
    subject/body), persist all and load back produces identical values.

    **Validates: Requirements 12.2, 12.3, 12.4, 12.5**
    """

    @given(
        font_family=st.sampled_from(AVAILABLE_FONTS),
        font_size=st.integers(min_value=10, max_value=120),
        font_color=_hex_color_strategy,
        vertical_position=st.integers(min_value=0, max_value=100),
        email_subject=st.text(),
        email_body=st.text(),
    )
    @settings(max_examples=100)
    def test_persist_load_roundtrip_all_settings(
        self,
        font_family: str,
        font_size: int,
        font_color: str,
        vertical_position: int,
        email_subject: str,
        email_body: str,
    ) -> None:
        """Persisting all settings and loading back produces identical values."""
        # Feature: offline-cross-platform-app, Property 14: Settings persistence round-trip
        page = _create_mock_page_with_storage()
        manager = AppStateManager(page)

        async def save_and_load():
            await manager.save("font_family", font_family)
            await manager.save("font_size", str(font_size))
            await manager.save("font_color", font_color)
            await manager.save("vertical_position", str(vertical_position))
            await manager.save("email_subject", email_subject)
            await manager.save("email_body", email_body)

            # Load back
            loaded = await manager.load_all()
            return loaded

        loaded = asyncio.run(save_and_load())

        assert loaded["font_family"] == font_family, (
            f"font_family: expected '{font_family}', got '{loaded['font_family']}'"
        )
        assert loaded["font_size"] == str(font_size), (
            f"font_size: expected '{font_size}', got '{loaded['font_size']}'"
        )
        assert loaded["font_color"] == font_color, (
            f"font_color: expected '{font_color}', got '{loaded['font_color']}'"
        )
        assert loaded["vertical_position"] == str(vertical_position), (
            f"vertical_position: expected '{vertical_position}', "
            f"got '{loaded['vertical_position']}'"
        )
        assert loaded["email_subject"] == email_subject, (
            "email_subject mismatch"
        )
        assert loaded["email_body"] == email_body, (
            "email_body mismatch"
        )

    @given(
        font_family=st.sampled_from(AVAILABLE_FONTS),
        font_size=st.integers(min_value=10, max_value=120),
        font_color=_hex_color_strategy,
        vertical_position=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=100)
    def test_numeric_settings_survive_string_conversion(
        self,
        font_family: str,
        font_size: int,
        font_color: str,
        vertical_position: int,
    ) -> None:
        """Numeric values persisted as strings can be converted back."""
        # Feature: offline-cross-platform-app, Property 14: Settings persistence round-trip
        page = _create_mock_page_with_storage()
        manager = AppStateManager(page)

        async def save_and_load():
            await manager.save("font_family", font_family)
            await manager.save("font_size", str(font_size))
            await manager.save("font_color", font_color)
            await manager.save("vertical_position", str(vertical_position))

            loaded = await manager.load_all()
            return loaded

        loaded = asyncio.run(save_and_load())

        # Verify numeric conversions work
        assert int(loaded["font_size"]) == font_size
        assert int(loaded["vertical_position"]) == vertical_position

    @given(
        email_subject=st.text(min_size=1, max_size=300),
        email_body=st.text(min_size=1, max_size=1000),
    )
    @settings(max_examples=100)
    def test_arbitrary_text_settings_preserved(
        self, email_subject: str, email_body: str
    ) -> None:
        """Arbitrary Unicode text in subject/body is preserved exactly."""
        # Feature: offline-cross-platform-app, Property 14: Settings persistence round-trip
        page = _create_mock_page_with_storage()
        manager = AppStateManager(page)

        async def save_and_load():
            await manager.save("email_subject", email_subject)
            await manager.save("email_body", email_body)
            loaded = await manager.load_all()
            return loaded

        loaded = asyncio.run(save_and_load())

        assert loaded["email_subject"] == email_subject
        assert loaded["email_body"] == email_body
