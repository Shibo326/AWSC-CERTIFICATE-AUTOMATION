"""PDF processor for certificate name overlay using ReportLab and PyMuPDF."""

import io
import uuid
from typing import Optional, Tuple, Union

import fitz  # PyMuPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from utils.exceptions import FontLoadError, TemplateLoadError, TextOverflowError
from utils.font_config import FontConfiguration


class PDFProcessor:
    """Handles rendering attendee names onto PDF certificate templates.

    Uses PyMuPDF for reading PDFs and ReportLab for creating text overlays.
    The original template file is never modified — a new PDF is produced each time.
    """

    def __init__(self, template_path: str, font_config: FontConfiguration) -> None:
        """Initialize with PDF template path and font settings.

        Args:
            template_path: Path to the PDF template file.
            font_config: Font configuration (path, size, color).

        Raises:
            TemplateLoadError: If the PDF cannot be opened or is corrupted.
            FontLoadError: If the font file cannot be registered.
        """
        self._template_path = template_path
        self._font_config = font_config
        self._font_name = f"CertFlow_{uuid.uuid4().hex[:8]}"

        # Validate PDF template
        try:
            doc = fitz.open(template_path)
            if doc.page_count == 0:
                raise TemplateLoadError(
                    f"PDF template '{template_path}' has no pages"
                )
            page = doc.load_page(0)
            rect = page.rect
            self._page_width = rect.width
            self._page_height = rect.height
            doc.close()
        except fitz.FileDataError as e:
            raise TemplateLoadError(
                f"PDF template '{template_path}' is corrupted: {e}"
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"PDF template not found: '{template_path}'"
            )

        # Validate and register font
        try:
            pdfmetrics.registerFont(
                TTFont(self._font_name, font_config.font_path)
            )
        except Exception as e:
            raise FontLoadError(
                f"Cannot load font at '{font_config.font_path}': {e}"
            )

    def calculate_text_position(
        self,
        text: str,
        vertical_position: Optional[Union[int, float]] = None,
        vertical_as_percentage: bool = False,
    ) -> Tuple[float, float]:
        """Calculate (x, y) coordinates for centered text on PDF page.

        Note: PDF coordinate system has origin at bottom-left.

        Args:
            text: The text to render (attendee name).
            vertical_position: Y position override (from top). If None, uses center.
            vertical_as_percentage: If True, vertical_position is 0-100 percentage.

        Returns:
            Tuple of (x, y) coordinates in PDF points (origin bottom-left).

        Raises:
            TextOverflowError: If text dimensions exceed page bounds.
        """
        text_width = pdfmetrics.stringWidth(
            text, self._font_name, self._font_config.font_size
        )
        text_height = self._font_config.font_size  # Approximate

        # Horizontal center
        x = (self._page_width - text_width) / 2

        # Vertical position (convert from top-origin to bottom-origin)
        if vertical_position is None:
            # Center vertically
            y = (self._page_height - text_height) / 2
        elif vertical_as_percentage:
            # Percentage from top
            from_top = (vertical_position / 100) * self._page_height
            y = self._page_height - from_top - text_height / 2
        else:
            # Pixel from top → convert to bottom-origin
            y = self._page_height - vertical_position - text_height

        # Overflow check
        if x < 0 or x + text_width > self._page_width:
            raise TextOverflowError(
                f"Text width ({text_width:.1f}pt) exceeds page width "
                f"({self._page_width:.1f}pt)"
            )
        if y < 0 or y + text_height > self._page_height:
            raise TextOverflowError(
                f"Text at y={y:.1f} with height {text_height:.1f}pt exceeds "
                f"page height ({self._page_height:.1f}pt)"
            )

        return (x, y)

    def render_name(
        self,
        attendee_name: str,
        vertical_position: Optional[Union[int, float]] = None,
        vertical_as_percentage: bool = False,
    ) -> bytes:
        """Render attendee name onto a copy of the PDF template.

        Args:
            attendee_name: Name to render on the certificate.
            vertical_position: Y position override (from top). If None, uses center.
            vertical_as_percentage: If True, vertical_position is 0-100 percentage.

        Returns:
            PDF document as bytes with the name rendered on the first page.

        Raises:
            TextOverflowError: If the name doesn't fit within page bounds.
        """
        x, y = self.calculate_text_position(
            attendee_name, vertical_position, vertical_as_percentage
        )

        # Create text overlay with ReportLab
        overlay_buffer = io.BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(self._page_width, self._page_height))

        # Convert RGB (0-255) to ReportLab color (0-1)
        r, g, b = self._font_config.font_color
        c.setFillColorRGB(r / 255, g / 255, b / 255)
        c.setFont(self._font_name, self._font_config.font_size)
        c.drawString(x, y, attendee_name)
        c.save()

        # Merge overlay onto template using PyMuPDF
        template_doc = fitz.open(self._template_path)
        overlay_doc = fitz.open(stream=overlay_buffer.getvalue(), filetype="pdf")

        page = template_doc.load_page(0)
        page.show_pdf_page(page.rect, overlay_doc, 0)

        # Output as bytes
        output_buffer = io.BytesIO()
        template_doc.save(output_buffer)
        template_doc.close()
        overlay_doc.close()

        return output_buffer.getvalue()
