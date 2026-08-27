"""Secure credential storage for CertFlow using Flet's client storage.

This module provides platform-agnostic credential management backed by
platform-native secure storage mechanisms:
- iOS: Keychain
- Android: Keystore
- Windows: DPAPI (via flutter_secure_storage)
- macOS: Keychain

When platform secure storage is unavailable (permission denied, missing
service, or runtime error), the module falls back to an encoded
credentials.toml file at ~/.certflow/credentials.toml.

Requires a Flet Page context to access client_storage.
"""

import base64
import logging
import os
import platform
import re
from pathlib import Path
from typing import Optional

import flet as ft

from utils.exceptions import ConfigurationError
from utils.models import GmailCredentials

logger = logging.getLogger(__name__)

KEY_EMAIL = "certflow_email"
KEY_APP_PASSWORD = "certflow_app_password"

# Fallback credentials file path
FALLBACK_DIR = Path.home() / ".certflow"
FALLBACK_FILE = FALLBACK_DIR / "credentials.toml"

# Allowed characters in the local-part of the email:
# alphanumeric, dots, underscores, hyphens, plus signs
_LOCAL_PART_PATTERN = re.compile(r"^[a-zA-Z0-9._\-+]+$")


def _get_machine_salt() -> str:
    """Get a machine-specific salt for encoding credentials.

    Uses platform.node() (hostname) as the primary source, falling back
    to os.getlogin() if node() returns empty.

    Returns:
        A non-empty string unique to the machine.
    """
    salt = platform.node()
    if not salt:
        try:
            salt = os.getlogin()
        except OSError:
            salt = "certflow_default_salt"
    return salt


def _encode_value(value: str) -> str:
    """Encode a credential value using base64 with a machine-specific salt.

    The encoding XORs each byte of the value with a repeating salt,
    then base64-encodes the result.

    Args:
        value: The plaintext credential value.

    Returns:
        A base64-encoded string.
    """
    salt = _get_machine_salt()
    salt_bytes = salt.encode("utf-8")
    value_bytes = value.encode("utf-8")
    xored = bytes(
        v ^ salt_bytes[i % len(salt_bytes)]
        for i, v in enumerate(value_bytes)
    )
    return base64.b64encode(xored).decode("ascii")


def _decode_value(encoded: str) -> str:
    """Decode a credential value that was encoded with _encode_value.

    Args:
        encoded: The base64-encoded string.

    Returns:
        The original plaintext credential value.
    """
    salt = _get_machine_salt()
    salt_bytes = salt.encode("utf-8")
    xored = base64.b64decode(encoded.encode("ascii"))
    value_bytes = bytes(
        x ^ salt_bytes[i % len(salt_bytes)]
        for i, x in enumerate(xored)
    )
    return value_bytes.decode("utf-8")


def _extract_toml_value(line: str) -> Optional[str]:
    """Extract the quoted value from a TOML key = "value" line.

    Args:
        line: A stripped line in the format: key = "value"

    Returns:
        The unquoted value string, or None if parsing fails.
    """
    match = re.search(r'=\s*"([^"]*)"', line)
    if match:
        return match.group(1)
    return None


