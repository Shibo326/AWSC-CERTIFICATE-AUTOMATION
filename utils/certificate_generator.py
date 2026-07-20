"""Certificate generation orchestrator for CertFlow."""

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Union

from PIL import Image

from utils.exceptions import TemplateLoadError
from utils.font_config import FontConfiguration
from utils.image_processor import ImageProcessor
from utils.models import BatchResult, CertificateOutput, GenerationError
from utils.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg"}
SUPPORTED_PDF_FORMATS = {".pdf"}
SUPPORTED_FORMATS = SUPPORTED_IMAGE_FORMATS | SUPPORTED_PDF_FORMATS


class CertificateGenerator:
    """Top-level orchestrator for certificate generation.

    Coordinates template loading, format detection, and delegates rendering
    to ImageProcessor (PNG/JPG) or PDFProcessor (PDF) based on template type.
    """

    def __init__(
        self,
        template_path: Optional[str] = None,
        template_bytes: Optional[bytes] = None,
        template_format: Optional[str] = None,
        font_config: Optional[FontConfiguration] = None,
    ) -> None:
        """Initialize with template and font configuration.

        Provide either template_path OR (template_bytes + template_format).

        Args:
            template_path: Path to the certificate template file.
            template_bytes: Raw bytes of the template (for uploaded files).
            template_format: Format when using template_bytes ('png', 'jpg', 'pdf').
            font_config: Font settings. Defaults to Arial 40pt black.

        Raises:
            FileNotFoundError: If template_path doesn't exist.
            TemplateLoadError: If template is corrupted or unsupported format.
        """
        self._font_config = font_config or FontConfiguration()
        self._format: str = ""
        self._image_processor: Optional[ImageProcessor] = None
        self._pdf_processor: Optional[PDFProcessor] = None
        self._template_path: Optional[str] = None
        self._temp_file: Optional[str] = None  # Track temp file for cleanup

        if template_path:
            self._load_from_path(template_path)
        elif template_bytes and template_format:
            self._load_from_bytes(template_bytes, template_format)
        else:
            raise ValueError(
                "Provide either template_path or (template_bytes + template_format)"
            )

    def _load_from_path(self, template_path: str) -> None:
        """Load template from file path.

        Args:
            template_path: Path to the template file.

        Raises:
            FileNotFoundError: If path doesn't exist.
            TemplateLoadError: If file is corrupted or unsupported.
        """
        path = Path(template_path)

        if not path.exists():
            raise FileNotFoundError(f"Template file not found: '{template_path}'")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise TemplateLoadError(
                f"Unsupported template format '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

        if ext in SUPPORTED_IMAGE_FORMATS:
            self._format = "png" if ext == ".png" else "jpg"
            try:
                template_image = Image.open(template_path)
                template_image.load()  # Force load to detect corruption
            except Exception as e:
                raise TemplateLoadError(
                    f"Cannot load image template '{template_path}': {e}"
                )

            w, h = template_image.size
            if w <= 0 or h <= 0:
                raise TemplateLoadError(
                    f"Invalid template dimensions: {w}x{h}"
                )

            self._image_processor = ImageProcessor(template_image, self._font_config)

        else:  # PDF
            self._format = "pdf"
            self._template_path = template_path
            self._pdf_processor = PDFProcessor(template_path, self._font_config)

    def _load_from_bytes(self, template_bytes: bytes, template_format: str) -> None:
        """Load template from raw bytes.

        Args:
            template_bytes: Raw file bytes.
            template_format: Format string ('png', 'jpg', 'pdf').

        Raises:
            TemplateLoadError: If bytes are corrupted or format unsupported.
        """
        fmt = template_format.lower().lstrip(".")
        if fmt == "jpeg":
            fmt = "jpg"

        if fmt in ("png", "jpg"):
            self._format = fmt
            try:
                template_image = Image.open(io.BytesIO(template_bytes))
                template_image.load()
            except Exception as e:
                raise TemplateLoadError(
                    f"Cannot load image template from bytes: {e}"
                )

            w, h = template_image.size
            if w <= 0 or h <= 0:
                raise TemplateLoadError(
                    f"Invalid template dimensions: {w}x{h}"
                )

            self._image_processor = ImageProcessor(template_image, self._font_config)

        elif fmt == "pdf":
            self._format = "pdf"
            # Write bytes to temp location for PyMuPDF
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(template_bytes)
            tmp.close()
            self._template_path = tmp.name
            self._temp_file = tmp.name  # Track for cleanup
            self._pdf_processor = PDFProcessor(tmp.name, self._font_config)

        else:
            raise TemplateLoadError(
                f"Unsupported template format '{fmt}'. Supported: png, jpg, pdf"
            )

    @property
    def format(self) -> str:
        """Output format matching input template format."""
        return self._format

    def cleanup(self) -> None:
        """Remove temporary files created during initialization."""
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                os.unlink(self._temp_file)
            except OSError:
                pass
            self._temp_file = None

    def __del__(self) -> None:
        """Clean up temp files on garbage collection."""
        self.cleanup()

    def generate(
        self,
        attendee_name: str,
        vertical_position: Optional[Union[int, float]] = None,
        vertical_as_percentage: bool = False,
    ) -> CertificateOutput:
        """Generate a single certificate for one attendee.

        Args:
            attendee_name: Name to render on the certificate.
            vertical_position: Optional Y position override.
            vertical_as_percentage: If True, position is 0-100 percentage.

        Returns:
            CertificateOutput with the generated certificate.

        Raises:
            TextOverflowError: If name doesn't fit on template.
        """
        if self._image_processor:
            image = self._image_processor.render_name(
                attendee_name, vertical_position, vertical_as_percentage
            )
            return CertificateOutput(
                attendee_name=attendee_name,
                certificate=image,
                format=self._format,
            )
        else:
            pdf_bytes = self._pdf_processor.render_name(
                attendee_name, vertical_position, vertical_as_percentage
            )
            return CertificateOutput(
                attendee_name=attendee_name,
                certificate=pdf_bytes,
                format=self._format,
            )

    def generate_batch(
        self,
        attendee_names: List[str],
        vertical_position: Optional[Union[int, float]] = None,
        vertical_as_percentage: bool = False,
    ) -> BatchResult:
        """Generate certificates for all attendees, collecting errors gracefully.

        Args:
            attendee_names: List of names to generate certificates for.
            vertical_position: Optional Y position override for all certificates.
            vertical_as_percentage: If True, position is 0-100 percentage.

        Returns:
            BatchResult containing successful outputs and error details.
        """
        result = BatchResult()

        for name in attendee_names:
            try:
                cert = self.generate(name, vertical_position, vertical_as_percentage)
                result.certificates.append(cert)
            except Exception as e:
                logger.warning(f"Failed to generate certificate for '{name}': {e}")
                result.errors.append(
                    GenerationError(attendee_name=name, error_message=str(e))
                )

        return result
