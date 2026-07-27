"""Tests for the QueueStatusDisplay component."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.email_queue import EmailQueueManager, QueueStatus


class TestQueueStatusDisplay:
    """Tests for QueueStatusDisplay component logic."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.data_dir = Path("/tmp/test_queue_status")
        self.queue_manager = EmailQueueManager(self.data_dir)
        self.mock_page = MagicMock()

    def _make_display(self, queue_manager=None):
        """Create a QueueStatusDisplay with mock page and build it."""
        from parts.queue_status import QueueStatusDisplay
        qm = queue_manager or self.queue_manager
        display = QueueStatusDisplay(page=self.mock_page, queue_manager=qm)
        display.build()
        return display

    def test_format_timestamp_iso_with_timezone(self) -> None:
        from parts.queue_status import QueueStatusDisplay
        result = QueueStatusDisplay._format_timestamp(
            "2024-01-15T10:31:00+00:00"
        )
        assert result == "2024-01-15 10:31:00"

    def test_format_timestamp_iso_with_z(self) -> None:
        from parts.queue_status import QueueStatusDisplay
        result = QueueStatusDisplay._format_timestamp("2024-01-15T10:31:00Z")
        assert result == "2024-01-15 10:31:00"

    def test_format_timestamp_with_microseconds(self) -> None:
        from parts.queue_status import QueueStatusDisplay
        result = QueueStatusDisplay._format_timestamp(
            "2024-01-15T10:31:00.123456+00:00"
        )
        assert result == "2024-01-15 10:31:00"

    def test_format_timestamp_plain(self) -> None:
        from parts.queue_status import QueueStatusDisplay
        result = QueueStatusDisplay._format_timestamp("2024-01-15T10:31:00")
        assert result == "2024-01-15 10:31:00"

    def test_format_timestamp_invalid_returns_original(self) -> None:
        from parts.queue_status import QueueStatusDisplay
        result = QueueStatusDisplay._format_timestamp("not a timestamp")
        assert result == "not a timestamp"

    def test_component_instantiation(self) -> None:
        """Test that QueueStatusDisplay can be instantiated."""
        display = self._make_display()
        assert display.queue_manager is self.queue_manager

    def test_show_queued_notification_single(self) -> None:
        """Test queued notification with single email."""
        display = self._make_display()
        display.show_queued_notification(1)
        banner_text = display._notification_banner.content
        assert banner_text.value == "1 email queued for later delivery"
        assert display._notification_banner.visible is True

    def test_show_queued_notification_multiple(self) -> None:
        """Test queued notification with multiple emails."""
        display = self._make_display()
        display.show_queued_notification(5)
        banner_text = display._notification_banner.content
        assert banner_text.value == "5 emails queued for later delivery"
        assert display._notification_banner.visible is True

    def test_show_batch_summary_no_failures(self) -> None:
        """Test batch summary with all emails sent successfully."""
        import flet as ft
        display = self._make_display()
        display.show_batch_summary(sent=10, failed=0)
        summary_text = display._summary_banner.content
        assert summary_text.value == "Batch complete: 10 sent, 0 failed"
        assert display._summary_banner.visible is True
        assert display._summary_banner.bgcolor == ft.Colors.GREEN

    def test_show_batch_summary_with_failures(self) -> None:
        """Test batch summary with some failures changes to orange."""
        import flet as ft
        display = self._make_display()
        display.show_batch_summary(sent=7, failed=3)
        summary_text = display._summary_banner.content
        assert summary_text.value == "Batch complete: 7 sent, 3 failed"
        assert display._summary_banner.visible is True
        assert display._summary_banner.bgcolor == ft.Colors.ORANGE

    def test_dismiss_notifications(self) -> None:
        """Test dismissing all notification banners."""
        display = self._make_display()
        display.show_queued_notification(3)
        display.show_batch_summary(sent=2, failed=1)
        display.dismiss_notifications()
        assert display._notification_banner.visible is False
        assert display._summary_banner.visible is False

    def test_refresh_status_with_pending_and_failed(self) -> None:
        """Test refresh_status updates labels from queue manager."""
        mock_qm = MagicMock()
        mock_qm.get_status = AsyncMock(
            return_value=QueueStatus(
                pending_count=5,
                failed_count=2,
                last_attempt="2024-06-01T14:30:00+00:00",
            )
        )
        display = self._make_display(queue_manager=mock_qm)
        asyncio.run(display.refresh_status())
        assert display._pending_count_text.value == "Pending: 5"
        assert display._failed_count_text.value == "Failed: 2"
        assert "2024-06-01 14:30:00" in display._last_attempt_text.value

    def test_refresh_status_no_last_attempt(self) -> None:
        """Test refresh_status when there's no last attempt timestamp."""
        mock_qm = MagicMock()
        mock_qm.get_status = AsyncMock(
            return_value=QueueStatus(
                pending_count=0,
                failed_count=0,
                last_attempt=None,
            )
        )
        display = self._make_display(queue_manager=mock_qm)
        asyncio.run(display.refresh_status())
        assert display._pending_count_text.value == "Pending: 0"
        assert display._failed_count_text.value == "Failed: 0"
        assert "Last attempt:" in display._last_attempt_text.value
