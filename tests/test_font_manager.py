"""Unit tests for FontManager module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.font_manager import FontImportResult, FontInfo, FontManager


@pytest.fixture
def assets_dir(tmp_path: Path) -> Path:
    """Create a temporary assets directory with bundled font files."""
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)

    # Create dummy bundled font files
    bundled_files = {
        "Arial.ttf": b"fake-arial-font-data",
        "Roboto-Regular.ttf": b"fake-roboto-font-data",
        "Montserrat-Regular.ttf": b"fake-montserrat-font-data",
        "PlayfairDisplay-Regular.ttf": b"fake-playfair-font-data",
        "GreatVibes-Regular.ttf": b"fake-greatvibes-font-data",
    }
    for filename, content in bundled_files.items():
        (fonts_dir / filename).write_bytes(content)

    return tmp_path / "assets"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory for imported fonts."""
    data = tmp_path / "data"
    data.mkdir(parents=True)
    return data


@pytest.fixture
def font_manager(assets_dir: Path, data_dir: Path) -> FontManager:
    """Create a FontManager instance with temporary directories."""
    return FontManager(assets_dir=assets_dir, data_dir=data_dir)


class TestGetAvailableFonts:
    """Tests for FontManager.get_available_fonts()."""

    def test_lists_all_5_bundled_fonts(self, font_manager: FontManager) -> None:
        """get_available_fonts returns all 5 bundled fonts."""
        fonts = font_manager.get_available_fonts()
        bundled = [f for f in fonts if f.is_bundled]

        assert len(bundled) == 5
        bundled_names = {f.name for f in bundled}
        assert bundled_names == {
            "Arial", "Roboto", "Montserrat", "PlayfairDisplay", "GreatVibes"
        }

    def test_bundled_fonts_have_correct_filenames(
        self, font_manager: FontManager
    ) -> None:
        """Bundled fonts have the expected filenames."""
        fonts = font_manager.get_available_fonts()
        bundled = {f.name: f.filename for f in fonts if f.is_bundled}

        assert bundled["Arial"] == "Arial.ttf"
        assert bundled["Roboto"] == "Roboto-Regular.ttf"
        assert bundled["Montserrat"] == "Montserrat-Regular.ttf"
        assert bundled["PlayfairDisplay"] == "PlayfairDisplay-Regular.ttf"
        assert bundled["GreatVibes"] == "GreatVibes-Regular.ttf"

    def test_bundled_fonts_have_nonzero_size(
        self, font_manager: FontManager
    ) -> None:
        """Bundled fonts report a non-zero size_bytes."""
        fonts = font_manager.get_available_fonts()
        for f in fonts:
            if f.is_bundled:
                assert f.size_bytes > 0

    def test_no_imported_fonts_initially(self, font_manager: FontManager) -> None:
        """With no imports, only bundled fonts are listed."""
        fonts = font_manager.get_available_fonts()
        assert len(fonts) == 5
        assert all(f.is_bundled for f in fonts)

    def test_imported_fonts_appear_in_listing(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """Imported fonts appear after bundled fonts in the listing."""
        # Create an imported font file
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "CustomFont.ttf").write_bytes(b"fake-custom-font")

        # Register it
        font_manager.add_imported_font("CustomFont", "CustomFont.ttf")

        fonts = font_manager.get_available_fonts()
        assert len(fonts) == 6

        imported = [f for f in fonts if not f.is_bundled]
        assert len(imported) == 1
        assert imported[0].name == "CustomFont"
        assert imported[0].filename == "CustomFont.ttf"
        assert imported[0].is_bundled is False
        assert imported[0].size_bytes > 0

    def test_multiple_imported_fonts(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """Multiple imported fonts all appear in the listing."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)

        for i in range(3):
            filename = f"Font{i}.ttf"
            (imported_dir / filename).write_bytes(b"font-data-" + str(i).encode())
            font_manager.add_imported_font(f"Font{i}", filename)

        fonts = font_manager.get_available_fonts()
        assert len(fonts) == 8  # 5 bundled + 3 imported
        imported = [f for f in fonts if not f.is_bundled]
        assert len(imported) == 3


class TestResolveFontPath:
    """Tests for FontManager.resolve_font_path()."""

    def test_resolve_bundled_arial(
        self, font_manager: FontManager, assets_dir: Path
    ) -> None:
        """resolve_font_path returns correct path for bundled Arial."""
        path = font_manager.resolve_font_path("Arial")
        expected = str(assets_dir / "fonts" / "Arial.ttf")
        assert path == expected

    def test_resolve_bundled_roboto(
        self, font_manager: FontManager, assets_dir: Path
    ) -> None:
        """resolve_font_path returns correct path for bundled Roboto."""
        path = font_manager.resolve_font_path("Roboto")
        expected = str(assets_dir / "fonts" / "Roboto-Regular.ttf")
        assert path == expected

    def test_resolve_all_bundled_fonts(
        self, font_manager: FontManager, assets_dir: Path
    ) -> None:
        """resolve_font_path works for all 5 bundled fonts."""
        expected_map = {
            "Arial": "Arial.ttf",
            "Roboto": "Roboto-Regular.ttf",
            "Montserrat": "Montserrat-Regular.ttf",
            "PlayfairDisplay": "PlayfairDisplay-Regular.ttf",
            "GreatVibes": "GreatVibes-Regular.ttf",
        }
        for name, filename in expected_map.items():
            path = font_manager.resolve_font_path(name)
            assert path == str(assets_dir / "fonts" / filename)

    def test_resolve_imported_font(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """resolve_font_path returns correct path for an imported font."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "MyFont.ttf").write_bytes(b"font-data")
        font_manager.add_imported_font("MyFont", "MyFont.ttf")

        path = font_manager.resolve_font_path("MyFont")
        expected = str(imported_dir / "MyFont.ttf")
        assert path == expected

    def test_resolve_unknown_font_raises_value_error(
        self, font_manager: FontManager
    ) -> None:
        """resolve_font_path raises ValueError for unknown font name."""
        with pytest.raises(ValueError, match="not found"):
            font_manager.resolve_font_path("NonExistentFont")


class TestFontPersistence:
    """Tests for font metadata persistence across sessions."""

    def test_imported_fonts_persist_across_instances(
        self, assets_dir: Path, data_dir: Path
    ) -> None:
        """Imported fonts persist and are visible to a new FontManager instance."""
        # First instance: add a font
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "PersistFont.ttf").write_bytes(b"persist-font-data")

        mgr1 = FontManager(assets_dir=assets_dir, data_dir=data_dir)
        mgr1.add_imported_font("PersistFont", "PersistFont.ttf")

        # Second instance: should see the same font
        mgr2 = FontManager(assets_dir=assets_dir, data_dir=data_dir)
        fonts = mgr2.get_available_fonts()
        imported = [f for f in fonts if not f.is_bundled]
        assert len(imported) == 1
        assert imported[0].name == "PersistFont"

    def test_persistence_file_is_valid_json(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """The imported_fonts.json file is valid JSON after adding fonts."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "TestFont.ttf").write_bytes(b"test-data")
        font_manager.add_imported_font("TestFont", "TestFont.ttf")

        metadata_path = data_dir / "fonts" / "imported_fonts.json"
        assert metadata_path.exists()

        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "TestFont"
        assert data[0]["filename"] == "TestFont.ttf"

    def test_removed_font_not_in_persistence(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """After removing a font, it is no longer in the JSON file."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "RemoveMe.ttf").write_bytes(b"remove-data")
        font_manager.add_imported_font("RemoveMe", "RemoveMe.ttf")

        font_manager.remove_imported_font("RemoveMe")

        # New instance should not see it
        mgr2 = FontManager(assets_dir=font_manager._assets_dir, data_dir=data_dir)
        fonts = mgr2.get_available_fonts()
        imported = [f for f in fonts if not f.is_bundled]
        assert len(imported) == 0

    def test_corrupted_json_returns_empty_imports(
        self, assets_dir: Path, data_dir: Path
    ) -> None:
        """If imported_fonts.json is corrupted, imported list is empty."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = imported_dir / "imported_fonts.json"
        metadata_path.write_text("not valid json {{{", encoding="utf-8")

        mgr = FontManager(assets_dir=assets_dir, data_dir=data_dir)
        fonts = mgr.get_available_fonts()

        # Should still list bundled fonts, no imported
        assert len(fonts) == 5
        assert all(f.is_bundled for f in fonts)


class TestAddAndRemoveImportedFont:
    """Tests for add_imported_font and remove_imported_font."""

    def test_add_imported_font_increments_count(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """Adding a font increments the imported font count."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "NewFont.ttf").write_bytes(b"new-font")

        assert font_manager.get_imported_font_count() == 0
        font_manager.add_imported_font("NewFont", "NewFont.ttf")
        assert font_manager.get_imported_font_count() == 1

    def test_add_duplicate_name_raises_error(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """Adding a font with a duplicate name raises ValueError."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "Dup.ttf").write_bytes(b"dup-data")

        font_manager.add_imported_font("DupFont", "Dup.ttf")
        with pytest.raises(ValueError, match="already imported"):
            font_manager.add_imported_font("DupFont", "Dup2.ttf")

    def test_max_imported_limit_enforced(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """Cannot add more than MAX_IMPORTED fonts."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)

        for i in range(FontManager.MAX_IMPORTED):
            filename = f"Font{i}.ttf"
            (imported_dir / filename).write_bytes(b"data")
            font_manager.add_imported_font(f"Font{i}", filename)

        with pytest.raises(ValueError, match="Maximum number"):
            font_manager.add_imported_font("OneMore", "OneMore.ttf")

    def test_remove_bundled_font_raises_error(
        self, font_manager: FontManager
    ) -> None:
        """Cannot remove a bundled font."""
        with pytest.raises(ValueError, match="Cannot remove bundled"):
            font_manager.remove_imported_font("Arial")

    def test_remove_nonexistent_font_returns_false(
        self, font_manager: FontManager
    ) -> None:
        """Removing a font that doesn't exist returns False."""
        result = font_manager.remove_imported_font("GhostFont")
        assert result is False

    def test_remove_imported_font_deletes_file(
        self, font_manager: FontManager, data_dir: Path
    ) -> None:
        """Removing an imported font also deletes its file from disk."""
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        font_file = imported_dir / "DeleteMe.ttf"
        font_file.write_bytes(b"delete-me-data")

        font_manager.add_imported_font("DeleteMe", "DeleteMe.ttf")
        assert font_file.exists()

        font_manager.remove_imported_font("DeleteMe")
        assert not font_file.exists()


# Path to a real TTF font for testing valid imports
_REAL_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Arial.ttf"


@pytest.fixture
def valid_ttf_bytes() -> bytes:
    """Load real TTF bytes from the bundled Arial font for testing."""
    return _REAL_FONT_PATH.read_bytes()


class TestImportFont:
    """Tests for FontManager.import_font()."""

    def test_valid_ttf_import_succeeds(
        self, font_manager: FontManager, valid_ttf_bytes: bytes
    ) -> None:
        """A valid .ttf file is imported successfully."""
        result = font_manager.import_font("CustomFont.ttf", valid_ttf_bytes)

        assert result.success is True
        assert result.font_name == "CustomFont"
        assert result.error_message == ""

    def test_non_ttf_extension_rejected(
        self, font_manager: FontManager, valid_ttf_bytes: bytes
    ) -> None:
        """Files without .ttf extension are rejected."""
        result = font_manager.import_font("myfont.otf", valid_ttf_bytes)

        assert result.success is False
        assert "Only .ttf" in result.error_message

    def test_non_ttf_extension_case_insensitive(
        self, font_manager: FontManager, valid_ttf_bytes: bytes
    ) -> None:
        """Extension check is case-insensitive — .TTF is accepted."""
        result = font_manager.import_font("MyFont.TTF", valid_ttf_bytes)

        assert result.success is True
        assert result.font_name == "MyFont"

    def test_file_exceeding_max_size_rejected(
        self, font_manager: FontManager
    ) -> None:
        """Files larger than 10 MB are rejected."""
        # Create bytes just over the 10 MB limit
        oversized_bytes = b"\x00" * (FontManager.MAX_FONT_SIZE_BYTES + 1)
        result = font_manager.import_font("BigFont.ttf", oversized_bytes)

        assert result.success is False
        assert "exceeds maximum size" in result.error_message

    def test_invalid_bytes_rejected(
        self, font_manager: FontManager
    ) -> None:
        """Random bytes that aren't a valid TTF are rejected."""
        garbage_bytes = b"this is not a font file at all" * 100
        result = font_manager.import_font("garbage.ttf", garbage_bytes)

        assert result.success is False
        assert "not a valid TTF font" in result.error_message

    def test_bytes_with_correct_magic_but_invalid_structure_rejected(
        self, font_manager: FontManager
    ) -> None:
        """Bytes with TTF magic number but invalid structure are rejected."""
        # Start with correct magic number but garbage content
        fake_ttf = b"\x00\x01\x00\x00" + b"\x00" * 1000
        result = font_manager.import_font("fake.ttf", fake_ttf)

        assert result.success is False
        assert "not a valid TTF font" in result.error_message

    def test_max_20_limit_enforced(
        self, font_manager: FontManager, data_dir: Path, valid_ttf_bytes: bytes
    ) -> None:
        """Cannot import more than 20 fonts."""
        # Pre-fill with 20 fonts using add_imported_font directly
        imported_dir = data_dir / "fonts"
        imported_dir.mkdir(parents=True, exist_ok=True)
        for i in range(FontManager.MAX_IMPORTED):
            filename = f"Font{i}.ttf"
            (imported_dir / filename).write_bytes(b"data")
            font_manager.add_imported_font(f"Font{i}", filename)

        # Now try to import another via the import_font method
        result = font_manager.import_font("Font21.ttf", valid_ttf_bytes)

        assert result.success is False
        assert "Maximum number" in result.error_message

    def test_successful_import_appears_in_available_fonts(
        self, font_manager: FontManager, valid_ttf_bytes: bytes
    ) -> None:
        """A successfully imported font appears in get_available_fonts."""
        font_manager.import_font("NewImported.ttf", valid_ttf_bytes)

        fonts = font_manager.get_available_fonts()
        imported = [f for f in fonts if not f.is_bundled]
        assert len(imported) == 1
        assert imported[0].name == "NewImported"
        assert imported[0].filename == "NewImported.ttf"

    def test_successful_import_file_persisted_on_disk(
        self, font_manager: FontManager, data_dir: Path, valid_ttf_bytes: bytes
    ) -> None:
        """Imported font file is written to the imported fonts directory."""
        font_manager.import_font("DiskFont.ttf", valid_ttf_bytes)

        dest = data_dir / "fonts" / "DiskFont.ttf"
        assert dest.exists()
        assert dest.read_bytes() == valid_ttf_bytes

    def test_duplicate_name_rejected(
        self, font_manager: FontManager, valid_ttf_bytes: bytes
    ) -> None:
        """Cannot import a font with a name that already exists."""
        font_manager.import_font("SameName.ttf", valid_ttf_bytes)
        result = font_manager.import_font("SameName.ttf", valid_ttf_bytes)

        assert result.success is False
        assert "already imported" in result.error_message


class TestRemoveFont:
    """Tests for FontManager.remove_font() public wrapper."""

    def test_remove_font_removes_imported(
        self, font_manager: FontManager, data_dir: Path, valid_ttf_bytes: bytes
    ) -> None:
        """remove_font successfully removes an imported font."""
        font_manager.import_font("ToRemove.ttf", valid_ttf_bytes)

        result = font_manager.remove_font("ToRemove")
        assert result is True

        fonts = font_manager.get_available_fonts()
        imported = [f for f in fonts if not f.is_bundled]
        assert len(imported) == 0

    def test_remove_font_raises_for_bundled(
        self, font_manager: FontManager
    ) -> None:
        """remove_font raises ValueError for bundled fonts."""
        with pytest.raises(ValueError, match="Cannot remove bundled"):
            font_manager.remove_font("Arial")

    def test_remove_font_nonexistent_returns_false(
        self, font_manager: FontManager
    ) -> None:
        """remove_font returns False if font doesn't exist."""
        result = font_manager.remove_font("NoSuchFont")
        assert result is False


class TestValidateTtf:
    """Tests for FontManager.validate_ttf()."""

    def test_valid_ttf_bytes_accepted(
        self, font_manager: FontManager, valid_ttf_bytes: bytes
    ) -> None:
        """Real TTF bytes pass validation."""
        assert font_manager.validate_ttf(valid_ttf_bytes) is True

    def test_empty_bytes_rejected(self, font_manager: FontManager) -> None:
        """Empty bytes fail validation."""
        assert font_manager.validate_ttf(b"") is False

    def test_short_bytes_rejected(self, font_manager: FontManager) -> None:
        """Bytes shorter than 4 fail validation."""
        assert font_manager.validate_ttf(b"\x00\x01\x00") is False

    def test_wrong_magic_rejected(self, font_manager: FontManager) -> None:
        """Bytes with wrong magic number fail validation."""
        assert font_manager.validate_ttf(b"\xFF\xFF\xFF\xFF" + b"\x00" * 100) is False

    def test_correct_magic_but_invalid_content_rejected(
        self, font_manager: FontManager
    ) -> None:
        """Bytes with correct magic but no valid glyph table fail."""
        fake = b"\x00\x01\x00\x00" + b"\x00" * 500
        assert font_manager.validate_ttf(fake) is False
