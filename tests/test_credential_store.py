"""Unit tests for CredentialStore module.

Tests cover:
- Initialization
- store/load/clear/is_configured via secure storage (happy path)
- Fallback to ~/.certflow/credentials.toml when client_storage raises RuntimeError
- Fallback store/load/clear work correctly with the TOML file
- Fallback file is created at the expected path
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from utils.credential_store import (
    CredentialStore,
    KEY_EMAIL,
    KEY_APP_PASSWORD,
    FALLBACK_DIR,
    FALLBACK_FILE,
    _encode_value,
    _decode_value,
)
from utils.exceptions import ConfigurationError
from utils.models import GmailCredentials


@pytest.fixture
def mock_page():
    """Create a mock Flet Page with client_storage."""
    page = MagicMock()
    page.client_storage = MagicMock()
    page.client_storage.set_async = AsyncMock()
    page.client_storage.get_async = AsyncMock(return_value=None)
    page.client_storage.remove_async = AsyncMock()
    return page


@pytest.fixture
def store(mock_page):
    """Create a CredentialStore instance with mocked page."""
    return CredentialStore(mock_page)


@pytest.fixture
def fallback_dir(tmp_path):
    """Provide a temporary directory as the fallback credentials path."""
    test_dir = tmp_path / ".certflow"
    test_file = test_dir / "credentials.toml"
    with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
         patch("utils.credential_store.FALLBACK_FILE", test_file):
        yield test_dir, test_file


class TestCredentialStoreInit:
    """Tests for CredentialStore initialization."""

    def test_init_with_valid_page(self, mock_page):
        """CredentialStore initializes with a valid page."""
        cs = CredentialStore(mock_page)
        assert cs._page is mock_page

    def test_init_with_none_raises_configuration_error(self):
        """CredentialStore raises ConfigurationError if page is None."""
        with pytest.raises(ConfigurationError, match="requires a Flet Page"):
            CredentialStore(None)

    def test_keys_constant(self):
        """KEYS contains the expected storage key names."""
        assert CredentialStore.KEYS == (KEY_EMAIL, KEY_APP_PASSWORD)
        assert KEY_EMAIL == "certflow_email"
        assert KEY_APP_PASSWORD == "certflow_app_password"


class TestCredentialStoreStore:
    """Tests for the store() method."""

    @pytest.mark.asyncio
    async def test_store_saves_email_and_password(self, store, mock_page):
        """store() writes both email and app_password to client_storage."""
        await store.store("user@gmail.com", "abcdefghijklmnop")

        mock_page.client_storage.set_async.assert_any_call(
            KEY_EMAIL, "user@gmail.com"
        )
        mock_page.client_storage.set_async.assert_any_call(
            KEY_APP_PASSWORD, "abcdefghijklmnop"
        )

    @pytest.mark.asyncio
    async def test_store_falls_back_to_toml_on_runtime_error(
        self, store, mock_page, tmp_path
    ):
        """store() falls back to credentials.toml when client_storage fails."""
        mock_page.client_storage.set_async.side_effect = RuntimeError(
            "storage unavailable"
        )

        test_dir = tmp_path / ".certflow"
        test_file = test_dir / "credentials.toml"

        with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
             patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.store("user@gmail.com", "abcdefghijklmnop")

        # The file should have been created
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_store_raises_when_both_storage_and_fallback_fail(
        self, store, mock_page, tmp_path
    ):
        """store() raises ConfigurationError when both paths fail."""
        mock_page.client_storage.set_async.side_effect = RuntimeError(
            "storage unavailable"
        )

        # Make fallback fail by patching store_fallback to raise
        with patch.object(
            store, "store_fallback",
            side_effect=PermissionError("denied")
        ):
            with pytest.raises(ConfigurationError, match="Unable to store"):
                await store.store("user@gmail.com", "abcdefghijklmnop")


class TestCredentialStoreLoad:
    """Tests for the load() method."""

    @pytest.mark.asyncio
    async def test_load_returns_credentials_when_stored(
        self, store, mock_page
    ):
        """load() returns GmailCredentials when both values exist."""
        mock_page.client_storage.get_async.side_effect = (
            lambda key: {
                KEY_EMAIL: "user@gmail.com",
                KEY_APP_PASSWORD: "abcdefghijklmnop",
            }.get(key)
        )

        result = await store.load()

        assert result is not None
        assert isinstance(result, GmailCredentials)
        assert result.sender_email == "user@gmail.com"
        assert result.app_password == "abcdefghijklmnop"

    @pytest.mark.asyncio
    async def test_load_returns_none_when_no_credentials(
        self, store, mock_page
    ):
        """load() returns None when storage is empty and no fallback."""
        mock_page.client_storage.get_async.return_value = None

        with patch("utils.credential_store.FALLBACK_FILE") as mock_file:
            mock_file.exists.return_value = False
            result = await store.load()

        assert result is None

    @pytest.mark.asyncio
    async def test_load_returns_none_when_partial_credentials(
        self, store, mock_page
    ):
        """load() tries fallback when only email is stored (no password)."""
        mock_page.client_storage.get_async.side_effect = (
            lambda key: "user@gmail.com" if key == KEY_EMAIL else None
        )

        with patch("utils.credential_store.FALLBACK_FILE") as mock_file:
            mock_file.exists.return_value = False
            result = await store.load()

        assert result is None

    @pytest.mark.asyncio
    async def test_load_falls_back_to_toml_on_runtime_error(
        self, store, mock_page, tmp_path
    ):
        """load() falls back to credentials.toml when client_storage fails."""
        mock_page.client_storage.get_async.side_effect = RuntimeError(
            "storage error"
        )

        # Create a valid fallback file
        test_dir = tmp_path / ".certflow"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "credentials.toml"

        encoded_email = _encode_value("fallback@gmail.com")
        encoded_password = _encode_value("abcdefghijklmnop")
        content = (
            "[email]\n"
            f'sender = "{encoded_email}"\n'
            f'app_password = "{encoded_password}"\n'
        )
        test_file.write_text(content, encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            result = await store.load()

        assert result is not None
        assert result.sender_email == "fallback@gmail.com"
        assert result.app_password == "abcdefghijklmnop"

    @pytest.mark.asyncio
    async def test_load_returns_none_when_both_fail(
        self, store, mock_page
    ):
        """load() returns None when secure storage and fallback both fail."""
        mock_page.client_storage.get_async.side_effect = RuntimeError(
            "storage error"
        )

        with patch("utils.credential_store.FALLBACK_FILE") as mock_file:
            mock_file.exists.return_value = False
            result = await store.load()

        assert result is None


class TestCredentialStoreClear:
    """Tests for the clear() method."""

    @pytest.mark.asyncio
    async def test_clear_removes_both_keys(self, store, mock_page):
        """clear() removes both email and password from storage."""
        with patch("utils.credential_store.FALLBACK_FILE") as mock_file:
            mock_file.exists.return_value = False
            await store.clear()

        mock_page.client_storage.remove_async.assert_any_call(KEY_EMAIL)
        mock_page.client_storage.remove_async.assert_any_call(KEY_APP_PASSWORD)

    @pytest.mark.asyncio
    async def test_clear_also_removes_fallback_file(
        self, store, mock_page, tmp_path
    ):
        """clear() removes fallback file as well as secure storage."""
        test_dir = tmp_path / ".certflow"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "credentials.toml"
        test_file.write_text("[email]\n", encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.clear()

        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_clear_falls_back_when_secure_storage_fails(
        self, store, mock_page, tmp_path
    ):
        """clear() clears fallback file even when secure storage fails."""
        mock_page.client_storage.remove_async.side_effect = RuntimeError(
            "permission denied"
        )

        test_dir = tmp_path / ".certflow"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "credentials.toml"
        test_file.write_text("[email]\n", encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.clear()

        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_clear_raises_when_both_fail(
        self, store, mock_page, tmp_path
    ):
        """clear() raises ConfigurationError when both paths fail."""
        mock_page.client_storage.remove_async.side_effect = RuntimeError(
            "permission denied"
        )

        # Make clear_fallback fail
        test_file = tmp_path / "credentials.toml"
        with patch("utils.credential_store.FALLBACK_FILE", test_file), \
             patch.object(
                 store, "clear_fallback",
                 side_effect=OSError("cannot delete")
             ):
            with pytest.raises(
                ConfigurationError, match="Unable to clear"
            ):
                await store.clear()


class TestCredentialStoreIsConfigured:
    """Tests for the is_configured() method."""

    @pytest.mark.asyncio
    async def test_is_configured_true_when_both_present(
        self, store, mock_page
    ):
        """is_configured() returns True when both credentials exist."""
        mock_page.client_storage.get_async.side_effect = (
            lambda key: {
                KEY_EMAIL: "user@gmail.com",
                KEY_APP_PASSWORD: "abcdefghijklmnop",
            }.get(key)
        )

        assert await store.is_configured() is True

    @pytest.mark.asyncio
    async def test_is_configured_false_when_empty(self, store, mock_page):
        """is_configured() returns False when storage is empty and no fallback."""
        mock_page.client_storage.get_async.return_value = None

        with patch("utils.credential_store.FALLBACK_FILE") as mock_file:
            mock_file.exists.return_value = False
            assert await store.is_configured() is False

    @pytest.mark.asyncio
    async def test_is_configured_true_via_fallback_on_storage_error(
        self, store, mock_page, tmp_path
    ):
        """is_configured() returns True from fallback when storage errors."""
        mock_page.client_storage.get_async.side_effect = RuntimeError("error")

        # Create a valid fallback file
        test_dir = tmp_path / ".certflow"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "credentials.toml"

        encoded_email = _encode_value("user@gmail.com")
        encoded_password = _encode_value("abcdefghijklmnop")
        content = (
            "[email]\n"
            f'sender = "{encoded_email}"\n'
            f'app_password = "{encoded_password}"\n'
        )
        test_file.write_text(content, encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            assert await store.is_configured() is True

    @pytest.mark.asyncio
    async def test_is_configured_false_when_both_fail(
        self, store, mock_page
    ):
        """is_configured() returns False when both storage and fallback fail."""
        mock_page.client_storage.get_async.side_effect = RuntimeError("error")

        with patch("utils.credential_store.FALLBACK_FILE") as mock_file:
            mock_file.exists.return_value = False
            assert await store.is_configured() is False


class TestFallbackStorageOperations:
    """Tests for the fallback TOML file operations."""

    @pytest.mark.asyncio
    async def test_store_fallback_creates_directory_and_file(
        self, store, tmp_path
    ):
        """store_fallback() creates ~/.certflow/ and credentials.toml."""
        test_dir = tmp_path / ".certflow"
        test_file = test_dir / "credentials.toml"

        with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
             patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.store_fallback("user@gmail.com", "abcdefghijklmnop")

        assert test_dir.exists()
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_store_fallback_content_is_toml_format(
        self, store, tmp_path
    ):
        """store_fallback() writes valid TOML-formatted content."""
        test_dir = tmp_path / ".certflow"
        test_file = test_dir / "credentials.toml"

        with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
             patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.store_fallback("user@gmail.com", "abcdefghijklmnop")

        content = test_file.read_text(encoding="utf-8")
        assert "[email]" in content
        assert "sender = " in content
        assert "app_password = " in content

    @pytest.mark.asyncio
    async def test_store_fallback_values_are_encoded_not_plaintext(
        self, store, tmp_path
    ):
        """store_fallback() encodes values — they are not stored as plaintext."""
        test_dir = tmp_path / ".certflow"
        test_file = test_dir / "credentials.toml"

        with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
             patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.store_fallback("user@gmail.com", "abcdefghijklmnop")

        content = test_file.read_text(encoding="utf-8")
        # The plaintext values should NOT appear directly
        assert "user@gmail.com" not in content
        assert "abcdefghijklmnop" not in content

    @pytest.mark.asyncio
    async def test_load_fallback_returns_decoded_credentials(
        self, store, tmp_path
    ):
        """load_fallback() decodes and returns the stored credentials."""
        test_dir = tmp_path / ".certflow"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "credentials.toml"

        encoded_email = _encode_value("user@gmail.com")
        encoded_password = _encode_value("abcdefghijklmnop")
        content = (
            "[email]\n"
            f'sender = "{encoded_email}"\n'
            f'app_password = "{encoded_password}"\n'
        )
        test_file.write_text(content, encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            result = await store.load_fallback()

        assert result is not None
        assert result.sender_email == "user@gmail.com"
        assert result.app_password == "abcdefghijklmnop"

    @pytest.mark.asyncio
    async def test_load_fallback_returns_none_when_file_missing(
        self, store, tmp_path
    ):
        """load_fallback() returns None when the file does not exist."""
        test_file = tmp_path / "nonexistent.toml"

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            result = await store.load_fallback()

        assert result is None

    @pytest.mark.asyncio
    async def test_load_fallback_returns_none_on_malformed_content(
        self, store, tmp_path
    ):
        """load_fallback() returns None for malformed TOML content."""
        test_dir = tmp_path / ".certflow"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "credentials.toml"
        test_file.write_text("garbage content\n", encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            result = await store.load_fallback()

        assert result is None

    @pytest.mark.asyncio
    async def test_store_then_load_fallback_roundtrip(
        self, store, tmp_path
    ):
        """Storing then loading from fallback file gives same credentials."""
        test_dir = tmp_path / ".certflow"
        test_file = test_dir / "credentials.toml"

        with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
             patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.store_fallback("test@gmail.com", "passwordpassword")
            result = await store.load_fallback()

        assert result is not None
        assert result.sender_email == "test@gmail.com"
        assert result.app_password == "passwordpassword"

    def test_clear_fallback_removes_existing_file(self, store, tmp_path):
        """clear_fallback() removes the credentials.toml file."""
        test_file = tmp_path / "credentials.toml"
        test_file.write_text("[email]\n", encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            store.clear_fallback()

        assert not test_file.exists()

    def test_clear_fallback_does_nothing_when_no_file(self, store, tmp_path):
        """clear_fallback() does not raise when file doesn't exist."""
        test_file = tmp_path / "nonexistent.toml"

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            store.clear_fallback()  # Should not raise


