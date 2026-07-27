"""Font management for CertFlow native app.

Provides FontManager for discovering bundled fonts and managing
user-imported fonts with persistence across sessions.
"""

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from utils.font_config import get_assets_root


@dataclass
class FontInfo:
    """Metadata about an available font.

    Attributes:
        name: Display name of the font (e.g., "Arial").
        filename: The font filename on disk (e.g., "Arial.ttf").
        path: Absolute path to the font file.
        is_bundled: True if this is a bundled font, False if user-imported.
        size_bytes: File size in bytes.
    """

    name: str
    filename: str
    path: str
    is_bundled: bool
    size_bytes: int


@dataclass
class FontImportResult:
    """Result of a font import operation.

    Attributes:
        success: True if the font was imported successfully.
        font_name: Display name of the imported font (empty on failure).
        error_message: Description of the failure (empty on success).
    """

    success: bool
    font_name: str = ""
    error_message: str = ""


# TrueType magic numbers for validation.
_TTF_MAGIC_TRUETYPE = b"\x00\x01\x00\x00"
_TTF_MAGIC_OTTO = b"OTTO"


# Mapping of bundled font display names to their actual filenames on disk.
_BUNDLED_FONT_FILENAMES: Dict[str, str] = {
    "Arial": "Arial.ttf",
    "Roboto": "Roboto-Regular.ttf",
    "Montserrat": "Montserrat-Regular.ttf",
    "PlayfairDisplay": "PlayfairDisplay-Regular.ttf",
    "GreatVibes": "GreatVibes-Regular.ttf",
}


