"""Tests for platform-aware storage directory resolution."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.platform_storage import PlatformStorage


@pytest.fixture
def storage() -> PlatformStorage:
    """Create a PlatformStorage instance for testing."""
    return PlatformStorage()


class TestDetectPlatform:
    """Tests for _detect_platform method."""

    def test_flet_platform_android(self, storage: PlatformStorage) -> None:
        """FLET_PLATFORM=android should be detected as android."""
        with patch.dict(os.environ, {"FLET_PLATFORM": "android"}):
            assert storage._detect_platform() == "android"

    def test_flet_platform_ios(self, storage: PlatformStorage) -> None:
        """FLET_PLATFORM=ios should be detected as ios."""
        with patch.dict(os.environ, {"FLET_PLATFORM": "ios"}):
            assert storage._detect_platform() == "ios"

    def test_flet_platform_case_insensitive(
        self, storage: PlatformStorage
    ) -> None:
        """FLET_PLATFORM detection should be case-insensitive."""
        with patch.dict(os.environ, {"FLET_PLATFORM": "Android"}):
            assert storage._detect_platform() == "android"

    @patch("utils.platform_storage.sys.platform", "win32")
    def test_windows_detection(self, storage: PlatformStorage) -> None:
        """sys.platform == 'win32' should detect windows."""
        with patch.dict(os.environ, {}, clear=True):
            assert storage._detect_platform() == "windows"

    @patch("utils.platform_storage.sys.platform", "darwin")
    def test_macos_detection(self, storage: PlatformStorage) -> None:
        """sys.platform == 'darwin' should detect macos."""
        with patch.dict(os.environ, {}, clear=True):
            assert storage._detect_platform() == "macos"

    @patch("utils.platform_storage.sys.platform", "linux")
    def test_linux_detection(self, storage: PlatformStorage) -> None:
        """sys.platform == 'linux' without Android indicators -> linux."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("FLET_PLATFORM", "ANDROID_ROOT", "ANDROID_DATA")}
        with patch.dict(os.environ, env, clear=True):
            assert storage._detect_platform() == "linux"

    @patch("utils.platform_storage.sys.platform", "linux")
    def test_linux_with_android_root(self, storage: PlatformStorage) -> None:
        """Linux with ANDROID_ROOT should be detected as android."""
        with patch.dict(
            os.environ, {"ANDROID_ROOT": "/system"}, clear=True
        ):
            assert storage._detect_platform() == "android"


class TestGetOutputDirectory:
    """Tests for get_output_directory method."""

    def test_windows_output_directory(self, storage: PlatformStorage) -> None:
        """Windows should return ~/Documents/CertFlow/."""
        with patch.object(storage, "_detect_platform", return_value="windows"):
            result = storage.get_output_directory()
            assert result == Path.home() / "Documents" / "CertFlow"

    def test_macos_output_directory(self, storage: PlatformStorage) -> None:
        """macOS should return ~/Documents/CertFlow/."""
        with patch.object(storage, "_detect_platform", return_value="macos"):
            result = storage.get_output_directory()
            assert result == Path.home() / "Documents" / "CertFlow"

    def test_android_output_with_env(self, storage: PlatformStorage) -> None:
        """Android with FLET_APP_EXTERNAL_FILES_DIR should use that path."""
        with patch.object(storage, "_detect_platform", return_value="android"):
            with patch.dict(
                os.environ,
                {"FLET_APP_EXTERNAL_FILES_DIR": "/data/app/files"},
            ):
                result = storage.get_output_directory()
                assert result == Path("/data/app/files") / "CertFlow"

    def test_android_output_fallback(self, storage: PlatformStorage) -> None:
        """Android without env var should fall back to external storage."""
        with patch.object(storage, "_detect_platform", return_value="android"):
            env = {k: v for k, v in os.environ.items()
                   if k != "FLET_APP_EXTERNAL_FILES_DIR"}
            with patch.dict(os.environ, env, clear=True):
                result = storage.get_output_directory()
                assert "Documents" in str(result)
                assert "CertFlow" in str(result)

    def test_ios_output_with_env(self, storage: PlatformStorage) -> None:
        """iOS with FLET_APP_DOCUMENTS_DIR should use that path."""
        with patch.object(storage, "_detect_platform", return_value="ios"):
            with patch.dict(
                os.environ,
                {"FLET_APP_DOCUMENTS_DIR": "/var/mobile/Documents"},
            ):
                result = storage.get_output_directory()
                assert result == Path("/var/mobile/Documents") / "CertFlow"

    def test_ios_output_fallback(self, storage: PlatformStorage) -> None:
        """iOS without env var should fall back to ~/Documents/CertFlow/."""
        with patch.object(storage, "_detect_platform", return_value="ios"):
            env = {k: v for k, v in os.environ.items()
                   if k != "FLET_APP_DOCUMENTS_DIR"}
            with patch.dict(os.environ, env, clear=True):
                result = storage.get_output_directory()
                assert result == Path.home() / "Documents" / "CertFlow"


