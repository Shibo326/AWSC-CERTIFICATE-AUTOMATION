"""Shared test fixtures for CertFlow tests."""

import io
import os
import sys

import pytest
from PIL import Image

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.font_config import FontConfiguration
from utils.models import AttendeeRecord


@pytest.fixture
def sample_png_template() -> Image.Image:
    """Create an 800x600 white PNG image for testing."""
    return Image.new("RGB", (800, 600), "white")


@pytest.fixture
def sample_jpg_template() -> Image.Image:
    """Create an 800x600 white JPG image for testing."""
    return Image.new("RGB", (800, 600), "white")


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Create PNG template as bytes."""
    img = Image.new("RGB", (800, 600), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_jpg_bytes() -> bytes:
    """Create JPG template as bytes."""
    img = Image.new("RGB", (800, 600), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def default_font_config() -> FontConfiguration:
    """Default font configuration (Arial, 40pt, black)."""
    return FontConfiguration()


@pytest.fixture
def sample_attendees() -> list:
    """List of 5 sample attendee records."""
    return [
        AttendeeRecord(name="Juan Dela Cruz", email="juan@example.com"),
        AttendeeRecord(name="Maria Santos", email="maria@example.com"),
        AttendeeRecord(name="Jose Reyes", email="jose@example.com"),
        AttendeeRecord(name="Ana Rodriguez", email="ana@example.com"),
        AttendeeRecord(name="Pedro Fernandez", email="pedro@example.com"),
    ]


@pytest.fixture
def sample_csv_content() -> str:
    """Valid CSV string with name and email columns."""
    return (
        "name,email\n"
        "Juan Dela Cruz,juan@example.com\n"
        "Maria Santos,maria@example.com\n"
        "Jose Reyes,jose@example.com\n"
    )


@pytest.fixture
def sample_csv_with_errors() -> str:
    """CSV with various validation errors."""
    return (
        "name,email\n"
        "Juan Dela Cruz,juan@example.com\n"
        ",maria@example.com\n"
        "Jose Reyes,not-an-email\n"
        "Ana Rodriguez,\n"
    )


@pytest.fixture
def sample_csv_with_duplicates() -> str:
    """CSV with duplicate email entries."""
    return (
        "name,email\n"
        "Juan Dela Cruz,juan@example.com\n"
        "Maria Santos,maria@example.com\n"
        "Juan Copy,juan@example.com\n"
    )
