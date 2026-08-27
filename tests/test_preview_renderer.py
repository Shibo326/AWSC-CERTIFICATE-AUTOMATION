"""Tests for the shared certificate preview renderer."""

import base64
import io

import pytest
from PIL import Image

from utils import preview_renderer
from utils.preview_renderer import (
    PREVIEW_MAX_WIDTH,
    render_preview_base64,
    render_preview_png,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure each test starts with a clean preview cache."""
    preview_renderer.clear_cache()
    yield
    preview_renderer.clear_cache()


def _decode_png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_small_image_is_not_upscaled():
    img = Image.new("RGB", (400, 300), color="white")
    out = render_preview_png(img, "png")
    result = _decode_png(out)
    assert result.size == (400, 300)


def test_large_image_is_downscaled_to_max_width():
    img = Image.new("RGB", (3000, 1500), color="white")
    out = render_preview_png(img, "png")
    result = _decode_png(out)
    assert result.width == PREVIEW_MAX_WIDTH
    # Aspect ratio preserved (3000x1500 -> 800x400).
    assert result.height == 400


def test_downscale_preserves_aspect_ratio_odd_sizes():
    img = Image.new("RGB", (1601, 900), color="white")
    out = render_preview_png(img, "png")
    result = _decode_png(out)
    assert result.width == PREVIEW_MAX_WIDTH
    assert result.height == pytest.approx(900 * (800 / 1601), abs=1)


def test_custom_max_width_is_respected():
    img = Image.new("RGB", (2000, 1000), color="white")
    out = render_preview_png(img, "png", max_width=500)
    result = _decode_png(out)
    assert result.width == 500
    assert result.height == 250


def test_output_is_valid_png_regardless_of_input_format():
    img = Image.new("RGB", (1000, 1000), color="red")
    out = render_preview_png(img, "jpg")
    result = _decode_png(out)
    assert result.format == "PNG"


def test_rgba_image_is_handled():
    img = Image.new("RGBA", (900, 600), color=(0, 0, 0, 0))
    out = render_preview_png(img, "png")
    result = _decode_png(out)
    assert result.width == PREVIEW_MAX_WIDTH


def test_base64_wrapper_returns_decodable_png():
    img = Image.new("RGB", (1200, 600), color="blue")
    encoded = render_preview_base64(img, "png")
    assert encoded  # non-empty
    raw = base64.b64decode(encoded)
    result = _decode_png(raw)
    assert result.format == "PNG"


def test_cache_returns_identical_bytes_for_same_image():
    img = Image.new("RGB", (2000, 1000), color="green")
    first = render_preview_png(img, "png")
    second = render_preview_png(img, "png")
    assert first == second


def test_cache_hit_avoids_recompute():
    img = Image.new("RGB", (2000, 1000), color="green")
    render_preview_png(img, "png")
    info_before = preview_renderer._cached_bytes_preview.cache_info()
    render_preview_png(img, "png")
    info_after = preview_renderer._cached_bytes_preview.cache_info()
    assert info_after.hits == info_before.hits + 1


def test_unsupported_certificate_type_raises():
    with pytest.raises(ValueError):
        render_preview_png(12345, "png")  # type: ignore[arg-type]


def test_base64_returns_empty_on_bad_pdf_bytes():
    # Not a real PDF; should be caught and return empty string.
    encoded = render_preview_base64(b"not a pdf", "pdf")
    assert encoded == ""
