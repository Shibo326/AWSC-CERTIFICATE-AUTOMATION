"""Property-based tests for credential validation.

# Feature: offline-cross-platform-app, Property 6: Credential validation correctness
"""

import re
import string

from hypothesis import given, settings, strategies as st
from unittest.mock import MagicMock

from utils.credential_store import CredentialStore


# Pattern matching the implementation's local-part validation
_LOCAL_PART_RE = re.compile(r"^[a-zA-Z0-9._\-+]+$")


def _is_valid_gmail(email: str) -> bool:
    """Reference implementation: email is valid iff matches local-part@gmail.com."""
    if not email:
        return False
    if len(email) > 254:
        return False
    suffix = "@gmail.com"
    if not email.endswith(suffix):
        return False
    local_part = email[: -len(suffix)]
    if len(local_part) < 1:
        return False
    if not _LOCAL_PART_RE.match(local_part):
        return False
    return True


def _is_valid_app_password(raw: str) -> bool:
    """Reference implementation: valid iff exactly 16 alpha chars after stripping spaces."""
    if not raw:
        return False
    stripped = raw.replace(" ", "")
    if not stripped.isalpha():
        return False
    if len(stripped) != 16:
        return False
    return True


# Strategy for generating valid Gmail local-part characters
_local_part_chars = st.sampled_from(
    string.ascii_letters + string.digits + "._-+"
)


# Strategy that generates valid Gmail addresses
_valid_gmail_strategy = st.builds(
    lambda local, domain: local + domain,
    local=st.text(alphabet=_local_part_chars, min_size=1, max_size=50),
    domain=st.just("@gmail.com"),
)

# Strategy that generates valid app passwords (16 alpha + optional spaces)
_valid_password_strategy = st.builds(
    lambda chars, spaces: "".join(
        c + (" " if i in spaces else "")
        for i, c in enumerate(chars)
    ),
    chars=st.text(
        alphabet=st.sampled_from(string.ascii_letters),
        min_size=16,
        max_size=16,
    ),
    spaces=st.frozensets(st.integers(min_value=0, max_value=15), max_size=4),
)


class TestProperty6EmailValidation:
    """Property 6: For any string as email, validator accepts iff matches
    local-part@gmail.com (alphanumeric/dots/underscores/hyphens/plus,
    max 254 chars).

    **Validates: Requirements 3.6**
    """

    @staticmethod
    def _get_store() -> CredentialStore:
        """Create a CredentialStore with a mock page."""
        page = MagicMock()
        page.client_storage = MagicMock()
        return CredentialStore(page)

    @given(email=st.text(min_size=0, max_size=300))
    @settings(max_examples=100)
    def test_arbitrary_string_email_validation(self, email: str) -> None:
        """For any arbitrary string, validate_email matches reference impl."""
        # Feature: offline-cross-platform-app, Property 6: Credential validation correctness
        store = self._get_store()
        result = store.validate_email(email)
        expected_valid = _is_valid_gmail(email)

        if expected_valid:
            assert result is None, (
                f"Expected valid but got error: '{result}' for email '{email}'"
            )
        else:
            assert result is not None, (
                f"Expected invalid but got None for email '{email}'"
            )

    @given(email=_valid_gmail_strategy)
    @settings(max_examples=100)
    def test_valid_gmail_addresses_accepted(self, email: str) -> None:
        """All properly formed Gmail addresses are accepted."""
        # Feature: offline-cross-platform-app, Property 6: Credential validation correctness
        store = self._get_store()
        if len(email) <= 254:
            result = store.validate_email(email)
            assert result is None, (
                f"Valid email '{email}' rejected with: '{result}'"
            )

    @given(
        local=st.text(min_size=1, max_size=50),
        domain=st.text(min_size=1, max_size=30).filter(
            lambda d: d != "gmail.com"
        ),
    )
    @settings(max_examples=100)
    def test_non_gmail_domains_rejected(self, local: str, domain: str) -> None:
        """Emails not ending with @gmail.com are always rejected."""
        # Feature: offline-cross-platform-app, Property 6: Credential validation correctness
        store = self._get_store()
        email = f"{local}@{domain}"
        result = store.validate_email(email)
        assert result is not None, (
            f"Non-gmail email '{email}' was incorrectly accepted"
        )


class TestProperty6PasswordValidation:
    """Property 6: For any string as password, validator accepts iff exactly
    16 alpha chars after stripping spaces.

    **Validates: Requirements 3.6**
    """

    @staticmethod
    def _get_store() -> CredentialStore:
        """Create a CredentialStore with a mock page."""
        page = MagicMock()
        page.client_storage = MagicMock()
        return CredentialStore(page)

    @given(raw=st.text(min_size=0, max_size=100))
    @settings(max_examples=100)
    def test_arbitrary_string_password_validation(self, raw: str) -> None:
        """For any arbitrary string, validate_app_password matches reference."""
        # Feature: offline-cross-platform-app, Property 6: Credential validation correctness
        store = self._get_store()
        result = store.validate_app_password(raw)
        expected_valid = _is_valid_app_password(raw)

        if expected_valid:
            assert result is None, (
                f"Expected valid but got error: '{result}' for password '{raw}'"
            )
        else:
            assert result is not None, (
                f"Expected invalid but got None for password '{raw}'"
            )

    @given(password=_valid_password_strategy)
    @settings(max_examples=100)
    def test_valid_passwords_accepted(self, password: str) -> None:
        """All properly formed 16-alpha-char passwords are accepted."""
        # Feature: offline-cross-platform-app, Property 6: Credential validation correctness
        store = self._get_store()
        result = store.validate_app_password(password)
        assert result is None, (
            f"Valid password '{password}' rejected with: '{result}'"
        )

    @given(
        chars=st.text(
            alphabet=st.sampled_from(string.ascii_letters),
            min_size=1,
            max_size=100,
        ).filter(lambda s: len(s) != 16)
    )
    @settings(max_examples=100)
    def test_wrong_length_passwords_rejected(self, chars: str) -> None:
        """Passwords with != 16 alpha chars (no spaces) are rejected."""
        # Feature: offline-cross-platform-app, Property 6: Credential validation correctness
        store = self._get_store()
        result = store.validate_app_password(chars)
        assert result is not None, (
            f"Password with {len(chars)} chars was incorrectly accepted"
        )
