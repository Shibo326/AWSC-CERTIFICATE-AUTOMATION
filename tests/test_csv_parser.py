"""Unit tests for CSVParser."""

import pytest

from utils.csv_parser import CSVParser
from utils.models import AttendeeRecord


class TestCSVParserHeaders:
    """Tests for header validation."""

    def test_valid_headers_lowercase(self, sample_csv_content):
        parser = CSVParser()
        result = parser.parse(sample_csv_content)
        assert len(result.records) == 3

    def test_valid_headers_mixed_case(self):
        parser = CSVParser()
        csv = "Name,Email\nJuan,juan@example.com\n"
        result = parser.parse(csv)
        assert len(result.records) == 1

    def test_valid_headers_uppercase(self):
        parser = CSVParser()
        csv = "NAME,EMAIL\nJuan,juan@example.com\n"
        result = parser.parse(csv)
        assert len(result.records) == 1

    def test_missing_name_column(self):
        parser = CSVParser()
        with pytest.raises(ValueError, match="name"):
            parser.parse("email\njuan@example.com\n")

    def test_missing_email_column(self):
        parser = CSVParser()
        with pytest.raises(ValueError, match="email"):
            parser.parse("name\nJuan\n")

    def test_missing_both_columns(self):
        parser = CSVParser()
        with pytest.raises(ValueError, match="name.*email|email.*name"):
            parser.parse("id,phone\n1,123\n")

    def test_empty_file(self):
        parser = CSVParser()
        with pytest.raises(ValueError, match="empty"):
            parser.parse("")

    def test_extra_columns_ignored(self):
        parser = CSVParser()
        csv = "name,email,phone\nJuan,juan@example.com,123\n"
        result = parser.parse(csv)
        assert len(result.records) == 1
        assert result.records[0].name == "Juan"


class TestCSVParserRowValidation:
    """Tests for row-level validation."""

    def test_valid_row(self):
        parser = CSVParser()
        csv = "name,email\nJuan Dela Cruz,juan@example.com\n"
        result = parser.parse(csv)
        assert len(result.records) == 1
        assert result.records[0].name == "Juan Dela Cruz"
        assert result.records[0].email == "juan@example.com"

    def test_empty_name(self, sample_csv_with_errors):
        parser = CSVParser()
        result = parser.parse(sample_csv_with_errors)
        name_errors = [e for e in result.errors if e.field == "name"]
        assert len(name_errors) >= 1

    def test_empty_email(self, sample_csv_with_errors):
        parser = CSVParser()
        result = parser.parse(sample_csv_with_errors)
        email_errors = [
            e for e in result.errors
            if e.field == "email" and "required" in e.message
        ]
        assert len(email_errors) >= 1

    def test_invalid_email_format(self, sample_csv_with_errors):
        parser = CSVParser()
        result = parser.parse(sample_csv_with_errors)
        format_errors = [
            e for e in result.errors
            if e.field == "email" and "Invalid" in e.message
        ]
        assert len(format_errors) >= 1

    def test_whitespace_stripped(self):
        parser = CSVParser()
        csv = "name,email\n  Juan  , juan@example.com \n"
        result = parser.parse(csv)
        assert result.records[0].name == "Juan"
        assert result.records[0].email == "juan@example.com"

    def test_continues_after_error(self, sample_csv_with_errors):
        parser = CSVParser()
        result = parser.parse(sample_csv_with_errors)
        assert len(result.records) >= 1
        assert len(result.errors) >= 1

    def test_empty_data_rows_returns_empty(self):
        parser = CSVParser()
        csv = "name,email\n"
        result = parser.parse(csv)
        assert len(result.records) == 0
        assert len(result.errors) == 0


class TestCSVParserDuplicates:
    """Tests for duplicate email detection."""

    def test_duplicate_detected(self, sample_csv_with_duplicates):
        parser = CSVParser()
        result = parser.parse(sample_csv_with_duplicates)
        dup_errors = [e for e in result.errors if e.field == "duplicate"]
        assert len(dup_errors) == 1

    def test_first_occurrence_retained(self, sample_csv_with_duplicates):
        parser = CSVParser()
        result = parser.parse(sample_csv_with_duplicates)
        juan_records = [r for r in result.records if "juan" in r.email.lower()]
        assert len(juan_records) == 1
        assert juan_records[0].name == "Juan Dela Cruz"

    def test_case_insensitive_duplicate(self):
        parser = CSVParser()
        csv = "name,email\nJuan,JUAN@example.com\nCopy,juan@example.com\n"
        result = parser.parse(csv)
        dup_errors = [e for e in result.errors if e.field == "duplicate"]
        assert len(dup_errors) == 1


class TestCSVParserFormatRecords:
    """Tests for format_records round-trip."""

    def test_format_records_output(self):
        parser = CSVParser()
        records = [
            AttendeeRecord(name="Juan", email="juan@example.com"),
            AttendeeRecord(name="Maria", email="maria@example.com"),
        ]
        output = parser.format_records(records)
        assert "name,email" in output
        assert "Juan" in output
        assert "Maria" in output

    def test_round_trip_consistency(self, sample_csv_content):
        parser = CSVParser()
        result1 = parser.parse(sample_csv_content)
        formatted = parser.format_records(result1.records)
        result2 = parser.parse(formatted)
        assert len(result1.records) == len(result2.records)
        for r1, r2 in zip(result1.records, result2.records):
            assert r1.name == r2.name
            assert r1.email == r2.email

    def test_order_preserved(self):
        parser = CSVParser()
        records = [
            AttendeeRecord(name="C", email="c@example.com"),
            AttendeeRecord(name="A", email="a@example.com"),
            AttendeeRecord(name="B", email="b@example.com"),
        ]
        output = parser.format_records(records)
        result = parser.parse(output)
        assert result.records[0].name == "C"
        assert result.records[1].name == "A"
        assert result.records[2].name == "B"
