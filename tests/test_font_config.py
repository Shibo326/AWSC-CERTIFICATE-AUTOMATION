"""Tests for font configuration and assets root resolution."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.font_config import FontConfiguration, get_assets_root


class TestGetAssetsRoot:
    """Tests for get_assets_root() helper function."""

    def test_development_mode_returns_assets_dir(self):
        """In dev mode (no env var), returns assets/ relative to project root."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure FLET_ASSETS_DIR is not set
            os.environ.pop("FLET_ASSETS_DIR", None)
            result = get_assets_root()

        # Should resolve to <project_root>/assets
        project_root = Path(__file__).resolve().parent.parent
        expected = project_root / "assets"
        assert result == expected

    def test_development_mode_assets_dir_exists(self):
        """The resolved assets directory actually exists in dev mode."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLET_ASSETS_DIR", None)
            result = get_assets_root()

        assert result.exists()
        assert result.is_dir()

    def test_packaged_mode_uses_env_var(self, tmp_path):
        """When FLET_ASSETS_DIR is set, uses that path."""
        fake_assets = tmp_path / "bundled_assets"
        fake_assets.mkdir()

        with patch.dict(os.environ, {"FLET_ASSETS_DIR": str(fake_assets)}):
            result = get_assets_root()

        assert result == fake_assets.resolve()

    def test_packaged_mode_resolves_relative_env_var(self, tmp_path):
        """FLET_ASSETS_DIR with a relative path is resolved to absolute."""
        with patch.dict(os.environ, {"FLET_ASSETS_DIR": "relative/assets"}):
            result = get_assets_root()

        assert result.is_absolute()


class TestFontConfigurationDefaults:
    """Tests for FontConfiguration default path resolution."""

    def test_default_font_path_is_absolute(self):
        """Default font_path should be an absolute path."""
        config = FontConfiguration()
        assert Path(config.font_path).is_absolute()

    def test_default_font_path_points_to_arial(self):
        """Default font_path should end with fonts/Arial.ttf."""
        config = FontConfiguration()
        path = Path(config.font_path)
        assert path.name == "Arial.ttf"
        assert path.parent.name == "fonts"

    def test_default_font_path_file_exists(self):
        """Default font file should exist in development mode."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLET_ASSETS_DIR", None)
            config = FontConfiguration()

        assert Path(config.font_path).exists()

    def test_custom_font_path_preserved(self):
        """Explicitly provided font_path is not overridden."""
        config = FontConfiguration(font_path="/custom/path/font.ttf")
        assert config.font_path == "/custom/path/font.ttf"

    def test_default_font_size(self):
        """Default font size is 40."""
        config = FontConfiguration()
        assert config.font_size == 40

    def test_default_font_color(self):
        """Default font color is black (0, 0, 0)."""
        config = FontConfiguration()
        assert config.font_color == (0, 0, 0)


class TestFontConfigurationParseColor:
    """Tests for FontConfiguration.parse_color static method."""

    def test_valid_hex_color(self):
        """Parses valid hex color strings."""
        assert FontConfiguration.parse_color("#FF5733") == (255, 87, 51)

    def test_valid_hex_without_hash(self):
        """Parses hex color without leading #."""
        assert FontConfiguration.parse_color("000000") == (0, 0, 0)

    def test_valid_rgb_tuple(self):
        """Returns valid RGB tuples unchanged."""
        assert FontConfiguration.parse_color((128, 64, 32)) == (128, 64, 32)

    def test_invalid_hex_length(self):
        """Raises ValueError for hex strings with wrong length."""
        with pytest.raises(ValueError):
            FontConfiguration.parse_color("#FFF")

    def test_invalid_rgb_tuple_length(self):
        """Raises ValueError for tuples with wrong number of elements."""
        with pytest.raises(ValueError):
            FontConfiguration.parse_color((255, 0))  # type: ignore

    def test_invalid_rgb_value_out_of_range(self):
        """Raises ValueError for RGB values outside 0-255."""
        with pytest.raises(ValueError):
            FontConfiguration.parse_color((256, 0, 0))

    def test_invalid_type(self):
        """Raises ValueError for unsupported types."""
        with pytest.raises(ValueError):
            FontConfiguration.parse_color(12345)  # type: ignore
