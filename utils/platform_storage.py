"""Platform-aware file storage for generated certificates.

Provides platform-specific directory resolution for certificate output
and application data, supporting Windows, macOS, Android, and iOS.
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)


class PlatformStorage:
    """Platform-aware file storage for generated certificates.

    Resolves platform-appropriate directories for certificate output
    and application data. Supports Windows, macOS, Android, and iOS
    with reasonable fallbacks for unknown platforms.
    """

    APP_NAME = "CertFlow"

    def _detect_platform(self) -> str:
        """Detect the current platform, including mobile environments.

        Returns:
            A string identifying the platform: 'windows', 'macos',
            'android', 'ios', or 'unknown'.
        """
        flet_platform = os.environ.get("FLET_PLATFORM", "").lower()
        if flet_platform == "android":
            return "android"
        if flet_platform == "ios":
            return "ios"

        if sys.platform == "win32":
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        if sys.platform == "linux":
            # On Android via Flet, sys.platform may report 'linux'
            # Check for Android-specific environment indicators
            if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
                return "android"
            return "linux"

        return "unknown"

    def get_output_directory(self) -> Path:
        """Return the platform-appropriate output directory for certificates.

        Returns:
            Path to the output directory:
            - Windows: ~/Documents/CertFlow/
            - macOS: ~/Documents/CertFlow/
            - Android: app external files directory (from env or fallback)
            - iOS: app Documents directory (from env or fallback)
            - Linux/unknown: ~/Documents/CertFlow/
        """
        platform = self._detect_platform()

        if platform == "android":
            # Prefer Flet-provided external files path via environment variable
            ext_dir = os.environ.get("FLET_APP_EXTERNAL_FILES_DIR")
            if ext_dir:
                return Path(ext_dir) / self.APP_NAME
            # Fallback: common Android external storage path
            android_storage = os.environ.get(
                "EXTERNAL_STORAGE", "/storage/emulated/0"
            )
            return Path(android_storage) / "Documents" / self.APP_NAME

        if platform == "ios":
            # Prefer Flet-provided documents path via environment variable
            ios_docs = os.environ.get("FLET_APP_DOCUMENTS_DIR")
            if ios_docs:
                return Path(ios_docs) / self.APP_NAME
            # Fallback: iOS app sandbox Documents directory
            home = Path.home()
            return home / "Documents" / self.APP_NAME

        # Windows, macOS, Linux, and unknown all use ~/Documents/CertFlow/
        home = Path.home()
        return home / "Documents" / self.APP_NAME

    def get_app_data_directory(self) -> Path:
        """Return the platform-appropriate app data directory.

        This directory is used for internal app data such as email queue,
        imported fonts, and configuration files.

        Returns:
            Path to the app data directory:
            - Windows: %APPDATA%/CertFlow/
            - macOS: ~/Library/Application Support/CertFlow/
            - Android: app internal data directory (from env or fallback)
            - iOS: app data container (from env or fallback)
            - Linux/unknown: ~/.local/share/CertFlow/
        """
        platform = self._detect_platform()

        if platform == "windows":
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / self.APP_NAME
            # Fallback if APPDATA is not set
            return Path.home() / "AppData" / "Roaming" / self.APP_NAME

        if platform == "macos":
            return (
                Path.home() / "Library" / "Application Support" / self.APP_NAME
            )

        if platform == "android":
            # Prefer Flet-provided internal data path
            data_dir = os.environ.get("FLET_APP_DATA_DIR")
            if data_dir:
                return Path(data_dir)
            # Fallback: common Android internal data path
            android_data = os.environ.get("ANDROID_DATA", "/data")
            return Path(android_data) / "data" / "com.certflow.app" / "files"

        if platform == "ios":
            # Prefer Flet-provided data container path
            ios_data = os.environ.get("FLET_APP_DATA_DIR")
            if ios_data:
                return Path(ios_data)
            # Fallback: iOS app sandbox Library/Application Support
            home = Path.home()
            return home / "Library" / "Application Support" / self.APP_NAME

        # Linux and unknown platforms
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return Path(xdg_data) / self.APP_NAME
        return Path.home() / ".local" / "share" / self.APP_NAME

    async def ensure_directory(self, path: Path) -> None:
        """Create the full directory tree if it doesn't exist.

        Args:
            path: The directory path to create. All intermediate
                directories will be created as needed.

        Raises:
            OSError: If the directory cannot be created due to
                permission or filesystem errors.
        """
        path.mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, name: str, extension: str) -> str:
        """Sanitize an attendee name for use as a filename.

        Replaces characters that are not alphanumeric or spaces with
        underscores, then replaces spaces with underscores, truncates
        the base name to 200 characters, and appends the extension.

        Args:
            name: The raw attendee name to sanitize.
            extension: The file extension including the leading dot
                (e.g., '.png', '.jpg', '.pdf').

        Returns:
            A sanitized filename string containing only alphanumeric
            characters and underscores, with the given extension.
        """
        # Replace non-alphanumeric and non-space characters with underscore
        sanitized = re.sub(r"[^a-zA-Z0-9 ]", "_", name)
        # Replace spaces with underscores
        sanitized = sanitized.replace(" ", "_")
        # Truncate base name to 200 characters
        sanitized = sanitized[:200]
        # Append extension
        return sanitized + extension

    def deduplicate_filename(self, filename: str, existing: Set[str]) -> str:
        """Ensure a filename is unique within a set of existing filenames.

        If the filename already exists in the set, appends a numeric
        suffix (_2, _3, etc.) before the extension until a unique name
        is found.

        Args:
            filename: The candidate filename to deduplicate.
            existing: A set of filenames already in use.

        Returns:
            A unique filename not present in the existing set.
        """
        if filename not in existing:
            return filename

        # Split into base name and extension
        dot_index = filename.rfind(".")
        if dot_index == -1:
            base = filename
            ext = ""
        else:
            base = filename[:dot_index]
            ext = filename[dot_index:]

        counter = 2
        while True:
            candidate = f"{base}_{counter}{ext}"
            if candidate not in existing:
                return candidate
            counter += 1

    async def write_certificate(
        self, filename: str, data: bytes
    ) -> Optional[str]:
        """Write certificate bytes to the output directory.

        Creates the output directory if it doesn't exist, then writes
        the certificate data to a file with the given filename.

        Args:
            filename: The sanitized filename for the certificate file.
            data: The raw certificate bytes to write.

        Returns:
            None on success, or an error message string on filesystem
            failure (e.g., permission denied, disk full).
        """
        output_dir = self.get_output_directory()
        try:
            await self.ensure_directory(output_dir)
            file_path = output_dir / filename
            file_path.write_bytes(data)
        except (PermissionError, OSError, IOError) as exc:
            error_msg = (
                f"Failed to write certificate '{filename}' "
                f"to '{output_dir}': {exc}"
            )
            logger.error(error_msg)
            return error_msg
        return None