class TestGetAppDataDirectory:
    """Tests for get_app_data_directory method."""

    def test_windows_app_data_with_env(
        self, storage: PlatformStorage
    ) -> None:
        """Windows should use %APPDATA%/CertFlow/."""
        with patch.object(storage, "_detect_platform", return_value="windows"):
            with patch.dict(
                os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}
            ):
                result = storage.get_app_data_directory()
                assert result == Path(
                    "C:\\Users\\Test\\AppData\\Roaming"
                ) / "CertFlow"

    def test_windows_app_data_fallback(
        self, storage: PlatformStorage
    ) -> None:
        """Windows without APPDATA should use ~/AppData/Roaming/CertFlow/."""
        with patch.object(storage, "_detect_platform", return_value="windows"):
            env = {k: v for k, v in os.environ.items() if k != "APPDATA"}
            with patch.dict(os.environ, env, clear=True):
                result = storage.get_app_data_directory()
                expected = (
                    Path.home() / "AppData" / "Roaming" / "CertFlow"
                )
                assert result == expected

    def test_macos_app_data(self, storage: PlatformStorage) -> None:
        """macOS should use ~/Library/Application Support/CertFlow/."""
        with patch.object(storage, "_detect_platform", return_value="macos"):
            result = storage.get_app_data_directory()
            expected = (
                Path.home() / "Library" / "Application Support" / "CertFlow"
            )
            assert result == expected

    def test_android_app_data_with_env(
        self, storage: PlatformStorage
    ) -> None:
        """Android with FLET_APP_DATA_DIR should use that path directly."""
        with patch.object(storage, "_detect_platform", return_value="android"):
            with patch.dict(
                os.environ,
                {"FLET_APP_DATA_DIR": "/data/data/com.certflow.app/files"},
            ):
                result = storage.get_app_data_directory()
                assert result == Path(
                    "/data/data/com.certflow.app/files"
                )

    def test_ios_app_data_with_env(self, storage: PlatformStorage) -> None:
        """iOS with FLET_APP_DATA_DIR should use that path directly."""
        with patch.object(storage, "_detect_platform", return_value="ios"):
            with patch.dict(
                os.environ,
                {"FLET_APP_DATA_DIR": "/var/mobile/data"},
            ):
                result = storage.get_app_data_directory()
                assert result == Path("/var/mobile/data")

    def test_linux_app_data_with_xdg(self, storage: PlatformStorage) -> None:
        """Linux with XDG_DATA_HOME should use that path."""
        with patch.object(storage, "_detect_platform", return_value="linux"):
            with patch.dict(
                os.environ, {"XDG_DATA_HOME": "/home/user/.local/share"}
            ):
                result = storage.get_app_data_directory()
                assert result == Path("/home/user/.local/share") / "CertFlow"

    def test_linux_app_data_fallback(self, storage: PlatformStorage) -> None:
        """Linux without XDG_DATA_HOME should use ~/.local/share/CertFlow/."""
        with patch.object(storage, "_detect_platform", return_value="linux"):
            env = {k: v for k, v in os.environ.items()
                   if k != "XDG_DATA_HOME"}
            with patch.dict(os.environ, env, clear=True):
                result = storage.get_app_data_directory()
                expected = Path.home() / ".local" / "share" / "CertFlow"
                assert result == expected


