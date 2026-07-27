"""Property-based tests for font import validation.

# Feature: offline-cross-platform-app, Property 10: Font import validation
"""

import uuid as uuid_mod
from pathlib import Path
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings, strategies as st

from utils.font_manager import FontManager


def _make_minimal_ttf() -> bytes:
    """Load valid TTF bytes from the bundled Arial font for testing."""
    from utils.font_config import get_assets_root

    arial_path = get_assets_root() / "fonts" / "Arial.ttf"
    if arial_path.exists():
        return arial_path.read_bytes()
    # Fallback: use any .ttf that exists
    fonts_dir = get_assets_root() / "fonts"
    for font_file in fonts_dir.glob("*.ttf"):
        return font_file.read_bytes()
    return b""


# Cache the valid TTF bytes for reuse across tests
_VALID_TTF_BYTES = _make_minimal_ttf()


def _setup_dirs(tmp_path: Path):
    """Create assets and data directories (idempotent)."""
    assets_dir = tmp_path / "assets"
    data_dir = tmp_path / "data"
    assets_dir.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)
    (assets_dir / "fonts").mkdir(exist_ok=True)
    return assets_dir, data_dir


class TestProperty10FontImportValidation:
    """Property 10: FontManager accepts file iff: .ttf extension AND
    <= 10MB AND valid TTF (use mock for the Pillow validation part).

    **Validates: Requirements 5.2, 5.5**
    """

    @given(
        random_bytes=st.binary(min_size=0, max_size=1000),
        extension=st.sampled_from([".otf", ".woff", ".txt", ".png", ""]),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_non_ttf_extension_rejected(
        self, random_bytes: bytes, extension: str, tmp_path: Path
    ) -> None:
        """Files with non-.ttf extension are always rejected."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir, data_dir = _setup_dirs(tmp_path)

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font(f"testfont{extension}", random_bytes)

        assert not result.success, (
            f"Expected rejection for extension '{extension}'"
        )
        assert "ttf" in result.error_message.lower() or "type" in result.error_message.lower()

    def test_oversized_ttf_file_rejected(self, tmp_path: Path) -> None:
        """Files exceeding 10MB are rejected even with .ttf extension."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir, data_dir = _setup_dirs(tmp_path)

        manager = FontManager(assets_dir, data_dir)
        # Create bytes just over 10MB limit
        oversized = b"\x00\x01\x00\x00" + b"\x00" * (10 * 1024 * 1024 + 1)
        result = manager.import_font("bigfont.ttf", oversized)

        assert not result.success
        assert "size" in result.error_message.lower() or "MB" in result.error_message

    @given(
        random_bytes=st.binary(min_size=4, max_size=5000).filter(
            lambda b: b[:4] != b"\x00\x01\x00\x00" and b[:4] != b"OTTO"
        ),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_invalid_ttf_structure_rejected(
        self, random_bytes: bytes, tmp_path: Path
    ) -> None:
        """Files with .ttf extension but invalid TTF magic are rejected."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir, data_dir = _setup_dirs(tmp_path)

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font("invalid.ttf", random_bytes)

        assert not result.success, (
            "Expected rejection for invalid TTF bytes"
        )

    @given(
        name_prefix=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_valid_ttf_with_mock_pillow_accepted(
        self, name_prefix: str, tmp_path: Path
    ) -> None:
        """Valid TTF bytes with .ttf extension and <= 10MB are accepted
        (Pillow validation mocked to return True)."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        if not _VALID_TTF_BYTES:
            return  # Skip if no fonts available

        # Use unique subdirectory per iteration to avoid max-import limit
        unique_id = uuid_mod.uuid4().hex[:8]
        iter_path = tmp_path / unique_id
        iter_path.mkdir(exist_ok=True)
        assets_dir, data_dir = _setup_dirs(iter_path)

        manager = FontManager(assets_dir, data_dir)
        safe_name = "".join(c for c in name_prefix if c.isalnum()) or "Font"
        result = manager.import_font(f"{safe_name}.ttf", _VALID_TTF_BYTES)

        assert result.success, (
            f"Expected acceptance for name '{safe_name}' "
            f"but got: {result.error_message}"
        )

    def test_ttf_magic_but_invalid_tables_rejected(self, tmp_path: Path) -> None:
        """Bytes with TTF magic number but no valid glyph tables are rejected."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir, data_dir = _setup_dirs(tmp_path)

        # Craft bytes with valid magic but garbage content
        fake_ttf = b"\x00\x01\x00\x00" + b"\x00" * 500

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font("fake.ttf", fake_ttf)

        assert not result.success, (
            "File with TTF magic but no glyph tables should be rejected"
        )

    @given(
        random_bytes=st.binary(min_size=0, max_size=3),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_too_small_ttf_rejected(
        self, random_bytes: bytes, tmp_path: Path
    ) -> None:
        """Files smaller than 4 bytes cannot be valid TTF."""
        # Feature: offline-cross-platform-app, Property 10: Font import validation
        assets_dir, data_dir = _setup_dirs(tmp_path)

        manager = FontManager(assets_dir, data_dir)
        result = manager.import_font("tiny.ttf", random_bytes)

        assert not result.success