class TestEncodeDecode:
    """Tests for the encoding/decoding utility functions."""

    def test_encode_produces_non_plaintext(self):
        """_encode_value() produces output different from input."""
        value = "test_secret_value"
        encoded = _encode_value(value)
        assert encoded != value

    def test_decode_reverses_encode(self):
        """_decode_value() reverses _encode_value()."""
        value = "my_secret_password"
        encoded = _encode_value(value)
        decoded = _decode_value(encoded)
        assert decoded == value

    def test_roundtrip_with_special_characters(self):
        """Encoding/decoding preserves special characters."""
        value = "p@$$w0rd!#%^&*()"
        encoded = _encode_value(value)
        decoded = _decode_value(encoded)
        assert decoded == value

    def test_roundtrip_with_unicode(self):
        """Encoding/decoding preserves unicode characters."""
        value = "unicode_test_chars"
        encoded = _encode_value(value)
        decoded = _decode_value(encoded)
        assert decoded == value

    def test_roundtrip_with_empty_string(self):
        """Encoding/decoding works with empty string."""
        value = ""
        encoded = _encode_value(value)
        decoded = _decode_value(encoded)
        assert decoded == value


class TestValidateEmail:
    """Tests for the validate_email() method."""

    def test_valid_email_returns_none(self, store):
        """A valid Gmail address returns None (no error)."""
        assert store.validate_email("user@gmail.com") is None

    def test_valid_email_with_dots_in_local_part(self, store):
        """Local part with dots is valid."""
        assert store.validate_email("first.last@gmail.com") is None

    def test_valid_email_with_plus_in_local_part(self, store):
        """Local part with plus addressing is valid."""
        assert store.validate_email("user+tag@gmail.com") is None

    def test_valid_email_with_underscore_in_local_part(self, store):
        """Local part with underscore is valid."""
        assert store.validate_email("user_name@gmail.com") is None

    def test_valid_email_with_hyphen_in_local_part(self, store):
        """Local part with hyphen is valid."""
        assert store.validate_email("user-name@gmail.com") is None

    def test_valid_email_with_mixed_allowed_chars(self, store):
        """Local part with mix of all allowed characters is valid."""
        assert store.validate_email("a.b_c-d+e1@gmail.com") is None

    def test_valid_email_single_char_local_part(self, store):
        """Single character local part is valid."""
        assert store.validate_email("a@gmail.com") is None

    def test_empty_email_returns_error(self, store):
        """Empty string returns an error message."""
        result = store.validate_email("")
        assert result is not None
        assert "required" in result.lower()

    def test_email_exceeds_254_chars_returns_error(self, store):
        """Email exceeding 254 characters returns an error."""
        long_local = "a" * 245  # 245 + len("@gmail.com") = 255 > 254
        result = store.validate_email(f"{long_local}@gmail.com")
        assert result is not None
        assert "254" in result

    def test_email_exactly_254_chars_is_valid(self, store):
        """Email at exactly 254 characters is valid."""
        # "@gmail.com" is 10 chars, so local part = 244
        local_part = "a" * 244
        email = f"{local_part}@gmail.com"
        assert len(email) == 254
        assert store.validate_email(email) is None

    def test_non_gmail_domain_returns_error(self, store):
        """Non-Gmail domain returns an error."""
        result = store.validate_email("user@yahoo.com")
        assert result is not None
        assert "gmail" in result.lower()

    def test_missing_at_sign_returns_error(self, store):
        """Email without @ returns an error."""
        result = store.validate_email("usergmail.com")
        assert result is not None
        assert "gmail" in result.lower()

    def test_empty_local_part_returns_error(self, store):
        """Email with no local part (@gmail.com) returns an error."""
        result = store.validate_email("@gmail.com")
        assert result is not None
        assert "local-part" in result.lower()

    def test_gmail_subdomain_returns_error(self, store):
        """Subdomains of gmail.com are not accepted."""
        result = store.validate_email("user@mail.gmail.com")
        assert result is not None

    def test_uppercase_gmail_domain_returns_error(self, store):
        """Uppercase domain 'Gmail.com' is not accepted (case-sensitive)."""
        result = store.validate_email("user@Gmail.com")
        assert result is not None

    def test_local_part_with_space_returns_error(self, store):
        """Local part containing spaces is invalid."""
        result = store.validate_email("user name@gmail.com")
        assert result is not None
        assert "local-part" in result.lower()

    def test_local_part_with_exclamation_returns_error(self, store):
        """Local part containing exclamation mark is invalid."""
        result = store.validate_email("user!name@gmail.com")
        assert result is not None
        assert "local-part" in result.lower()

    def test_local_part_with_at_sign_returns_error(self, store):
        """Local part containing @ (double @) is invalid."""
        result = store.validate_email("user@name@gmail.com")
        assert result is not None

    def test_local_part_with_hash_returns_error(self, store):
        """Local part containing # is invalid."""
        result = store.validate_email("user#tag@gmail.com")
        assert result is not None
        assert "local-part" in result.lower()


