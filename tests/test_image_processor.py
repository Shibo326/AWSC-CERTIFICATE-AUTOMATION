"""Unit tests for ImageProcessor."""

import pytest
from PIL import Image

from utils.exceptions import FontLoadError, TextOverflowError
from utils.font_config import FontConfiguration
from utils.image_processor import ImageProcessor


class TestImageProcessorInit:
    """Tests for initialization and font loading."""

    def test_init_with_valid_font(self, sample_png_template, default_font_config):
        processor = ImageProcessor(sample_png_template, default_font_config)
        assert processor is not None

    def test_init_with_missing_font(self, sample_png_template):
        config = FontConfiguration(font_path="nonexistent/font.ttf")
        with pytest.raises(FontLoadError):
            ImageProcessor(sample_png_template, config)


class TestImageProcessorPositioning:
    """Tests for text position calculation."""

    def test_horizontal_centering(self, sample_png_template, default_font_config):
        processor = ImageProcessor(sample_png_template, default_font_config)
        x, y = processor.calculate_text_position("Test")
        template_width = sample_png_template.size[0]
        assert 0 < x < template_width

    def test_vertical_default_center(self, sample_png_template, default_font_config):
        processor = ImageProcessor(sample_png_template, default_font_config)
        x, y = processor.calculate_text_position("Test")
        template_height = sample_png_template.size[1]
        assert template_height * 0.3 < y < template_height * 0.7

    def test_vertical_pixel_position(self, sample_png_template, default_font_config):
        processor = ImageProcessor(sample_png_template, default_font_config)
        x, y = processor.calculate_text_position("Test", vertical_position=100)
        assert y == 100

    def test_vertical_percentage_position(
        self, sample_png_template, default_font_config
    ):
        processor = ImageProcessor(sample_png_template, default_font_config)
        x, y = processor.calculate_text_position(
            "Test", vertical_position=25, vertical_as_percentage=True
        )
        template_height = sample_png_template.size[1]
        expected_approx = int(0.25 * template_height)
        assert abs(y - expected_approx) < 50

    def test_overflow_raises_error(self, default_font_config):
        tiny = Image.new("RGB", (50, 50), "white")
        processor = ImageProcessor(tiny, default_font_config)
        with pytest.raises(TextOverflowError):
            processor.calculate_text_position(
                "This is a very long name that won't fit"
            )


class TestImageProcessorRendering:
    """Tests for name rendering."""

    def test_render_returns_image(self, sample_png_template, default_font_config):
        processor = ImageProcessor(sample_png_template, default_font_config)
        result = processor.render_name("Juan Dela Cruz")
        assert isinstance(result, Image.Image)

    def test_render_preserves_dimensions(
        self, sample_png_template, default_font_config
    ):
        processor = ImageProcessor(sample_png_template, default_font_config)
        result = processor.render_name("Test Name")
        assert result.size == sample_png_template.size

    def test_render_does_not_modify_original(
        self, sample_png_template, default_font_config
    ):
        processor = ImageProcessor(sample_png_template, default_font_config)
        original_data = list(sample_png_template.getdata())
        processor.render_name("Test Name")
        after_data = list(sample_png_template.getdata())
        assert original_data == after_data

    def test_render_changes_pixels(self, sample_png_template, default_font_config):
        processor = ImageProcessor(sample_png_template, default_font_config)
        result = processor.render_name("Test Name")
        result_data = list(result.getdata())
        template_data = list(sample_png_template.getdata())
        assert result_data != template_data

    def test_render_with_custom_color(self, sample_png_template):
        config = FontConfiguration(font_color=(255, 0, 0))
        processor = ImageProcessor(sample_png_template, config)
        result = processor.render_name("Red Text")
        assert isinstance(result, Image.Image)

    def test_render_idempotent(self, sample_png_template, default_font_config):
        processor = ImageProcessor(sample_png_template, default_font_config)
        result1 = processor.render_name("Same Name")
        result2 = processor.render_name("Same Name")
        assert list(result1.getdata()) == list(result2.getdata())
