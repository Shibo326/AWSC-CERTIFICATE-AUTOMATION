"""Certificate review gallery with edit capability for CertFlow.

Provides a Flet component that displays generated certificates with
previous/next navigation, a position counter, and the ability to edit
an attendee name and regenerate only that single certificate.

Requirements: 11.6, 11.7
"""

import logging
from typing import Callable, List, Optional

import flet as ft

from utils.certificate_generator import CertificateGenerator
from utils.font_config import FontConfiguration
from utils.models import CertificateOutput
from utils.preview_renderer import render_preview_base64

logger = logging.getLogger(__name__)


class ReviewStep:
    """Certificate review gallery with navigation and single-certificate edit.

    Displays certificates one at a time with Previous/Next navigation
    and a "X / Y" counter. Allows editing an attendee name and regenerating
    only that certificate without affecting others.

    Attributes:
        certificates: List of CertificateOutput objects to review.
        current_index: Zero-based index of the currently displayed certificate.
    """

    def __init__(self, page: ft.Page,
        on_edit_complete: Optional[Callable[[int, CertificateOutput], None]] = None,
    ) -> None:
        """Initialize the review step.

        Args:
            on_edit_complete: Optional callback invoked after a single
                certificate is regenerated. Receives (index, new_certificate).
        """
        self.page = page
        self.on_edit_complete = on_edit_complete
        self.certificates: List[CertificateOutput] = []
        self.current_index: int = 0

        # Generation settings needed for single-certificate regeneration
        self._template_bytes: Optional[bytes] = None
        self._template_format: Optional[str] = None
        self._font_config: Optional[FontConfiguration] = None
        self._vertical_position: int = 50

        # Reusable generator so a single-name edit does not re-open the
        # template / re-register fonts on every regeneration.
        self._generator: Optional[CertificateGenerator] = None

    def build(self) -> ft.Control:
        """Build the review gallery UI layout.

        Returns:
            A Column containing the certificate image display, navigation
            controls, counter, and edit controls.
        """
        # Certificate preview image (base64-encoded)
        self._preview_image = ft.Image(
            src="",
            width=500,
            height=350,
            fit=ft.BoxFit.CONTAIN,
            visible=False,
        )

        # Empty state text
        self._empty_text = ft.Text(
            "No certificates to review. Generate certificates first.",
            size=14,
            color=ft.Colors.GREY,
            visible=True,
        )

        # Navigation counter: "3 / 20"
        self._counter_text = ft.Text(
            "0 / 0",
            size=14,
            weight=ft.FontWeight.W_500,
            visible=False,
        )

        # Attendee name display
        self._name_text = ft.Text(
            "",
            size=16,
            weight=ft.FontWeight.W_600,
            visible=False,
        )

        # Navigation buttons
        self._prev_btn = ft.IconButton(
            icon=ft.Icons.ARROW_BACK_IOS,
            tooltip="Previous certificate",
            on_click=self._on_prev,
            visible=False,
        )

        self._next_btn = ft.IconButton(
            icon=ft.Icons.ARROW_FORWARD_IOS,
            tooltip="Next certificate",
            on_click=self._on_next,
            visible=False,
        )

        # Edit name controls
        self._edit_field = ft.TextField(
            label="Edit attendee name",
            width=280,
            visible=False,
            on_submit=self._on_edit_name,
        )

        self._regenerate_btn = ft.ElevatedButton(
            "Regenerate",
            icon=ft.Icons.REFRESH,
            on_click=self._on_edit_name,
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TEAL,
                color=ft.Colors.WHITE,
            ),
        )

        self._edit_status = ft.Text(
            "",
            size=12,
            visible=False,
        )

        # Navigation row
        nav_row = ft.Row(
            controls=[
                self._prev_btn,
                self._counter_text,
                self._next_btn,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        # Edit row
        edit_row = ft.Row(
            controls=[
                self._edit_field,
                self._regenerate_btn,
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            wrap=True,
        )

        return ft.Column(
            controls=[
                self._empty_text,
                self._name_text,
                self._preview_image,
                nav_row,
                ft.Container(height=12),
                edit_row,
                self._edit_status,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def set_certificates(
        self,
        certificates: List[CertificateOutput],
        template_bytes: Optional[bytes] = None,
        template_format: Optional[str] = None,
        font_config: Optional[FontConfiguration] = None,
        vertical_position: int = 50,
    ) -> None:
        """Set the certificates to display in the gallery.

        Also stores generation settings for single-certificate regeneration.

        Args:
            certificates: List of CertificateOutput objects to display.
            template_bytes: Template bytes for regeneration.
            template_format: Template format for regeneration.
            font_config: Font configuration for regeneration.
            vertical_position: Vertical position percentage for regeneration.
        """
        self.certificates = certificates
        self.current_index = 0
        self._template_bytes = template_bytes
        self._template_format = template_format
        self._font_config = font_config
        self._vertical_position = vertical_position

        # New template/font settings invalidate any cached generator.
        self._dispose_generator()

        if certificates:
            self._empty_text.visible = False
            self._preview_image.visible = True
            self._counter_text.visible = True
            self._name_text.visible = True
            self._prev_btn.visible = True
            self._next_btn.visible = True
            self._edit_field.visible = True
            self._regenerate_btn.visible = True
            self._display_current()
        else:
            self._empty_text.visible = True
            self._preview_image.visible = False
            self._counter_text.visible = False
            self._name_text.visible = False
            self._prev_btn.visible = False
            self._next_btn.visible = False
            self._edit_field.visible = False
            self._regenerate_btn.visible = False

        self._edit_status.visible = False
        self.page.update()

    def _display_current(self) -> None:
        """Render the certificate at the current index in the gallery."""
        if not self.certificates:
            return

        cert = self.certificates[self.current_index]
        total = len(self.certificates)

        # Update counter
        self._counter_text.value = f"{self.current_index + 1} / {total}"

        # Update attendee name
        self._name_text.value = cert.attendee_name

        # Pre-fill edit field with current name
        self._edit_field.value = cert.attendee_name

        # Update navigation button states
        self._prev_btn.disabled = self.current_index <= 0
        self._next_btn.disabled = self.current_index >= total - 1

        # Generate preview image
        self._render_preview(cert)

    def _render_preview(self, cert: CertificateOutput) -> None:
        """Render a certificate as a downscaled, cached base64 preview.

        Delegates to the shared preview renderer, which downscales the image
        and caches the encoded result so navigating Prev/Next between already
        seen certificates is instant.

        Args:
            cert: The CertificateOutput to render as preview.
        """
        self._preview_image.src = render_preview_base64(
            cert.certificate, cert.format
        )

    def _on_prev(self, e: ft.ControlEvent) -> None:
        """Navigate to the previous certificate."""
        if self.current_index > 0:
            self.current_index -= 1
            self._edit_status.visible = False
            self._display_current()
            self.page.update()

    def _on_next(self, e: ft.ControlEvent) -> None:
        """Navigate to the next certificate."""
        if self.current_index < len(self.certificates) - 1:
            self.current_index += 1
            self._edit_status.visible = False
            self._display_current()
            self.page.update()

    def _on_edit_name(self, e: ft.ControlEvent) -> None:
        """Handle name edit and single-certificate regeneration.

        Regenerates ONLY the certificate at the current index with the
        new name, without affecting any other certificates in the batch.
        """
        new_name = self._edit_field.value.strip() if self._edit_field.value else ""

        if not new_name:
            self._edit_status.value = "Name cannot be empty."
            self._edit_status.color = ft.Colors.RED
            self._edit_status.visible = True
            self.page.update()
            return

        # Check if name actually changed
        current_cert = self.certificates[self.current_index]
        if new_name == current_cert.attendee_name:
            self._edit_status.value = "Name unchanged."
            self._edit_status.color = ft.Colors.GREY
            self._edit_status.visible = True
            self.page.update()
            return

        # Verify we have the template data for regeneration
        if not self._template_bytes or not self._template_format:
            self._edit_status.value = (
                "Cannot regenerate: template data not available."
            )
            self._edit_status.color = ft.Colors.RED
            self._edit_status.visible = True
            self.page.update()
            return

        # Regenerate only this single certificate using a reused generator.
        try:
            generator = self._get_generator()

            new_cert = generator.generate(
                attendee_name=new_name,
                vertical_position=self._vertical_position,
                vertical_as_percentage=True,
            )

            # Replace only this certificate in the list
            self.certificates[self.current_index] = new_cert

            # Update display
            self._display_current()

            self._edit_status.value = f"Regenerated for '{new_name}'"
            self._edit_status.color = ft.Colors.GREEN
            self._edit_status.visible = True

            # Notify parent
            if self.on_edit_complete:
                self.on_edit_complete(self.current_index, new_cert)

        except Exception as exc:
            logger.error("Single certificate regeneration failed: %s", exc)
            self._edit_status.value = f"Regeneration failed: {exc}"
            self._edit_status.color = ft.Colors.RED
            self._edit_status.visible = True

        self.page.update()

    def _get_generator(self) -> CertificateGenerator:
        """Return a cached CertificateGenerator, creating it on first use.

        Reusing the generator avoids re-opening the template and re-registering
        fonts on every single-name edit.
        """
        if self._generator is None:
            self._generator = CertificateGenerator(
                template_bytes=self._template_bytes,
                template_format=self._template_format,
                font_config=self._font_config or FontConfiguration(),
            )
        return self._generator

    def _dispose_generator(self) -> None:
        """Clean up and drop the cached generator, if any."""
        if self._generator is not None:
            self._generator.cleanup()
            self._generator = None

    def reset(self) -> None:
        """Reset the component to its initial state."""
        self.certificates = []
        self.current_index = 0
        self._template_bytes = None
        self._template_format = None
        self._font_config = None
        self._vertical_position = 50
        self._dispose_generator()

        if self._preview_image:
            self._preview_image.src = ""
            self._preview_image.visible = False
        if self._empty_text:
            self._empty_text.visible = True
        if self._counter_text:
            self._counter_text.visible = False
        if self._name_text:
            self._name_text.visible = False
        if self._prev_btn:
            self._prev_btn.visible = False
        if self._next_btn:
            self._next_btn.visible = False
        if self._edit_field:
            self._edit_field.visible = False
            self._edit_field.value = ""
        if self._regenerate_btn:
            self._regenerate_btn.visible = False
        if self._edit_status:
            self._edit_status.visible = False

        self.page.update()
