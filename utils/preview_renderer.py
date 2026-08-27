"""Shared certificate preview rendering for CertFlow.

Centralizes the logic that all UIs (Streamlit ``app.py`` and the Flet
``parts/*`` components) use to turn a generated certificate into a small,
display-ready PNG. Previously this PIL/PyMuPDF -> PNG dance was duplicated
in three places, each rendering the full-resolution image on every change.

This module:
    * Downscales previews to a maximum width (default 800px) so a 3000px
      template is not rasterized/encoded at full size just to be shown small.
    * Caches encoded previews by a cheap content key so repeated renders
      (e.g. dragging a slider back, navigating Prev/Next) are instant.
    * Provides a single ``CertificateOutput`` -> PNG bytes entry point plus a
      base64 helper for Flet's ``ft.Image``.
"""

import base64
import hashlib
import io
import logging
from functools import lru_cache
from typing import Union

from PIL import Image

logger = logging.getLogger(__name__)

# Maximum preview width in pixels. Full resolution is only needed at
# generation/download time, never for on-screen preview.
PREVIEW_MAX_WIDTH = 800


def _downscale(img: Image.Image, max_width: int = PREVIEW_MAX_WIDTH) -> Image.Image:
    """Return a copy of ``img`` scaled down so its width <= ``max_width``.

    Images already narrower than ``max_width`` are returned unchanged. Aspect
    ratio is always preserved.

    Args:
        img: Source PIL image.
        max_width: Maximum allowed width in pixels.

    Returns:
        A downscaled copy, or the original image if no scaling is needed.
    """
    width, height = img.size
    if width <= max_width:
        return img
    ratio = max_width / float(width)
    new_size = (max_width, max(1, int(height * ratio)))
    return img.resize(new_size, Image.LANCZOS)


def _image_to_preview_png(img: Image.Image, max_width: int) -> bytes:
    """Downscale a PIL image and encode it as PNG bytes."""
    scaled = _downscale(img, max_width)
    # Flatten unusual modes onto a predictable RGB(A) surface for preview.
    if scaled.mode not in ("RGB", "RGBA"):
        scaled = scaled.convert("RGB")
    buffer = io.BytesIO()
    scaled.save(buffer, format="PNG")
    return buffer.getvalue()


def _pdf_to_preview_png(pdf_bytes: bytes, max_width: int) -> bytes:
    """Rasterize the first page of a PDF and encode it as a downscaled PNG.

    Raises:
        RuntimeError: If PyMuPDF is unavailable or the PDF cannot be rendered.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PyMuPDF is required for PDF previews") from exc

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.page_count == 0:
            raise RuntimeError("PDF has no pages to preview")
        page = doc.load_page(0)
        # Choose a zoom factor that lands near max_width without oversampling.
        page_width = page.rect.width or max_width
        zoom = min(2.0, max(0.5, max_width / float(page_width)))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        png_bytes = pix.tobytes("png")
    finally:
        doc.close()

    # Re-open through PIL to enforce the max width exactly (and shrink further
    # if the zoom clamp left it too wide).
    img = Image.open(io.BytesIO(png_bytes))
    return _image_to_preview_png(img, max_width)


@lru_cache(maxsize=128)
def _cached_bytes_preview(
    kind: str, digest: str, raw: bytes, max_width: int
) -> bytes:
    """Cache preview PNG bytes keyed by content digest.

    ``digest`` is what actually drives the cache identity; ``raw`` carries the
    real bytes so they are available on a cache miss. ``kind`` is ``"image"``
    or ``"pdf"``.
    """
    if kind == "pdf":
        return _pdf_to_preview_png(raw, max_width)
    img = Image.open(io.BytesIO(raw))
    return _image_to_preview_png(img, max_width)


def render_preview_png(
    certificate: Union[Image.Image, bytes],
    fmt: str,
    max_width: int = PREVIEW_MAX_WIDTH,
) -> bytes:
    """Render a certificate into downscaled, display-ready PNG bytes.

    This is the single entry point every UI should use for certificate
    previews. Results are cached by content so repeated calls with the same
    certificate are effectively free.

    Args:
        certificate: A PIL ``Image`` (PNG/JPG certificates) or raw ``bytes``
            (PDF certificates).
        fmt: The certificate format: ``"png"``, ``"jpg"``, or ``"pdf"``.
        max_width: Maximum preview width in pixels.

    Returns:
        PNG-encoded preview bytes.

    Raises:
        RuntimeError: If a PDF cannot be rendered.
        ValueError: If the format/certificate combination is unsupported.
    """
    fmt = fmt.lower().lstrip(".")

    if isinstance(certificate, Image.Image):
        # Encode once, then cache by a digest of the encoded bytes.
        png_source = io.BytesIO()
        save_format = "PNG" if fmt != "jpg" else "JPEG"
        certificate.save(png_source, format=save_format)
        raw = png_source.getvalue()
        digest = hashlib.sha1(raw).hexdigest()
        return _cached_bytes_preview("image", digest, raw, max_width)

    if isinstance(certificate, (bytes, bytearray)):
        raw = bytes(certificate)
        digest = hashlib.sha1(raw).hexdigest()
        kind = "pdf" if fmt == "pdf" else "image"
        return _cached_bytes_preview(kind, digest, raw, max_width)

    raise ValueError(
        f"Unsupported certificate type {type(certificate)!r} for format {fmt!r}"
    )


def render_preview_base64(
    certificate: Union[Image.Image, bytes],
    fmt: str,
    max_width: int = PREVIEW_MAX_WIDTH,
) -> str:
    """Render a certificate preview and return it as a base64 string.

    Convenience wrapper for Flet's ``ft.Image(src=...)`` which expects a
    base64-encoded string.

    Args:
        certificate: PIL image or PDF bytes.
        fmt: Certificate format (``"png"``, ``"jpg"``, ``"pdf"``).
        max_width: Maximum preview width in pixels.

    Returns:
        Base64-encoded PNG string, or an empty string on failure.
    """
    try:
        png_bytes = render_preview_png(certificate, fmt, max_width)
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning("Preview render failed: %s", exc)
        return ""
    return base64.b64encode(png_bytes).decode("ascii")


def clear_cache() -> None:
    """Clear the preview cache. Useful in tests."""
    _cached_bytes_preview.cache_clear()
