"""Batch certificate generation step UI component for CertFlow.

Provides a Flet component that handles batch certificate generation
with a progress indicator, per-attendee error handling, and in-memory
certificate storage for the review step.
"""

import asyncio
import logging
from typing import Callable, List, Optional

import flet as ft

from utils.certificate_generator import CertificateGenerator
from utils.font_config import FontConfiguration
from utils.models import AttendeeRecord, BatchResult, CertificateOutput, GenerationError

logger = logging.getLogger(__name__)


class GenerateStep:
    """Batch certificate generation UI with progress indicator.

    Shows a "Generate Certificates" button that initiates batch generation.
    Displays real-time progress ("Generating X of Y"), collects per-attendee
    errors (text overflow), and stores generated certificates in memory
    for use in the review step.

    Attributes:
        certificates: List of successfully generated certificates.
        errors: List of per-attendee generation errors.
    """

    def __init__(self, page: ft.Page,
        on_generation_complete: Optional[Callable[[BatchResult], None]] = None,
    ) -> None:
        """Initialize the generate step.

        Args:
            on_generation_complete: Optional callback invoked when batch
                generation finishes. Receives the BatchResult containing
                certificates and errors.
        """
        self.page = page
        self.on_generation_complete = on_generation_complete
        self.certificates: List[CertificateOutput] = []
        self.errors: List[GenerationError] = []
        self._is_generating = False

        # UI controls (initialized in build)
        self._generate_btn: Optional[ft.ElevatedButton] = None
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._progress_text: Optional[ft.Text] = None
        self._result_text: Optional[ft.Text] = None
        self._error_container: Optional[ft.Container] = None

    def build(self) -> ft.Control:
        """Build the generate step UI layout.

        Returns:
            A Column containing the generate button, progress indicator,
            result summary, and expandable error panel.
        """
        self._generate_btn = ft.ElevatedButton(
            "Generate Certificates",
            icon=ft.Icons.AUTO_AWESOME,
            on_click=self._on_generate_click,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TEAL,
                color=ft.Colors.WHITE,
            ),
        )

        self._progress_bar = ft.ProgressBar(
            width=500,
            value=0,
            visible=False,
        )

        self._progress_text = ft.Text(
            value="",
            size=14,
            visible=False,
        )

        self._result_text = ft.Text(
            value="",
            size=14,
            weight=ft.FontWeight.W_500,
            visible=False,
        )

        self._error_container = ft.Container(
            visible=False,
            content=ft.Column(spacing=4),
        )

        return ft.Column(
            controls=[
                self._generate_btn,
                self._progress_bar,
                self._progress_text,
                self._result_text,
                self._error_container,
            ],
            spacing=10,
        )

    def _on_generate_click(self, e: ft.ControlEvent) -> None:
        """Handle generate button click — delegates to async generation."""
        if self._is_generating:
            return
        self.page.run_task(self._generate_clicked_async)

    async def _generate_clicked_async(self) -> None:
        """Validate inputs and start async generation via page.run_task."""
        # Access template_data, attendees, and font_config from page state
        # These should be set by the parent workflow before generation
        page_state = getattr(self.page, "certflow_state", None)
        if page_state is None:
            self._show_snackbar(
                "Internal error: app state not available.", ft.Colors.RED
            )
            return

        template_bytes = page_state.get("template_bytes")
        template_format = page_state.get("template_format")
        attendees: List[AttendeeRecord] = page_state.get("attendees", [])
        font_config: Optional[FontConfiguration] = page_state.get("font_config")
        vertical_position: int = page_state.get("vertical_position", 50)

        if not template_bytes:
            self._show_snackbar("Upload a template first.", ft.Colors.ORANGE)
            return
        if not attendees:
            self._show_snackbar("Upload attendees first.", ft.Colors.ORANGE)
            return

        await self.generate_batch(
            template_bytes=template_bytes,
            template_format=template_format,
            attendees=attendees,
            font_config=font_config,
            vertical_position=vertical_position,
        )

    async def generate_batch(
        self,
        template_bytes: bytes,
        template_format: str,
        attendees: List[AttendeeRecord],
        font_config: Optional[FontConfiguration] = None,
        vertical_position: int = 50,
    ) -> BatchResult:
        """Run batch certificate generation with progress updates.

        Generates certificates one-by-one, updating the progress bar and
        status text after each. Text overflow errors are collected per-attendee
        without halting the batch.

        Args:
            template_bytes: Raw bytes of the certificate template.
            template_format: Template format string ('png', 'jpg', or 'pdf').
            attendees: List of attendee records to generate certificates for.
            font_config: Font configuration for rendering. Defaults to Arial 40pt.
            vertical_position: Vertical position percentage (0-100).

        Returns:
            BatchResult containing successful certificates and errors.
        """
        self._is_generating = True
        self.certificates = []
        self.errors = []

        # Reset and show progress UI
        self._generate_btn.disabled = True
        self._progress_bar.value = 0
        self._progress_bar.visible = True
        self._progress_text.value = f"Generating 0 of {len(attendees)}"
        self._progress_text.visible = True
        self._result_text.visible = False
        self._error_container.visible = False
        self.page.update()

        total = len(attendees)
        generator = None

        try:
            generator = CertificateGenerator(
                template_bytes=template_bytes,
                template_format=template_format,
                font_config=font_config or FontConfiguration(),
            )

            for idx, attendee in enumerate(attendees):
                try:
                    cert = generator.generate(
                        attendee_name=attendee.name,
                        vertical_position=vertical_position,
                        vertical_as_percentage=True,
                    )
                    self.certificates.append(cert)
                except Exception as exc:
                    # Per-attendee error (e.g., text overflow) — report and continue
                    error = GenerationError(
                        attendee_name=attendee.name,
                        error_message=str(exc),
                    )
                    self.errors.append(error)
                    logger.warning(
                        "Certificate generation failed for '%s': %s",
                        attendee.name,
                        exc,
                    )

                # Update progress after each certificate
                completed = idx + 1
                self._progress_bar.value = completed / total
                self._progress_text.value = (
                    f"Generating {completed} of {total}"
                )
                self.page.update()

                # Yield control to allow UI to refresh
                await asyncio.sleep(0)

        except Exception as exc:
            # Fatal error during generator initialization
            logger.error("Batch generation failed: %s", exc)
            self._result_text.value = f"❌ Generation failed: {exc}"
            self._result_text.color = ft.Colors.RED
            self._result_text.visible = True
            self._progress_bar.visible = False
            self._progress_text.visible = False
            self._generate_btn.disabled = False
            self._is_generating = False
            self.page.update()
            return BatchResult()
        finally:
            if generator:
                generator.cleanup()

        # Generation complete — show results
        self._progress_bar.value = 1.0
        self._progress_text.visible = False
        self._generate_btn.disabled = False
        self._is_generating = False

        batch_result = BatchResult(
            certificates=self.certificates,
            errors=self.errors,
        )

        self._display_result_summary(batch_result)
        self.page.update()

        # Notify parent workflow
        if self.on_generation_complete:
            self.on_generation_complete(batch_result)

        return batch_result

    def _display_result_summary(self, result: BatchResult) -> None:
        """Display success/error summary after generation completes.

        Args:
            result: The BatchResult from batch generation.
        """
        cert_count = len(result.certificates)
        error_count = len(result.errors)

        if error_count == 0:
            # Pure success
            self._result_text.value = (
                f"✅ {cert_count} certificate{'s' if cert_count != 1 else ''} "
                f"generated successfully"
            )
            self._result_text.color = ft.Colors.GREEN
        else:
            # Mixed success/error
            self._result_text.value = (
                f"⚠️ {cert_count} generated, {error_count} failed"
            )
            self._result_text.color = ft.Colors.ORANGE

            # Build expandable error list
            error_controls = []
            for err in result.errors:
                error_controls.append(
                    ft.Text(
                        f"• {err.attendee_name}: {err.error_message}",
                        size=12,
                        color=ft.Colors.RED_700,
                    )
                )

            error_column = ft.Column(
                controls=[
                    ft.Text(
                        f"❌ {error_count} error{'s' if error_count != 1 else ''}:",
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.RED,
                    ),
                    *error_controls,
                ],
                spacing=4,
            )
            self._error_container.content = error_column
            self._error_container.visible = True

        self._result_text.visible = True

    def _show_snackbar(self, message: str, color: str = ft.Colors.GREEN) -> None:
        """Display a snackbar notification on the page.

        Args:
            message: The notification text to display.
            color: Background color for the snackbar.
        """
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=color,
                duration=3000,
            )
            self.page.snack_bar.open = True
            self.page.update()

    def reset(self) -> None:
        """Reset the component to its initial state.

        Clears stored certificates, errors, and resets UI controls to default.
        """
        self.certificates = []
        self.errors = []
        self._is_generating = False

        if self._generate_btn:
            self._generate_btn.disabled = False
        if self._progress_bar:
            self._progress_bar.visible = False
            self._progress_bar.value = 0
        if self._progress_text:
            self._progress_text.visible = False
            self._progress_text.value = ""
        if self._result_text:
            self._result_text.visible = False
            self._result_text.value = ""
        if self._error_container:
            self._error_container.visible = False

        self.page.update()
