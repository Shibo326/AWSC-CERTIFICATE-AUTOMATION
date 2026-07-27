"""Tests for parts/customize_step.py — CustomizeStep UI component.

Tests the logic of the CustomizeStep component including settings state,
callback invocation, font option building, and hex color validation.
"""

import re
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

from utils.font_manager import FontInfo, FontManager


# We test the logic functions without needing a live Flet page.
# Import the module-level pattern and the class for unit testing.
from parts.customize_step import CustomizeStep, _HEX_COLOR_PATTERN


@pytest.fixture
def mock_font_manager(tmp_path: Path) -> FontManager:
    """Create a FontManager with a temp assets dir containing bundled fonts."""
    assets_dir = tmp_path / "assets"
    fonts_dir = assets_dir / "fonts"
    fonts_dir.mkdir(parents=True)

    # Create dummy bundled font files
    for name in ["Arial.ttf", "Roboto-Regular.ttf", "Montserrat-Regular.ttf",
                 "PlayfairDisplay-Regular.ttf", "GreatVibes-Regular.ttf"]:
        (fonts_dir / name).write_bytes(b"\x00" * 100)

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    return FontManager(assets_dir=assets_dir, data_dir=data_dir)


class TestHexColorValidation:
    """Test the hex color pattern used for validation."""

    def test_valid_hex_colors(self) -> None:
        """Valid 6-digit hex colors with # prefix should match."""
        valid = ["#000000", "#FFFFFF", "#ff5733", "#Ab12Cd", "#123456"]
        for color in valid:
            assert _HEX_COLOR_PATTERN.match(color), f"{color} should be valid"

    def test_invalid_hex_colors(self) -> None:
        """Invalid hex formats should not match."""
        invalid = [
            "000000",     # missing #
            "#FFF",       # too short (3 digits)
            "#GGGGGG",   # invalid hex chars
            "#12345",    # 5 digits
            "#1234567",  # 7 digits
            "",
            "#",
            "red",
        ]
        for color in invalid:
            assert not _HEX_COLOR_PATTERN.match(color), (
                f"{color} should be invalid"
            )


class TestCustomizeStepSettings:
    """Test CustomizeStep settings state and callback behavior."""

    def test_default_settings(self, mock_font_manager: FontManager) -> None:
        """CustomizeStep initializes with correct defaults."""
        mock_page = MagicMock()
        step = CustomizeStep(page=mock_page, font_manager=mock_font_manager)
        assert step.selected_font == "Arial"
        assert step.font_size == 40
        assert step.font_color == "#000000"
        assert step.vertical_position == 50

    def test_get_settings_returns_dict(
        self, mock_font_manager: FontManager
    ) -> None:
        """_get_settings returns a dict with expected keys."""
        mock_page = MagicMock()
        step = CustomizeStep(page=mock_page, font_manager=mock_font_manager)
        settings = step._get_settings()
        assert "font_name" in settings
        assert "font_size" in settings
        assert "font_color" in settings
        assert "vertical_position" in settings
        assert "font_path" in settings
        assert settings["font_name"] == "Arial"
        assert settings["font_size"] == 40
        assert settings["font_color"] == "#000000"
        assert settings["vertical_position"] == 50

    def test_callback_invoked_on_notify(
        self, mock_font_manager: FontManager
    ) -> None:
        """on_settings_changed callback is called with current settings."""
        callback = MagicMock()
        mock_page = MagicMock()
        step = CustomizeStep(
            page=mock_page,
            font_manager=mock_font_manager,
            on_settings_changed=callback,
        )
        step._notify_change()
        callback.assert_called_once()
        args = callback.call_args[0][0]
        assert args["font_name"] == "Arial"
        assert args["font_size"] == 40

    def test_no_callback_when_none(
        self, mock_font_manager: FontManager
    ) -> None:
        """No error when on_settings_changed is None."""
        mock_page = MagicMock()
        step = CustomizeStep(page=mock_page, font_manager=mock_font_manager)
        # Should not raise
        step._notify_change()

    def test_build_font_options_contains_bundled(
        self, mock_font_manager: FontManager
    ) -> None:
        """Font options should include all bundled fonts."""
        mock_page = MagicMock()
        step = CustomizeStep(page=mock_page, font_manager=mock_font_manager)
        options = step._build_font_options()
        option_keys = [opt.key for opt in options]
        assert "Arial" in option_keys
        assert "Roboto" in option_keys
        assert "Montserrat" in option_keys
        assert "PlayfairDisplay" in option_keys
        assert "GreatVibes" in option_keys

    def test_get_settings_with_invalid_font(
        self, mock_font_manager: FontManager
    ) -> None:
        """When selected font doesn't exist, font_path is empty string."""
        mock_page = MagicMock()
        step = CustomizeStep(page=mock_page, font_manager=mock_font_manager)
        step.selected_font = "NonExistentFont"
        settings = step._get_settings()
        assert settings["font_path"] == ""

    def test_settings_state_mutation(
        self, mock_font_manager: FontManager
    ) -> None:
        """Directly changing state attributes is reflected in get_settings."""
        mock_page = MagicMock()
        step = CustomizeStep(page=mock_page, font_manager=mock_font_manager)
        step.selected_font = "Roboto"
        step.font_size = 72
        step.font_color = "#FF0000"
        step.vertical_position = 25

        settings = step._get_settings()
        assert settings["font_name"] == "Roboto"
        assert settings["font_size"] == 72
        assert settings["font_color"] == "#FF0000"
        assert settings["vertical_position"] == 25
