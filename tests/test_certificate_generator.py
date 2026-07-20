"""Unit tests for CertificateGenerator."""

import pytest
from PIL import Image

from utils.certificate_generator import CertificateGenerator
from utils.exceptions import TemplateLoadError
from utils.font_config import FontConfiguration
from utils.models import BatchResult, CertificateOutput


class TestCertificateGeneratorInit:
    """Tests for initialization and template loading."""

    def test_init_from_bytes_png(self, sample_png_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_png_bytes, template_format="png"
        )
        assert gen.format == "png"

    def test_init_from_bytes_jpg(self, sample_jpg_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_jpg_bytes, template_format="jpg"
        )
        assert gen.format == "jpg"

    def test_init_unsupported_format(self, sample_png_bytes):
        with pytest.raises(TemplateLoadError, match="Unsupported"):
            CertificateGenerator(
                template_bytes=sample_png_bytes, template_format="bmp"
            )

    def test_init_corrupted_bytes(self):
        with pytest.raises(TemplateLoadError):
            CertificateGenerator(
                template_bytes=b"not an image", template_format="png"
            )

    def test_init_missing_path(self):
        with pytest.raises(FileNotFoundError):
            CertificateGenerator(template_path="nonexistent.png")

    def test_init_no_args(self):
        with pytest.raises(ValueError):
            CertificateGenerator()


class TestCertificateGeneratorGenerate:
    """Tests for single certificate generation."""

    def test_generate_returns_certificate_output(self, sample_png_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_png_bytes, template_format="png"
        )
        result = gen.generate("Juan Dela Cruz")
        assert isinstance(result, CertificateOutput)
        assert result.attendee_name == "Juan Dela Cruz"
        assert result.format == "png"

    def test_generate_png_returns_image(self, sample_png_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_png_bytes, template_format="png"
        )
        result = gen.generate("Test Name")
        assert isinstance(result.certificate, Image.Image)

    def test_generate_preserves_format(self, sample_jpg_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_jpg_bytes, template_format="jpg"
        )
        result = gen.generate("Test Name")
        assert result.format == "jpg"

    def test_generate_with_vertical_position(self, sample_png_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_png_bytes, template_format="png"
        )
        result = gen.generate(
            "Test", vertical_position=30, vertical_as_percentage=True
        )
        assert isinstance(result, CertificateOutput)


class TestCertificateGeneratorBatch:
    """Tests for batch certificate generation."""

    def test_batch_generates_all(self, sample_png_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_png_bytes, template_format="png"
        )
        names = ["Alice", "Bob", "Charlie"]
        result = gen.generate_batch(names)
        assert isinstance(result, BatchResult)
        assert len(result.certificates) == 3
        assert len(result.errors) == 0

    def test_batch_empty_list(self, sample_png_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_png_bytes, template_format="png"
        )
        result = gen.generate_batch([])
        assert len(result.certificates) == 0
        assert len(result.errors) == 0

    def test_batch_preserves_order(self, sample_png_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_png_bytes, template_format="png"
        )
        names = ["Zara", "Alice", "Mike"]
        result = gen.generate_batch(names)
        assert result.certificates[0].attendee_name == "Zara"
        assert result.certificates[1].attendee_name == "Alice"
        assert result.certificates[2].attendee_name == "Mike"

    def test_batch_count_invariant(self, sample_png_bytes):
        gen = CertificateGenerator(
            template_bytes=sample_png_bytes, template_format="png"
        )
        names = ["A", "B", "C", "D", "E"]
        result = gen.generate_batch(names)
        assert (
            len(result.certificates) + len(result.errors) == len(names)
        )