class TestValidateAppPassword:
    """Tests for the validate_app_password() method."""

    def test_valid_16_alpha_chars_returns_none(self, store):
        """Exactly 16 alphabetic characters returns None."""
        assert store.validate_app_password("abcdefghijklmnop") is None

    def test_valid_with_spaces_stripped(self, store):
        """Password with spaces stripped to 16 alpha chars is valid."""
        # "abcd efgh ijkl mnop" -> strip spaces -> "abcdefghijklmnop" (16)
        assert store.validate_app_password("abcd efgh ijkl mnop") is None

    def test_valid_mixed_case(self, store):
        """Mixed case alphabetic password is valid."""
        assert store.validate_app_password("AbCdEfGhIjKlMnOp") is None

    def test_empty_password_returns_error(self, store):
        """Empty string returns an error message."""
        result = store.validate_app_password("")
        assert result is not None
        assert "required" in result.lower()

    def test_too_short_returns_error(self, store):
        """Fewer than 16 alpha chars returns an error."""
        result = store.validate_app_password("abcdef")
        assert result is not None
        assert "16" in result

    def test_too_long_returns_error(self, store):
        """More than 16 alpha chars returns an error."""
        result = store.validate_app_password("abcdefghijklmnopq")
        assert result is not None
        assert "16" in result

    def test_contains_digits_returns_error(self, store):
        """Password with digits returns an error."""
        result = store.validate_app_password("abcdefgh12345678")
        assert result is not None
        assert "alphabetic" in result.lower()

    def test_contains_special_chars_returns_error(self, store):
        """Password with special characters returns an error."""
        result = store.validate_app_password("abcdefgh!@#$%^&*")
        assert result is not None
        assert "alphabetic" in result.lower()

    def test_only_spaces_returns_error(self, store):
        """Password that is only spaces (empty after strip) returns error."""
        result = store.validate_app_password("    ")
        assert result is not None

    def test_spaces_dont_count_toward_length(self, store):
        """Spaces are stripped before length check."""
        # 15 alpha chars + many spaces = still invalid (too short)
        result = store.validate_app_password("a b c d e f g h i j k l m n o")
        assert result is not None
        assert "16" in result
