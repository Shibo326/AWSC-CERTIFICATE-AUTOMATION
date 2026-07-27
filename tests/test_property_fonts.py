"""Property-based tests for font import validation.

# Feature: offline-cross-platform-app, Property 10: Font import validation

For any file submitted for font import, FontManager accepts it iff:
(a) the file extension is .ttf, (b) the file size is at most 10 MB,
and (c) the file content is a valid TrueType font with at least one
glyph table present.

**Validates: Requirements 5.2, 5.5**
"""

from pathlib import Path
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings, strategies as st

from utils.font_manager import FontManager


def _get_valid_ttf_bytes() -> bytes:
    """Get valid TTF bytes from a bundled font for testing."""
    from utils.font_config import get_assets_root

    arial_path = get_assets_root() / "fonts" / "Arial.ttf"
    if arial_path.exists():
        return arial_path.read_bytes()
    fonts_dir = get_assets_root() / "fonts"
    for font_file in fonts_dir.glob("*.ttf"):
        return font_file.read_bytes()
    return b""


_VALID_TTF_BYTES = _get_valid_ttf_bytes()


class TestProperty10FontValidation:
    """Property 10: Random bytes are rejected, real TTF bytes are accepted."""

    @given(
        random_bytes=st.binary(min_size=0, max_size=1000),
        extension=st.sampled_from([".otf", ".woff", ".txt", ".png", ""]),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_random_bytes_non_ttf_extension_rejected(
        self, random_bytes: bytes, extension: str, tmp_path: Path
    ) -> None:
        """Files with non-.ttf extension are always rejected."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir = tmp_path / "assets"
        data_dir = tmp_path / "data"
        assets_dir.mkdir(exist_ok=True)
        data_dir.mkdir(exist_ok=True)
        (assets_dir / "fonts").mkdir(exist_ok=True)

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font(f"testfont{extension}", random_bytes)

        assert not result.success, (
            f"Expected rejection for extension '{extension}'"
        )

    @given(
        random_bytes=st.binary(min_size=4, max_size=5000).filter(
            lambda b: b[:4] != b"\x00\x01\x00\x00" and b[:4] != b"OTTO"
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_random_bytes_invalid_ttf_rejected(
        self, random_bytes: bytes, tmp_path: Path
    ) -> None:
        """Files with .ttf extension but invalid TTF magic are rejected."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir = tmp_path / "assets"
        data_dir = tmp_path / "data"
        assets_dir.mkdir(exist_ok=True)
        data_dir.mkdir(exist_ok=True)
        (assets_dir / "fonts").mkdir(exist_ok=True)

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font("invalid.ttf", random_bytes)

        assert not result.success

    def test_valid_ttf_bytes_accepted(self, tmp_path: Path) -> None:
        """A valid TTF file with .ttf extension and <= 10MB is accepted."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        if not _VALID_TTF_BYTES:
            return  # Skip if no fonts available

        assets_dir = tmp_path / "assets"
        data_dir = tmp_path / "data"
        assets_dir.mkdir(exist_ok=True)
        data_dir.mkdir(exist_ok=True)
        (assets_dir / "fonts").mkdir(exist_ok=True)

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font("ValidFont.ttf", _VALID_TTF_BYTES)

        assert result.success, (
            f"Expected acceptance but got error: {result.error_message}"
        )
        assert result.font_name == "ValidFont"

    @given(
        random_bytes=st.binary(min_size=0, max_size=3),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_too_small_bytes_rejected(
        self, random_bytes: bytes, tmp_path: Path
    ) -> None:
        """Files smaller than 4 bytes cannot be valid TTF."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir = tmp_path / "assets"
        data_dir = tmp_path / "data"
        assets_dir.mkdir(exist_ok=True)
        data_dir.mkdir(exist_ok=True)
        (assets_dir / "fonts").mkdir(exist_ok=True)

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font("tiny.ttf", random_bytes)

        assert not result.success

    def test_ttf_magic_but_no_glyphs_rejected(self, tmp_path: Path) -> None:
        """Bytes with TTF magic number but no valid glyph tables are rejected."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir = tmp_path / "assets"
        data_dir = tmp_path / "data"
        assets_dir.mkdir(exist_ok=True)
        data_dir.mkdir(exist_ok=True)
        (assets_dir / "fonts").mkdir(exist_ok=True)

        fake_ttf = b"\x00\x01\x00\x00" + b"\x00" * 500

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font("fake.ttf", fake_ttf)

        assert not result.success
