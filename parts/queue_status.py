"""Email queue status display component for CertFlow native app.

Shows the current state of the email queue including pending count,
permanently failed count, last send attempt timestamp, and notifications
for queued/batch-processed emails.
"""

from typing import Optional

import flet as ft

from utils.email_queue import EmailQueueManager, QueueStatus


class QueueStatusDisplay:
    """Flet UI component displaying email queue status.

    Shows pending email count, permanently failed count, last send
    attempt timestamp, offline queueing notifications, and batch
    processing summaries.

    Attributes:
        queue_manager: The EmailQueueManager instance providing queue state.
    """

    def __init__(self, page: ft.Page, queue_manager: EmailQueueManager) -> None:
        """Initialize the QueueStatusDisplay component.

        Args:
            queue_manager: The EmailQueueManager instance to read status from.
        """
        self.page = page
        self.queue_manager = queue_manager

    def build(self) -> ft.Control:
        """Build the queue status display UI controls."""
        self._pending_count_text = ft.Text(
            "Pending: 0",
            size=14,
            weight=ft.FontWeight.W_500,
        )

        self._failed_count_text = ft.Text(
            "Failed: 0",
            size=14,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.RED,
        )

        self._last_attempt_text = ft.Text(
            "Last attempt: —",
            size=12,
            color=ft.Colors.GREY,
        )

        self._notification_banner = ft.Container(
            content=ft.Text(
                "",
                size=13,
                color=ft.Colors.WHITE,
            ),
            bgcolor=ft.Colors.ORANGE,
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=6,
            visible=False,
        )

        self._summary_banner = ft.Container(
            content=ft.Text(
                "",
                size=13,
                color=ft.Colors.WHITE,
            ),
            bgcolor=ft.Colors.GREEN,
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=6,
            visible=False,
        )

        return ft.Column(
            controls=[
                ft.Text(
                    "Email Queue Status",
                    size=16,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Row(
                    controls=[
                        self._pending_count_text,
                        ft.VerticalDivider(width=1),
                        self._failed_count_text,
                    ],
                    spacing=12,
                ),
                self._last_attempt_text,
                self._notification_banner,
                self._summary_banner,
            ],
            spacing=12,
        )

    async def refresh_status(self) -> None:
        """Refresh the displayed queue status from the queue manager.

        Reads the current QueueStatus and updates the pending count,
        failed count, and last attempt timestamp labels.
        """
        status: QueueStatus = await self.queue_manager.get_status()

        self._pending_count_text.value = f"Pending: {status.pending_count}"
        self._failed_count_text.value = f"Failed: {status.failed_count}"

        if status.last_attempt:
            # Format the ISO timestamp for display (show date and time)
            display_ts = self._format_timestamp(status.last_attempt)
            self._last_attempt_text.value = f"Last attempt: {display_ts}"
        else:
            self._last_attempt_text.value = "Last attempt: —"

        self.page.update()

    def show_queued_notification(self, count: int) -> None:
        """Show a notification indicating emails have been queued offline.

        Displays a banner with the count of emails queued for later
        delivery when the network is unavailable.

        Args:
            count: Number of emails queued for later delivery.
        """
        banner_text: ft.Text = self._notification_banner.content
        banner_text.value = (
            f"{count} email{'s' if count != 1 else ''} queued for later delivery"
        )
        self._notification_banner.visible = True

        # Hide the summary banner when a new queue notification appears
        self._summary_banner.visible = False

        self.page.update()

    def show_batch_summary(self, sent: int, failed: int) -> None:
        """Show a summary after batch processing completes.

        Displays a banner with the count of emails sent successfully
        and the count that permanently failed.

        Args:
            sent: Number of emails sent successfully.
            failed: Number of emails that permanently failed.
        """
        summary_text: ft.Text = self._summary_banner.content
        summary_text.value = (
            f"Batch complete: {sent} sent, {failed} failed"
        )

        # Use green if no failures, orange if there are failures
        if failed > 0:
            self._summary_banner.bgcolor = ft.Colors.ORANGE
        else:
            self._summary_banner.bgcolor = ft.Colors.GREEN

        self._summary_banner.visible = True

        # Hide the queued notification when batch summary appears
        self._notification_banner.visible = False

        self.page.update()

    def dismiss_notifications(self) -> None:
        """Hide all notification banners."""
        self._notification_banner.visible = False
        self._summary_banner.visible = False
        self.page.update()

    @staticmethod
    def _format_timestamp(iso_timestamp: str) -> str:
        """Format an ISO 8601 timestamp for user-friendly display.

        Args:
            iso_timestamp: An ISO 8601 timestamp string.

        Returns:
            A human-readable date/time string (YYYY-MM-DD HH:MM:SS).
        """
        try:
            # Handle ISO timestamps with timezone info
            # e.g. "2024-01-15T10:31:00+00:00" or "2024-01-15T10:31:00Z"
            date_time = iso_timestamp.replace("Z", "").split("+")[0]
            if "T" in date_time:
                date_str, time_str = date_time.split("T", 1)
                # Truncate to seconds (remove microseconds if present)
                time_display = time_str.split(".")[0]
                return f"{date_str} {time_display}"
            return iso_timestamp
        except (ValueError, IndexError):
            return iso_timestamp
