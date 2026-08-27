"""Tests for attendee name sanitization in the CSV parser."""

from utils.csv_parser import CSVParser, sanitize_name


def test_sanitize_removes_control_characters():
    assert sanitize_name("John\x00Doe") == "JohnDoe"
    assert sanitize_name("A\x1fB") == "AB"


def test_sanitize_collapses_whitespace_and_newlines():
    assert sanitize_name("John   Doe") == "John Doe"
    assert sanitize_name("John\nDoe") == "John Doe"
    assert sanitize_name("John\t Doe") == "John Doe"


def test_sanitize_strips_surrounding_whitespace():
    assert sanitize_name("  John Doe  ") == "John Doe"


def test_sanitize_preserves_normal_names_and_unicode():
    assert sanitize_name("José Álvarez") == "José Álvarez"
    assert sanitize_name("Mary-Jane O'Neil") == "Mary-Jane O'Neil"


def test_parser_sanitizes_name_with_embedded_newline():
    csv_content = "name,email\n" "\"Evil\nInjection\",evil@example.com\n"
    result = CSVParser().parse(csv_content)
    assert len(result.records) == 1
    assert "\n" not in result.records[0].name
    assert result.records[0].name == "Evil Injection"