class FontManager:
    """Manages bundled and user-imported fonts.

    Bundled fonts are stored in the application assets directory.
    Imported fonts are stored in `{data_dir}/fonts/` and their metadata
    is persisted in `{data_dir}/fonts/imported_fonts.json`.
    """

    BUNDLED_FONTS: List[str] = [
        "Arial", "Roboto", "Montserrat", "PlayfairDisplay", "GreatVibes"
    ]
    MAX_IMPORTED: int = 20
    MAX_FONT_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    def __init__(self, assets_dir: Path, data_dir: Path) -> None:
        """Initialize FontManager.

        Args:
            assets_dir: Path to the bundled assets root directory
                (contains a `fonts/` subdirectory with bundled .ttf files).
            data_dir: Path to the application's writable data directory
                (imported fonts stored in `{data_dir}/fonts/`).
        """
        self._assets_dir = assets_dir
        self._data_dir = data_dir
        self._imported_fonts_dir = data_dir / "fonts"
        self._metadata_path = self._imported_fonts_dir / "imported_fonts.json"

    @property
    def imported_fonts_dir(self) -> Path:
        """Return the directory path for imported fonts."""
        return self._imported_fonts_dir

    def _bundled_fonts_dir(self) -> Path:
        """Return the directory path for bundled fonts."""
        return self._assets_dir / "fonts"

    def _load_imported_metadata(self) -> List[Dict[str, str]]:
        """Load imported font metadata from the JSON persistence file.

        Returns:
            A list of dicts with keys: name, filename. Returns an empty
            list if the file does not exist or cannot be parsed.
        """
        if not self._metadata_path.exists():
            return []
        try:
            with open(self._metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_imported_metadata(self, metadata: List[Dict[str, str]]) -> None:
        """Persist imported font metadata to JSON file.

        Creates the fonts directory if it does not exist.

        Args:
            metadata: List of dicts with keys: name, filename.
        """
        self._imported_fonts_dir.mkdir(parents=True, exist_ok=True)
        with open(self._metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def get_available_fonts(self) -> List[FontInfo]:
        """List all fonts (bundled + imported) with metadata.

        Returns:
            A list of FontInfo objects for all available fonts. Bundled
            fonts appear first, followed by imported fonts.
        """
        fonts: List[FontInfo] = []

        # Bundled fonts
        bundled_dir = self._bundled_fonts_dir()
        for font_name in self.BUNDLED_FONTS:
            filename = _BUNDLED_FONT_FILENAMES.get(font_name, f"{font_name}.ttf")
            font_path = bundled_dir / filename
            size_bytes = 0
            if font_path.exists():
                size_bytes = font_path.stat().st_size
            fonts.append(FontInfo(
                name=font_name,
                filename=filename,
                path=str(font_path),
                is_bundled=True,
                size_bytes=size_bytes,
            ))

        # Imported fonts
        imported_metadata = self._load_imported_metadata()
        for entry in imported_metadata:
            name = entry.get("name", "")
            filename = entry.get("filename", "")
            if not name or not filename:
                continue
            font_path = self._imported_fonts_dir / filename
            size_bytes = 0
            if font_path.exists():
                size_bytes = font_path.stat().st_size
            fonts.append(FontInfo(
                name=name,
                filename=filename,
                path=str(font_path),
                is_bundled=False,
                size_bytes=size_bytes,
            ))

        return fonts

    def resolve_font_path(self, font_name: str) -> str:
        """Get absolute path for a font by name.

        Searches bundled fonts first, then imported fonts.

        Args:
            font_name: The display name of the font to resolve.

        Returns:
            Absolute string path to the font file.

        Raises:
            ValueError: If the font name is not found in bundled or
                imported fonts.
        """
        # Check bundled fonts
        if font_name in self.BUNDLED_FONTS:
            filename = _BUNDLED_FONT_FILENAMES.get(font_name, f"{font_name}.ttf")
            font_path = self._bundled_fonts_dir() / filename
            return str(font_path)

        # Check imported fonts
        imported_metadata = self._load_imported_metadata()
        for entry in imported_metadata:
            if entry.get("name") == font_name:
                filename = entry.get("filename", "")
                font_path = self._imported_fonts_dir / filename
                return str(font_path)

        raise ValueError(
            f"Font '{font_name}' not found in bundled or imported fonts."
        )

    def get_imported_font_count(self) -> int:
        """Return the number of currently imported fonts."""
        return len(self._load_imported_metadata())

    def add_imported_font(self, name: str, filename: str) -> None:
        """Register a new imported font in the metadata store.

        This method records the font in the persistence file. It does NOT
        validate or copy the font file — that responsibility belongs to
        the import validation logic (task 7.2).

        Args:
            name: Display name of the font.
            filename: Filename of the font in the imported fonts directory.

        Raises:
            ValueError: If the maximum imported font limit is reached or
                a font with the same name already exists.
        """
        metadata = self._load_imported_metadata()

        if len(metadata) >= self.MAX_IMPORTED:
            raise ValueError(
                f"Maximum number of imported fonts ({self.MAX_IMPORTED}) reached."
            )

        # Check for duplicate name
        for entry in metadata:
            if entry.get("name") == name:
                raise ValueError(
                    f"A font with name '{name}' is already imported."
                )

        metadata.append({"name": name, "filename": filename})
        self._save_imported_metadata(metadata)

    def remove_imported_font(self, font_name: str) -> bool:
        """Remove an imported font by name.

        Removes the font from the metadata store and deletes the font
        file from the imported fonts directory. Bundled fonts cannot be
        removed.

        Args:
            font_name: The display name of the font to remove.

        Returns:
            True if the font was found and removed, False if not found.

        Raises:
            ValueError: If attempting to remove a bundled font.
        """
        if font_name in self.BUNDLED_FONTS:
            raise ValueError(
                f"Cannot remove bundled font '{font_name}'."
            )

        metadata = self._load_imported_metadata()
        updated = []
        removed = False

        for entry in metadata:
            if entry.get("name") == font_name:
                # Delete the font file if it exists
                filename = entry.get("filename", "")
                font_path = self._imported_fonts_dir / filename
                if font_path.exists():
                    font_path.unlink()
                removed = True
            else:
                updated.append(entry)

        if removed:
            self._save_imported_metadata(updated)

        return removed

    def remove_font(self, font_name: str) -> bool:
        """Public-facing method to remove an imported font.

        Wraps remove_imported_font for a cleaner public API.

        Args:
            font_name: The display name of the font to remove.

        Returns:
            True if the font was found and removed, False if not found.

        Raises:
            ValueError: If attempting to remove a bundled font.
        """
        return self.remove_imported_font(font_name)

    def validate_ttf(self, file_bytes: bytes) -> bool:
        """Check if file bytes represent a valid TrueType font.

        Validates by checking the TrueType magic number in the first 4
        bytes. Valid signatures are 0x00010000 (TrueType) or "OTTO"
        (OpenType with CFF). Additionally attempts to load the font via
        Pillow's ImageFont to confirm at least one glyph table exists.

        Args:
            file_bytes: Raw bytes of the font file.

        Returns:
            True if the file is a valid TTF/OTF font, False otherwise.
        """
        if len(file_bytes) < 4:
            return False

        magic = file_bytes[:4]
        if magic != _TTF_MAGIC_TRUETYPE and magic != _TTF_MAGIC_OTTO:
            return False

        # Try loading with Pillow to confirm valid glyph table
        try:
            import io
            from PIL import ImageFont
            ImageFont.truetype(io.BytesIO(file_bytes), size=12)
            return True
        except (OSError, IOError, Exception):
            return False

    def import_font(self, file_path: str, file_bytes: bytes) -> FontImportResult:
        """Validate and store an imported TTF font.

        Performs the following validations:
        1. File extension must be .ttf (case-insensitive)
        2. File size must be <= MAX_FONT_SIZE_BYTES (10 MB)
        3. File must be a valid TrueType font with at least one glyph table
        4. Number of imported fonts must not exceed MAX_IMPORTED (20)

        If all validations pass, copies the file to the imported fonts
        directory and registers it in the metadata store.

        Args:
            file_path: Original file path/name (used for extension check
                and deriving the display name).
            file_bytes: Raw bytes of the font file.

        Returns:
            FontImportResult indicating success or failure with details.
        """
        # 1. Validate .ttf extension
        if not file_path.lower().endswith(".ttf"):
            return FontImportResult(
                success=False,
                error_message="Invalid file type. Only .ttf font files are accepted."
            )

        # 2. Validate file size
        if len(file_bytes) > self.MAX_FONT_SIZE_BYTES:
            return FontImportResult(
                success=False,
                error_message=(
                    f"Font file exceeds maximum size of "
                    f"{self.MAX_FONT_SIZE_BYTES // (1024 * 1024)} MB."
                )
            )

        # 3. Validate TTF structure
        if not self.validate_ttf(file_bytes):
            return FontImportResult(
                success=False,
                error_message="File is not a valid TTF font."
            )

        # 4. Check import limit
        if self.get_imported_font_count() >= self.MAX_IMPORTED:
            return FontImportResult(
                success=False,
                error_message=(
                    f"Maximum number of imported fonts "
                    f"({self.MAX_IMPORTED}) reached."
                )
            )

        # Derive font name from filename (without extension)
        filename = Path(file_path).name
        font_name = Path(filename).stem

        # Check for duplicate name
        metadata = self._load_imported_metadata()
        for entry in metadata:
            if entry.get("name") == font_name:
                return FontImportResult(
                    success=False,
                    error_message=(
                        f"A font with name '{font_name}' is already imported."
                    )
                )

        # 5. Copy file to imported fonts directory
        self._imported_fonts_dir.mkdir(parents=True, exist_ok=True)
        dest_path = self._imported_fonts_dir / filename
        dest_path.write_bytes(file_bytes)

        # 6. Register via add_imported_font
        try:
            self.add_imported_font(font_name, filename)
        except ValueError as e:
            # Clean up the file if registration fails
            if dest_path.exists():
                dest_path.unlink()
            return FontImportResult(
                success=False,
                error_message=str(e)
            )

        # 7. Return success result
        return FontImportResult(
            success=True,
            font_name=font_name
        )
