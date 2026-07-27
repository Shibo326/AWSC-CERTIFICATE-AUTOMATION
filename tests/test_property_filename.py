"""Property-based tests for filename sanitization and deduplication.

# Feature: offline-cross-platform-app, Property 4: Filename sanitization correctness
# Feature: offline-cross-platform-app, Property 5: Filename deduplication guarantees uniqueness
"""

import re

from hypothesis import given, settings, strategies as st

from utils.platform_storage import PlatformStorage


# Valid file extensions used in CertFlow
VALID_EXTENSIONS = [".png", ".jpg", ".pdf"]

storage = PlatformStorage()


class TestProperty4FilenameSanitization:
    """Property 4: For any Unicode string name and valid extension,
    sanitized filename contains only [a-zA-Z0-9_], base <= 200 chars,
    ends with correct extension.

    **Validates: Requirements 2.6**
    """

    @given(
        name=st.text(),
        extension=st.sampled_from(VALID_EXTENSIONS),
    )
    @settings(max_examples=100)
    def test_sanitized_contains_only_valid_chars(
        self, name: str, extension: str
    ) -> None:
        """Base name contains only alphanumeric and underscore characters."""
        # Feature: offline-cross-platform-app, Property 4: Filename sanitization correctness
        result = storage.sanitize_filename(name, extension)
        base = result[: -len(extension)]
        assert re.fullmatch(r"[a-zA-Z0-9_]*", base), (
            f"Base '{base}' contains invalid characters for input '{name!r}'"
        )

    @given(
        name=st.text(),
        extension=st.sampled_from(VALID_EXTENSIONS),
    )
    @settings(max_examples=100)
    def test_base_name_at_most_200_chars(
        self, name: str, extension: str
    ) -> None:
        """Base name (before extension) is at most 200 characters."""
        # Feature: offline-cross-platform-app, Property 4: Filename sanitization correctness
        result = storage.sanitize_filename(name, extension)
        base = result[: -len(extension)]
        assert len(base) <= 200, (
            f"Base length {len(base)} exceeds 200 for input '{name!r}'"
        )

    @given(
        name=st.text(),
        extension=st.sampled_from(VALID_EXTENSIONS),
    )
    @settings(max_examples=100)
    def test_ends_with_correct_extension(
        self, name: str, extension: str
    ) -> None:
        """Sanitized filename ends with the provided extension."""
        # Feature: offline-cross-platform-app, Property 4: Filename sanitization correctness
        result = storage.sanitize_filename(name, extension)
        assert result.endswith(extension), (
            f"Result '{result}' does not end with '{extension}'"
        )


class TestProperty5FilenameDeduplication:
    """Property 5: For any list of names (with duplicates), all
    deduplicated filenames are unique.

    **Validates: Requirements 2.7**
    """

    @given(
        names=st.lists(st.text(min_size=1), min_size=1, max_size=50),
        extension=st.sampled_from(VALID_EXTENSIONS),
    )
    @settings(max_examples=100)
    def test_all_filenames_unique_after_deduplication(
        self, names: list, extension: str
    ) -> None:
        """After sanitization and deduplication, all filenames are unique."""
        # Feature: offline-cross-platform-app, Property 5: Filename deduplication guarantees uniqueness
        seen: set = set()
        results: list = []

        for name in names:
            sanitized = storage.sanitize_filename(name, extension)
            deduped = storage.deduplicate_filename(sanitized, seen)
            results.append(deduped)
            seen.add(deduped)

        assert len(results) == len(set(results)), (
            f"Duplicates found in results: {results}"
        )
        assert len(results) == len(names)

    @given(
        names=st.lists(st.just("Same Name"), min_size=2, max_size=20),
        extension=st.sampled_from(VALID_EXTENSIONS),
    )
    @settings(max_examples=100)
    def test_identical_names_produce_unique_filenames(
        self, names: list, extension: str
    ) -> None:
        """Even identical names produce unique filenames after deduplication."""
        # Feature: offline-cross-platform-app, Property 5: Filename deduplication guarantees uniqueness
        seen: set = set()
        results: list = []

        for name in names:
            sanitized = storage.sanitize_filename(name, extension)
            deduped = storage.deduplicate_filename(sanitized, seen)
            results.append(deduped)
            seen.add(deduped)

        assert len(results) == len(set(results))
        assert len(results) == len(names)