class CredentialStore:
    """Platform-agnostic credential management using Flet's client storage.

    Flet's client_storage wraps flutter_secure_storage under the hood,
    which uses iOS Keychain, Android Keystore, Windows DPAPI, and
    macOS Keychain for secure persistence.

    Attributes:
        KEYS: Tuple of storage key names used for credentials.
    """

    KEYS = (KEY_EMAIL, KEY_APP_PASSWORD)

    def __init__(self, page: ft.Page) -> None:
        """Initialize the credential store with a Flet page context.

        Args:
            page: The Flet Page instance providing access to client_storage.

        Raises:
            ConfigurationError: If page is None or does not support
                client_storage.
        """
        if page is None:
            raise ConfigurationError(
                "CredentialStore requires a Flet Page instance for "
                "secure storage access."
            )
        self._page = page

    async def store(self, email: str, app_password: str) -> None:
        """Store Gmail credentials in platform secure storage.

        If platform secure storage is unavailable, falls back to an
        encoded credentials.toml file at ~/.certflow/credentials.toml.

        Args:
            email: Gmail address to store.
            app_password: Gmail App Password (16 alphabetic characters).

        Raises:
            ConfigurationError: If both secure storage and fallback fail.
        """
        try:
            await self._page.client_storage.set_async(KEY_EMAIL, email)
            await self._page.client_storage.set_async(
                KEY_APP_PASSWORD, app_password
            )
            logger.info("Credentials stored successfully in secure storage.")
        except Exception as e:
            logger.warning(
                "Secure storage unavailable, falling back to "
                "credentials.toml: %s", e
            )
            try:
                await self.store_fallback(email, app_password)
            except Exception as fallback_err:
                logger.error(
                    "Fallback storage also failed: %s", fallback_err
                )
                raise ConfigurationError(
                    f"Unable to store credentials. Secure storage error: {e}. "
                    f"Fallback error: {fallback_err}"
                ) from fallback_err

    async def load(self) -> Optional[GmailCredentials]:
        """Load credentials from secure storage, falling back to file.

        Tries platform secure storage first. If it raises (permission
        denied, missing service), tries loading from the fallback
        credentials.toml file. Returns None only if both fail to find
        credentials.

        Returns:
            GmailCredentials if credentials are found in either source,
            None if credentials are not configured anywhere.
        """
        try:
            email = await self._page.client_storage.get_async(KEY_EMAIL)
            app_password = await self._page.client_storage.get_async(
                KEY_APP_PASSWORD
            )
            if email and app_password:
                return GmailCredentials(
                    sender_email=email, app_password=app_password
                )
            # Credentials not found in secure storage, try fallback
            return await self.load_fallback()
        except Exception as e:
            logger.warning(
                "Secure storage read failed, trying fallback: %s", e
            )
            try:
                return await self.load_fallback()
            except Exception as fallback_err:
                logger.error(
                    "Fallback load also failed: %s", fallback_err
                )
                return None

    async def clear(self) -> None:
        """Remove all stored credentials from platform secure storage.

        Also removes the fallback file if it exists. If secure storage
        raises an error, falls back to clearing the TOML file only.

        Raises:
            ConfigurationError: If both secure storage and fallback clear fail.
        """
        secure_cleared = False
        try:
            await self._page.client_storage.remove_async(KEY_EMAIL)
            await self._page.client_storage.remove_async(KEY_APP_PASSWORD)
            secure_cleared = True
            logger.info("Credentials cleared from secure storage.")
        except Exception as e:
            logger.warning(
                "Secure storage clear failed, falling back to "
                "clearing credentials.toml: %s", e
            )

        # Always attempt to clear fallback file too
        try:
            self.clear_fallback()
        except Exception as fallback_err:
            if not secure_cleared:
                logger.error(
                    "Fallback clear also failed: %s", fallback_err
                )
                raise ConfigurationError(
                    f"Unable to clear credentials from secure storage or "
                    f"fallback file: {fallback_err}"
                ) from fallback_err
            # If secure storage was cleared successfully, just log warning
            logger.warning(
                "Could not clear fallback file: %s", fallback_err
            )

    def clear_fallback(self) -> None:
        """Remove the fallback credentials.toml file if it exists.

        Raises:
            OSError: If the file exists but cannot be deleted.
        """
        if FALLBACK_FILE.exists():
            FALLBACK_FILE.unlink()
            logger.info("Fallback credentials file removed: %s", FALLBACK_FILE)
        else:
            logger.debug("No fallback credentials file to remove.")

    async def has_credentials(self) -> bool:
        """Alias for is_configured(). Check if credentials are stored.

        Returns:
            True if both email and app_password are stored, False otherwise.
        """
        return await self.is_configured()

    async def is_configured(self) -> bool:
        """Check if credentials exist in storage or fallback file.

        Returns:
            True if both email and app_password are stored in either
            secure storage or the fallback file, False otherwise.
        """
        try:
            email = await self._page.client_storage.get_async(KEY_EMAIL)
            app_password = await self._page.client_storage.get_async(
                KEY_APP_PASSWORD
            )
            if bool(email) and bool(app_password):
                return True
        except Exception as e:
            logger.warning(
                "Could not check credential status in secure storage: %s", e
            )

        # Check fallback file
        try:
            fallback_creds = await self.load_fallback()
            return fallback_creds is not None
        except Exception:
            return False

    async def store_fallback(self, email: str, app_password: str) -> None:
        """Write credentials to ~/.certflow/credentials.toml in encoded form.

        SECURITY NOTE: The encoding here (base64 + XOR with a machine-derived
        salt) is obfuscation, NOT encryption — anyone with read access to the
        file and the machine can recover the App Password. This path is a
        last-resort fallback used only when the platform's native secure
        storage (Keychain / Keystore / DPAPI) is unavailable. The file is
        written with owner-only permissions where the OS supports it.

        Args:
            email: Gmail address to store.
            app_password: Gmail App Password (16 alphabetic characters).

        Raises:
            OSError: If the directory or file cannot be created/written.
        """
        logger.warning(
            "Storing Gmail credentials in the INSECURE fallback file %s "
            "(obfuscated, not encrypted). Platform secure storage was "
            "unavailable. Treat this file as sensitive.",
            FALLBACK_FILE,
        )

        FALLBACK_DIR.mkdir(parents=True, exist_ok=True)

        encoded_email = _encode_value(email)
        encoded_password = _encode_value(app_password)

        content = (
            "[email]\n"
            f'sender = "{encoded_email}"\n'
            f'app_password = "{encoded_password}"\n'
        )

        FALLBACK_FILE.write_text(content, encoding="utf-8")

        # Restrict to owner read/write only where the OS supports it (POSIX).
        try:
            os.chmod(FALLBACK_FILE, 0o600)
        except (OSError, NotImplementedError):
            # e.g. Windows without POSIX perms — best effort only.
            pass

        logger.info(
            "Credentials stored in fallback file: %s", FALLBACK_FILE
        )

    async def load_fallback(self) -> Optional[GmailCredentials]:
        """Read credentials from ~/.certflow/credentials.toml and decode.

        Returns:
            GmailCredentials if the fallback file exists and can be decoded,
            None if the file does not exist or is malformed.
        """
        if not FALLBACK_FILE.exists():
            return None

        try:
            content = FALLBACK_FILE.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Cannot read fallback file: %s", e)
            return None

        # Simple TOML parsing for our known format
        encoded_email = None
        encoded_password = None

        for line in content.splitlines():
            line = line.strip()
            if line.startswith("sender"):
                encoded_email = _extract_toml_value(line)
            elif line.startswith("app_password"):
                encoded_password = _extract_toml_value(line)

        if not encoded_email or not encoded_password:
            logger.warning("Fallback file is malformed or incomplete.")
            return None

        try:
            email = _decode_value(encoded_email)
            app_password = _decode_value(encoded_password)
        except Exception as e:
            logger.warning("Failed to decode fallback credentials: %s", e)
            return None

        return GmailCredentials(
            sender_email=email, app_password=app_password
        )

    def validate_email(self, email: str) -> Optional[str]:
        """Validate that email conforms to the pattern local-part@gmail.com.

        The email must:
        - Be at most 254 characters total.
        - End with exactly '@gmail.com' (case-sensitive).
        - Have at least one character in the local-part before '@gmail.com'.
        - The local-part may only contain alphanumeric characters, dots,
          underscores, hyphens, and plus signs.

        Args:
            email: The email address string to validate.

        Returns:
            An error message string if validation fails, None if the email
            is valid.
        """
        if not email:
            return "Email address is required."

        if len(email) > 254:
            return "Email address must not exceed 254 characters."

        suffix = "@gmail.com"
        if not email.endswith(suffix):
            return "Email must be a Gmail address (local-part@gmail.com)."

        local_part = email[: -len(suffix)]
        if len(local_part) < 1:
            return "Email must have a local-part before @gmail.com."

        if not _LOCAL_PART_PATTERN.match(local_part):
            return (
                "Email local-part may only contain alphanumeric characters, "
                "dots, underscores, hyphens, and plus signs."
            )

        return None

    def validate_app_password(self, raw: str) -> Optional[str]:
        """Validate that the app password is exactly 16 alphabetic characters.

        Spaces are stripped before validation. After stripping, the password
        must contain exactly 16 characters, all of which are alphabetic
        (a-z, A-Z).

        Args:
            raw: The raw app password string (may contain spaces).

        Returns:
            An error message string if validation fails, None if the
            password is valid.
        """
        if not raw:
            return "App password is required."

        stripped = raw.replace(" ", "")

        if not stripped.isalpha():
            return (
                "App password must contain only alphabetic characters "
                "(a-z, A-Z) after removing spaces."
            )

        if len(stripped) != 16:
            return (
                "App password must be exactly 16 alphabetic characters "
                f"(got {len(stripped)})."
            )

        return None