class TestEnsureDirectory:
    """Tests for ensure_directory method."""

    @pytest.mark.asyncio
    async def test_creates_directory(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """ensure_directory should create the full directory tree."""
        target = tmp_path / "a" / "b" / "c"
        assert not target.exists()
        await storage.ensure_directory(target)
        assert target.exists()
        assert target.is_dir()

    @pytest.mark.asyncio
    async def test_existing_directory_no_error(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """ensure_directory should not raise if directory already exists."""
        target = tmp_path / "existing"
        target.mkdir()
        await storage.ensure_directory(target)
        assert target.exists()

    @pytest.mark.asyncio
    async def test_creates_nested_path(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """ensure_directory should create deeply nested paths."""
        target = tmp_path / "level1" / "level2" / "level3" / "level4"
        await storage.ensure_directory(target)
        assert target.exists()
        assert target.is_dir()


class TestSanitizeFilename:
    """Tests for sanitize_filename method."""

    def test_simple_name(self, storage: PlatformStorage) -> None:
        """Simple alphanumeric name should remain unchanged except spaces."""
        result = storage.sanitize_filename("John Smith", ".png")
        assert result == "John_Smith.png"

    def test_special_characters_replaced(
        self, storage: PlatformStorage
    ) -> None:
        """Non-alphanumeric/non-space characters become underscores."""
        result = storage.sanitize_filename("O'Brien-Jr.", ".pdf")
        assert result == "O_Brien_Jr_.pdf"

    def test_unicode_characters_replaced(
        self, storage: PlatformStorage
    ) -> None:
        """Unicode characters should be replaced with underscores."""
        result = storage.sanitize_filename("José García", ".jpg")
        assert result == "Jos__Garc_a.jpg"

    def test_spaces_replaced_with_underscores(
        self, storage: PlatformStorage
    ) -> None:
        """All spaces should become underscores."""
        result = storage.sanitize_filename("First  Middle  Last", ".png")
        assert result == "First__Middle__Last.png"

    def test_truncation_at_200_characters(
        self, storage: PlatformStorage
    ) -> None:
        """Base name should be truncated to 200 characters."""
        long_name = "A" * 300
        result = storage.sanitize_filename(long_name, ".pdf")
        base = result.replace(".pdf", "")
        assert len(base) == 200
        assert result.endswith(".pdf")

    def test_empty_name(self, storage: PlatformStorage) -> None:
        """Empty name should produce just the extension."""
        result = storage.sanitize_filename("", ".png")
        assert result == ".png"

    def test_only_special_characters(
        self, storage: PlatformStorage
    ) -> None:
        """A name with only special characters becomes underscores."""
        result = storage.sanitize_filename("@#$%", ".jpg")
        assert result == "____.jpg"

    def test_result_contains_only_valid_chars(
        self, storage: PlatformStorage
    ) -> None:
        """Sanitized base should only contain [a-zA-Z0-9_]."""
        import re
        result = storage.sanitize_filename("Test!@# Name$%^", ".png")
        base = result.replace(".png", "")
        assert re.fullmatch(r"[a-zA-Z0-9_]*", base)


class TestSanitizeFilenameAdditional:
    """Additional edge-case tests for sanitize_filename."""

    def test_special_chars_bang_at_hash(
        self, storage: PlatformStorage
    ) -> None:
        """Names with !@#$%^&* should all become underscores."""
        result = storage.sanitize_filename("Hi!@#$%^&*There", ".png")
        assert result == "Hi________There.png"

    def test_very_long_unicode_name(self, storage: PlatformStorage) -> None:
        """Long Unicode name (>200 chars) should be sanitized and truncated."""
        # 250 chars of mixed unicode
        long_name = "André" * 50  # 250 chars
        result = storage.sanitize_filename(long_name, ".pdf")
        base = result[: -len(".pdf")]
        assert len(base) <= 200
        assert result.endswith(".pdf")
        import re
        assert re.fullmatch(r"[a-zA-Z0-9_]*", base)

    def test_extension_preserved_jpg(self, storage: PlatformStorage) -> None:
        """Extension should be correctly appended for .jpg."""
        result = storage.sanitize_filename("Test Name", ".jpg")
        assert result == "Test_Name.jpg"

    def test_extension_preserved_pdf(self, storage: PlatformStorage) -> None:
        """Extension should be correctly appended for .pdf."""
        result = storage.sanitize_filename("Test", ".pdf")
        assert result == "Test.pdf"

    def test_mixed_valid_and_invalid_chars(
        self, storage: PlatformStorage
    ) -> None:
        """Mix of valid and invalid chars should produce correct output."""
        result = storage.sanitize_filename("A1 B2!C3@D4", ".png")
        assert result == "A1_B2_C3_D4.png"

    def test_tabs_and_newlines(self, storage: PlatformStorage) -> None:
        """Tabs and newlines should be replaced with underscores."""
        result = storage.sanitize_filename("Line1\tLine2\nLine3", ".png")
        assert result == "Line1_Line2_Line3.png"

    def test_exactly_200_chars_no_truncation(
        self, storage: PlatformStorage
    ) -> None:
        """Name that is exactly 200 chars should not be truncated."""
        name = "A" * 200
        result = storage.sanitize_filename(name, ".png")
        base = result[: -len(".png")]
        assert len(base) == 200

    def test_201_chars_truncated(self, storage: PlatformStorage) -> None:
        """Name that is 201 chars should be truncated to 200."""
        name = "B" * 201
        result = storage.sanitize_filename(name, ".png")
        base = result[: -len(".png")]
        assert len(base) == 200


class TestDeduplicateFilenameAdditional:
    """Additional edge-case tests for deduplicate_filename."""

    def test_many_duplicates(self, storage: PlatformStorage) -> None:
        """Should handle 10+ duplicates by incrementing suffix."""
        existing = {"report.pdf"}
        existing.update({f"report_{i}.pdf" for i in range(2, 12)})
        result = storage.deduplicate_filename("report.pdf", existing)
        assert result == "report_12.pdf"
        assert result not in existing

    def test_all_filenames_unique_after_batch(
        self, storage: PlatformStorage
    ) -> None:
        """Simulating a batch: all output filenames should be unique."""
        names = ["John Smith", "John Smith", "John Smith", "Jane Doe"]
        filenames: set[str] = set()
        results = []
        for name in names:
            sanitized = storage.sanitize_filename(name, ".png")
            deduped = storage.deduplicate_filename(sanitized, filenames)
            filenames.add(deduped)
            results.append(deduped)

        assert len(results) == len(set(results))
        assert results[0] == "John_Smith.png"
        assert results[1] == "John_Smith_2.png"
        assert results[2] == "John_Smith_3.png"
        assert results[3] == "Jane_Doe.png"

    def test_deduplicate_with_different_extensions(
        self, storage: PlatformStorage
    ) -> None:
        """Files with different extensions should not conflict."""
        existing = {"report.png"}
        result = storage.deduplicate_filename("report.pdf", existing)
        assert result == "report.pdf"


class TestDeduplicateFilename:
    """Tests for deduplicate_filename method."""

    def test_no_conflict(self, storage: PlatformStorage) -> None:
        """Filename not in existing set should be returned as-is."""
        result = storage.deduplicate_filename(
            "John_Smith.png", {"Jane_Doe.png"}
        )
        assert result == "John_Smith.png"

    def test_single_conflict(self, storage: PlatformStorage) -> None:
        """Single conflict should append _2."""
        result = storage.deduplicate_filename(
            "John_Smith.png", {"John_Smith.png"}
        )
        assert result == "John_Smith_2.png"

    def test_multiple_conflicts(self, storage: PlatformStorage) -> None:
        """Multiple conflicts should increment suffix."""
        existing = {"John_Smith.png", "John_Smith_2.png", "John_Smith_3.png"}
        result = storage.deduplicate_filename("John_Smith.png", existing)
        assert result == "John_Smith_4.png"

    def test_empty_existing_set(self, storage: PlatformStorage) -> None:
        """Empty existing set should return filename unchanged."""
        result = storage.deduplicate_filename("report.pdf", set())
        assert result == "report.pdf"

    def test_result_not_in_existing(self, storage: PlatformStorage) -> None:
        """Result should never be in the existing set."""
        existing = {"file.png", "file_2.png"}
        result = storage.deduplicate_filename("file.png", existing)
        assert result not in existing

    def test_preserves_extension(self, storage: PlatformStorage) -> None:
        """Deduplication should preserve the file extension."""
        result = storage.deduplicate_filename(
            "name.pdf", {"name.pdf"}
        )
        assert result.endswith(".pdf")

    def test_no_extension(self, storage: PlatformStorage) -> None:
        """Filename without extension should still deduplicate."""
        result = storage.deduplicate_filename(
            "filename", {"filename"}
        )
        assert result == "filename_2"


class TestWriteCertificate:
    """Tests for write_certificate method."""

    @pytest.mark.asyncio
    async def test_successful_write_creates_file(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """Successful write creates the file with correct content."""
        data = b"fake certificate PNG data \x89PNG\r\n"
        with patch.object(
            storage, "get_output_directory", return_value=tmp_path
        ):
            result = await storage.write_certificate("cert.png", data)

        assert result is None
        written_file = tmp_path / "cert.png"
        assert written_file.exists()
        assert written_file.read_bytes() == data

    @pytest.mark.asyncio
    async def test_write_to_readonly_directory_returns_error(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """Write to a read-only directory returns error message, not raises."""
        with patch.object(
            storage, "get_output_directory", return_value=tmp_path
        ):
            with patch.object(
                Path, "write_bytes",
                side_effect=PermissionError("Permission denied"),
            ):
                result = await storage.write_certificate(
                    "cert.png", b"certificate data"
                )

        # Should return an error message string, not raise
        assert result is not None
        assert isinstance(result, str)
        assert "cert.png" in result
        assert "Permission denied" in result

    @pytest.mark.asyncio
    async def test_multiple_writes_to_same_directory(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """Multiple writes to the same directory all succeed."""
        files = {
            "cert_alice.png": b"alice data",
            "cert_bob.pdf": b"bob data",
            "cert_carol.jpg": b"carol data",
        }

        with patch.object(
            storage, "get_output_directory", return_value=tmp_path
        ):
            for filename, data in files.items():
                result = await storage.write_certificate(filename, data)
                assert result is None

        for filename, data in files.items():
            written = tmp_path / filename
            assert written.exists()
            assert written.read_bytes() == data

    @pytest.mark.asyncio
    async def test_filename_with_special_characters(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """Filename with special characters (underscores, numbers) works."""
        # After sanitization, filenames may contain underscores and numbers
        filename = "Jos__Garc_a_2.pdf"
        data = b"%PDF-1.4 fake pdf content"

        with patch.object(
            storage, "get_output_directory", return_value=tmp_path
        ):
            result = await storage.write_certificate(filename, data)

        assert result is None
        written_file = tmp_path / filename
        assert written_file.exists()
        assert written_file.read_bytes() == data

    @pytest.mark.asyncio
    async def test_write_creates_output_directory_if_missing(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """write_certificate creates the output directory if it doesn't exist."""
        nested_dir = tmp_path / "new_output" / "certs"
        assert not nested_dir.exists()

        with patch.object(
            storage, "get_output_directory", return_value=nested_dir
        ):
            result = await storage.write_certificate(
                "test.png", b"test data"
            )

        assert result is None
        assert nested_dir.exists()
        assert (nested_dir / "test.png").read_bytes() == b"test data"

    @pytest.mark.asyncio
    async def test_oserror_returns_error_message(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """OSError during write returns an error message string."""
        with patch.object(
            storage, "get_output_directory", return_value=tmp_path
        ):
            with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
                result = await storage.write_certificate(
                    "cert.png", b"data"
                )

        assert result is not None
        assert "cert.png" in result
        assert "disk full" in result

    @pytest.mark.asyncio
    async def test_error_does_not_raise(
        self, storage: PlatformStorage, tmp_path: Path
    ) -> None:
        """Filesystem errors are caught and returned, never raised."""
        with patch.object(
            storage, "get_output_directory", return_value=tmp_path
        ):
            with patch.object(
                Path, "write_bytes",
                side_effect=PermissionError("access denied")
            ):
                # Should NOT raise
                result = await storage.write_certificate(
                    "cert.pdf", b"data"
                )
                assert result is not None
                assert "access denied" in result
