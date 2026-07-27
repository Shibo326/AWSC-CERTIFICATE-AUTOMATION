"""Email composition and sending step UI component for CertFlow.

Provides a Flet component that handles ZIP download of all generated
certificates and bulk email sending with progress tracking, network-aware
queueing, and per-attendee failure reporting.
"""

import asyncio
import base64
import io
import logging
import zipfile
from typing import Callable, List, Optional

import flet as ft

from utils.email_queue import EmailQueueManager, QueuedEmail
from utils.email_sender import EmailSender
from utils.models import (
    AttendeeRecord,
    CertificateOutput,
    DeliveryFailure,
    EmailTemplate,
    SendResult,
)
from utils.network_monitor import NetworkMonitor
from utils.platform_storage import PlatformStorage

logger = logging.getLogger(__name__)


class SendStep:
    """Email composition and sending UI with ZIP download.

    Provides ZIP download of all generated certificates, email
    composition with {name} placeholder support, bulk sending with
    progress indicator, and a final summary of results. Integrates
    with NetworkMonitor to queue emails when offline.

    Attributes:
        certificates: List of generated certificates to send/download.
        attendees: List of attendee records matching the certificates.
    """

    def __init__(self, page: ft.Page,
        on_send_complete: Optional[Callable[[SendResult], None]] = None,
    ) -> None:
        """Initialize the send step.

        Args:
            on_send_complete: Optional callback invoked when bulk sending
                finishes. Receives the SendResult with successes and failures.
        """
        self.page = page
        self.on_send_complete = on_send_complete
        self.certificates: List[CertificateOutput] = []
        self.attendees: List[AttendeeRecord] = []
        self._is_sending = False

        self._network_monitor = NetworkMonitor()
        self._platform_storage = PlatformStorage()

        # UI controls (initialized in build)
        self._download_zip_btn: Optional[ft.ElevatedButton] = None
        self._subject_field: Optional[ft.TextField] = None
        self._body_field: Optional[ft.TextField] = None
        self._send_btn: Optional[ft.ElevatedButton] = None
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._progress_text: Optional[ft.Text] = None
        self._summary_container: Optional[ft.Container] = None

    def build(self) -> ft.Control:
        """Build the send step UI layout.

        Returns:
            A Column containing ZIP download button, email composition
            fields (subject, body), send button, progress indicator,
            and result summary panel.
        """
        self._download_zip_btn = ft.ElevatedButton(
            "Download ZIP",
            icon=ft.Icons.ARCHIVE,
            on_click=self._on_download_zip_click,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
            ),
        )

        self._subject_field = ft.TextField(
            label="Email Subject",
            hint_text="e.g., Your Certificate of Achievement",
            value="Your Certificate of Achievement",
            max_length=200,
        )

        self._body_field = ft.TextField(
            label="Email Body",
            hint_text="Use {name} as a placeholder for each attendee's name",
            value=(
                "Hi {name},\n\n"
                "Please find your certificate attached.\n\n"
                "Best regards,\nThe Team"
            ),
            multiline=True,
            min_lines=4,
            max_lines=10,
        )

        placeholder_hint = ft.Text(
            value="Tip: Use {name} in subject or body — it will be replaced "
            "with each attendee's name on send.",
            size=12,
            italic=True,
            color=ft.Colors.GREY_600,
        )

        self._send_btn = ft.ElevatedButton(
            "Send Emails",
            icon=ft.Icons.SEND,
            on_click=self._on_send_click,
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
            size=13,
            visible=False,
        )

        self._summary_container = ft.Container(
            visible=False,
            content=ft.Column(spacing=4),
        )

        return ft.Column(
            controls=[
                ft.Text(
                    "Download & Send",
                    size=16,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Divider(height=1),
                self._download_zip_btn,
                ft.Container(height=12),
                ft.Text(
                    "Email Composition",
                    size=16,
                    weight=ft.FontWeight.W_500,
                ),
                self._subject_field,
                self._body_field,
                placeholder_hint,
                ft.Container(height=12),
                self._send_btn,
                self._progress_bar,
                self._progress_text,
                self._summary_container,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        )

    def set_data(
        self,
        certificates: List[CertificateOutput],
        attendees: List[AttendeeRecord],
    ) -> None:
        """Set the certificates and attendees for sending/downloading.

        Args:
            certificates: Generated certificate outputs.
            attendees: Attendee records matching the certificates.
        """
        self.certificates = certificates
        self.attendees = attendees

    # ------------------------------------------------------------------
    # ZIP Download
    # ------------------------------------------------------------------

    def _on_download_zip_click(self, e: ft.ControlEvent) -> None:
        """Handle ZIP download button click."""
        if not self.certificates:
            self._show_snackbar(
                "No certificates to download.", ft.Colors.ORANGE
            )
            return
        self.page.run_task(self._create_and_download_zip)

    async def _create_and_download_zip(self) -> None:
        """Create a ZIP archive of certificates and trigger download."""
        zip_bytes = self._create_zip(self.certificates, self.attendees)

        # Save ZIP to the platform output directory
        output_dir = self._platform_storage.get_output_directory()
        await self._platform_storage.ensure_directory(output_dir)
        zip_path = output_dir / "certificates.zip"

        try:
            zip_path.write_bytes(zip_bytes)
            self._show_snackbar(
                f"ZIP saved to: {zip_path}", ft.Colors.GREEN
            )
        except (OSError, PermissionError) as exc:
            logger.error("Failed to save ZIP: %s", exc)
            self._show_snackbar(
                f"Failed to save ZIP: {exc}", ft.Colors.RED
            )

    def _create_zip(
        self,
        certificates: List[CertificateOutput],
        attendees: List[AttendeeRecord],
    ) -> bytes:
        """Create a ZIP archive of all generated certificates.

        Filenames are sanitized and deduplicated using PlatformStorage
        utilities. Each certificate is stored with the attendee's
        sanitized name and the original format extension.

        Args:
            certificates: List of generated certificate outputs.
            attendees: List of attendee records (used for naming).

        Returns:
            Raw bytes of the ZIP archive.
        """
        buffer = io.BytesIO()
        used_filenames: set = set()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for cert in certificates:
                extension = f".{cert.format}"
                filename = self._platform_storage.sanitize_filename(
                    cert.attendee_name, extension
                )
                filename = self._platform_storage.deduplicate_filename(
                    filename, used_filenames
                )
                used_filenames.add(filename)

                # Get certificate bytes
                cert_bytes = self._get_certificate_bytes(cert)
                zf.writestr(filename, cert_bytes)

        return buffer.getvalue()

    @staticmethod
    def _get_certificate_bytes(cert: CertificateOutput) -> bytes:
        """Extract raw bytes from a CertificateOutput.

        Handles both PIL Image objects and raw bytes (PDF).

        Args:
            cert: The certificate output to extract bytes from.

        Returns:
            Raw bytes of the certificate file.
        """
        from PIL import Image

        if isinstance(cert.certificate, Image.Image):
            buf = io.BytesIO()
            img_format = "PNG" if cert.format == "png" else "JPEG"
            cert.certificate.save(buf, format=img_format)
            return buf.getvalue()
        # Already bytes (PDF or pre-encoded)
        return cert.certificate

    # ------------------------------------------------------------------
    # Email Sending
    # ------------------------------------------------------------------

    def _on_send_click(self, e: ft.ControlEvent) -> None:
        """Handle send button click — delegates to async sending."""
        if self._is_sending:
            return
        self.page.run_task(self._send_clicked_async)

    async def _send_clicked_async(self) -> None:
        """Validate inputs and start async email sending."""
        if not self.certificates:
            self._show_snackbar(
                "No certificates to send.", ft.Colors.ORANGE
            )
            return
        if not self.attendees:
            self._show_snackbar(
                "No attendees available.", ft.Colors.ORANGE
            )
            return

        subject = self._subject_field.value.strip()
        body = self._body_field.value.strip()

        if not subject:
            self._show_snackbar(
                "Please enter an email subject.", ft.Colors.ORANGE
            )
            return
        if not body:
            self._show_snackbar(
                "Please enter an email body.", ft.Colors.ORANGE
            )
            return

        await self._send_emails(
            certificates=self.certificates,
            attendees=self.attendees,
            subject=subject,
            body=body,
        )

    async def _send_emails(
        self,
        certificates: List[CertificateOutput],
        attendees: List[AttendeeRecord],
        subject: str,
        body: str,
    ) -> None:
        """Send emails with certificates attached, with network awareness.

        Checks network connectivity first. If offline, queues all emails
        for later delivery. If online, sends emails one by one with
        progress updates and reports results.

        Args:
            certificates: Generated certificates to attach.
            attendees: Attendee records with email addresses.
            subject: Email subject (may contain {name} placeholder).
            body: Email body (may contain {name} placeholder).
        """
        self._is_sending = True
        self._send_btn.disabled = True
        self._summary_container.visible = False
        self.page.update()

        total = len(certificates)

        # Check network connectivity
        is_online = await self._network_monitor.is_online()

        if not is_online:
            # Queue all emails for later delivery
            await self._queue_emails(certificates, attendees, subject, body)
            self._is_sending = False
            self._send_btn.disabled = False
            self.page.update()
            return

        # Show progress UI
        self._progress_bar.value = 0
        self._progress_bar.visible = True
        self._progress_text.value = f"Sending 0 of {total}"
        self._progress_text.visible = True
        self.page.update()

        # Build certificate data list
        cert_data_list: List[bytes] = []
        for cert in certificates:
            cert_data_list.append(self._get_certificate_bytes(cert))

        # Determine format from first certificate
        cert_format = certificates[0].format if certificates else "png"

        # Build email template
        template = EmailTemplate(subject=subject, body=body)

        # Send using EmailSender
        result = SendResult()

        try:
            sender = EmailSender()

            def progress_callback(current: int, total_count: int) -> None:
                """Update progress UI during sending."""
                self._progress_bar.value = current / total_count
                self._progress_text.value = (
                    f"Sending {current} of {total_count}"
                )
                self.page.update()

            result = sender.send_bulk(
                recipients=attendees,
                certificate_data=cert_data_list,
                certificate_format=cert_format,
                template=template,
                progress_callback=progress_callback,
            )

        except ConnectionError as exc:
            # Network went down during sending — queue remaining
            logger.warning("Connection lost during sending: %s", exc)
            self._show_snackbar(
                "Connection lost. Remaining emails have been queued.",
                ft.Colors.ORANGE,
            )
            # Queue emails that weren't sent
            sent_count = result.success_count + result.failure_count
            if sent_count < total:
                remaining_certs = certificates[sent_count:]
                remaining_attendees = attendees[sent_count:]
                await self._queue_emails(
                    remaining_certs, remaining_attendees, subject, body
                )
        except Exception as exc:
            logger.error("Email sending failed: %s", exc)
            self._show_snackbar(
                f"Sending failed: {exc}", ft.Colors.RED
            )

        # Hide progress, show summary
        self._progress_bar.visible = False
        self._progress_text.visible = False
        self._is_sending = False
        self._send_btn.disabled = False

        self._display_send_summary(result)
        self.page.update()

        # Notify parent
        if self.on_send_complete:
            self.on_send_complete(result)

    async def _queue_emails(
        self,
        certificates: List[CertificateOutput],
        attendees: List[AttendeeRecord],
        subject: str,
        body: str,
    ) -> None:
        """Queue all emails for later delivery when network is available.

        Creates QueuedEmail entries with base64-encoded certificate data
        and enqueues them via EmailQueueManager.

        Args:
            certificates: Certificates to queue for sending.
            attendees: Attendee records with email addresses.
            subject: Email subject template.
            body: Email body template.
        """
        data_dir = self._platform_storage.get_app_data_directory()
        queue_manager = EmailQueueManager(data_dir)

        queued_emails: List[QueuedEmail] = []
        for cert, attendee in zip(certificates, attendees):
            cert_bytes = self._get_certificate_bytes(cert)
            cert_b64 = base64.b64encode(cert_bytes).decode("utf-8")

            # Replace {name} placeholder per attendee
            personalized_subject = subject.replace("{name}", attendee.name)
            personalized_body = body.replace("{name}", attendee.name)

            queued_email = QueuedEmail(
                id="",
                recipient_email=attendee.email,
                attendee_name=attendee.name,
                subject=personalized_subject,
                body=personalized_body,
                certificate_data_b64=cert_b64,
                certificate_format=cert.format,
            )
            queued_emails.append(queued_email)

        await queue_manager.enqueue(queued_emails)

        count = len(queued_emails)
        self._show_snackbar(
            f"{count} email{'s' if count != 1 else ''} queued. "
            "They will be sent when connectivity returns.",
            ft.Colors.BLUE,
        )

    def _display_send_summary(self, result: SendResult) -> None:
        """Display the final send summary with success/failure counts.

        Shows total sent, total failed, and per-failure details including
        the attendee name and error description.

        Args:
            result: The SendResult from bulk sending.
        """
        sent_count = result.success_count
        failed_count = result.failure_count

        summary_controls: List[ft.Control] = []

        # Header summary
        if failed_count == 0 and sent_count > 0:
            summary_controls.append(
                ft.Text(
                    f"✅ All {sent_count} email{'s' if sent_count != 1 else ''} "
                    f"sent successfully",
                    size=14,
                    weight=ft.FontWeight.W_500,
                    color=ft.Colors.GREEN,
                )
            )
        elif sent_count == 0 and failed_count == 0:
            summary_controls.append(
                ft.Text(
                    "No emails were processed.",
                    size=14,
                    color=ft.Colors.GREY_600,
                )
            )
        else:
            summary_controls.append(
                ft.Text(
                    f"📧 Sent: {sent_count}  |  ❌ Failed: {failed_count}",
                    size=14,
                    weight=ft.FontWeight.W_500,
                    color=(
                        ft.Colors.ORANGE
                        if failed_count > 0
                        else ft.Colors.GREEN
                    ),
                )
            )

        # Per-failure details
        if result.failures:
            summary_controls.append(
                ft.Text(
                    "Failure details:",
                    size=12,
                    weight=ft.FontWeight.W_500,
                    color=ft.Colors.RED,
                )
            )
            for failure in result.failures:
                summary_controls.append(
                    ft.Text(
                        f"• {failure.attendee_name}: {failure.error_message}",
                        size=12,
                        color=ft.Colors.RED_700,
                    )
                )

        self._summary_container.content = ft.Column(
            controls=summary_controls,
            spacing=4,
        )
        self._summary_container.visible = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_snackbar(
        self, message: str, color: str = ft.Colors.GREEN
    ) -> None:
        """Display a snackbar notification on the page.

        Args:
            message: The notification text to display.
            color: Background color for the snackbar.
        """
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=color,
                duration=4000,
            )
            self.page.snack_bar.open = True
            self.page.update()

    def reset(self) -> None:
        """Reset the component to its initial state.

        Clears certificates, attendees, and resets UI controls.
        """
        self.certificates = []
        self.attendees = []
        self._is_sending = False

        if self._send_btn:
            self._send_btn.disabled = False
        if self._progress_bar:
            self._progress_bar.visible = False
            self._progress_bar.value = 0
        if self._progress_text:
            self._progress_text.visible = False
            self._progress_text.value = ""
        if self._summary_container:
            self._summary_container.visible = False
        if self._subject_field:
            self._subject_field.value = "Your Certificate of Achievement"
        if self._body_field:
            self._body_field.value = (
                "Hi {name},\n\n"
                "Please find your certificate attached.\n\n"
                "Best regards,\nThe Team"
            )

        self.page.update()
