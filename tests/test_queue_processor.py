"""Unit tests for QueueProcessor integration module.

Tests cover:
- process_queue sends pending emails successfully
- Socket errors trigger mark_failed
- Auth errors stop processing immediately
- Summary returns correct sent/failed counts
"""

import base64
import smtplib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.email_queue import EmailQueueManager, QueuedEmail
from utils.email_sender import EmailSender
from utils.exceptions import AuthenticationError
from utils.models import GmailCredentials
from utils.network_monitor import NetworkMonitor
from utils.queue_processor import QueueProcessor


@pytest.fixture
def mock_queue_manager(tmp_path: Path) -> EmailQueueManager:
    """Create a real EmailQueueManager with a temp directory."""
    return EmailQueueManager(data_dir=tmp_path)


@pytest.fixture
def mock_email_sender() -> MagicMock:
    """Create a mocked EmailSender."""
    sender = MagicMock(spec=EmailSender)
    sender._credentials = GmailCredentials(
        sender_email="test@gmail.com",
        app_password="abcdefghijklmnop",
    )
    sender._smtp = MagicMock()
    sender.connect = MagicMock()
    sender.disconnect = MagicMock()
    sender._compose_email = MagicMock(return_value=MagicMock(as_string=MagicMock(
        return_value="MIME message"
    )))
    return sender


@pytest.fixture
def mock_network_monitor() -> MagicMock:
    """Create a mocked NetworkMonitor."""
    monitor = MagicMock(spec=NetworkMonitor)
    monitor.start_polling = AsyncMock()
    monitor.stop_polling = AsyncMock()
    return monitor


@pytest.fixture
def sample_queued_emails() -> list:
    """Create sample queued emails for testing."""
    cert_data = base64.b64encode(b"fake certificate data").decode()
    return [
        QueuedEmail(
            id="email-001",
            recipient_email="alice@example.com",
            attendee_name="Alice Smith",
            subject="Your Certificate",
            body="Hi Alice Smith, here is your cert.",
            certificate_data_b64=cert_data,
            certificate_format="png",
            retry_count=0,
        ),
        QueuedEmail(
            id="email-002",
            recipient_email="bob@example.com",
            attendee_name="Bob Jones",
            subject="Your Certificate",
            body="Hi Bob Jones, here is your cert.",
            certificate_data_b64=cert_data,
            certificate_format="pdf",
            retry_count=1,
        ),
        QueuedEmail(
            id="email-003",
            recipient_email="carol@example.com",
            attendee_name="Carol White",
            subject="Your Certificate",
            body="Hi Carol White, here is your cert.",
            certificate_data_b64=cert_data,
            certificate_format="jpg",
            retry_count=0,
        ),
    ]


@pytest.fixture
def processor(
    mock_queue_manager: EmailQueueManager,
    mock_email_sender: MagicMock,
    mock_network_monitor: MagicMock,
) -> QueueProcessor:
    """Create a QueueProcessor with mocked dependencies."""
    return QueueProcessor(
        queue_manager=mock_queue_manager,
        email_sender=mock_email_sender,
        network_monitor=mock_network_monitor,
    )


class TestProcessQueueSendsPending:
    """Test that process_queue sends all pending emails successfully."""

    @pytest.mark.asyncio
    async def test_sends_all_pending_emails(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """All pending emails should be sent and marked as sent."""
        await mock_queue_manager.enqueue(sample_queued_emails)

        sent, failed = await processor.process_queue()

        assert sent == 3
        assert failed == 0
        assert mock_email_sender.connect.call_count == 1
        assert mock_email_sender.disconnect.call_count == 1
        assert mock_email_sender._smtp.sendmail.call_count == 3

    @pytest.mark.asyncio
    async def test_marks_emails_as_sent(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        sample_queued_emails: list,
    ) -> None:
        """Successfully sent emails are removed from the queue."""
        await mock_queue_manager.enqueue(sample_queued_emails)

        await processor.process_queue()

        # All emails should be removed from the queue
        pending = await mock_queue_manager.dequeue_pending()
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_empty_queue_returns_zero(
        self,
        processor: QueueProcessor,
        mock_email_sender: MagicMock,
    ) -> None:
        """Empty queue should return (0, 0) without connecting."""
        sent, failed = await processor.process_queue()

        assert sent == 0
        assert failed == 0
        mock_email_sender.connect.assert_not_called()


class TestSocketErrorsMarkFailed:
    """Test that socket/connection errors trigger mark_failed."""

    @pytest.mark.asyncio
    async def test_socket_error_marks_failed(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """Socket errors should mark the email as failed and continue."""
        await mock_queue_manager.enqueue(sample_queued_emails)

        # First email fails with OSError, others succeed
        call_count = [0]

        def sendmail_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("Connection reset by peer")

        mock_email_sender._smtp.sendmail.side_effect = sendmail_side_effect

        sent, failed = await processor.process_queue()

        assert sent == 2
        assert failed == 1

    @pytest.mark.asyncio
    async def test_smtp_exception_marks_failed(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """SMTP exceptions should mark the email as failed and continue."""
        await mock_queue_manager.enqueue(sample_queued_emails)

        # Second email fails with SMTPException
        call_count = [0]

        def sendmail_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise smtplib.SMTPException("Server error")

        mock_email_sender._smtp.sendmail.side_effect = sendmail_side_effect

        sent, failed = await processor.process_queue()

        assert sent == 2
        assert failed == 1

    @pytest.mark.asyncio
    async def test_connection_error_on_connect_marks_all_failed(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """If connect() fails, all pending emails are marked failed."""
        await mock_queue_manager.enqueue(sample_queued_emails)
        mock_email_sender.connect.side_effect = ConnectionError("No network")

        sent, failed = await processor.process_queue()

        assert sent == 0
        assert failed == 3

    @pytest.mark.asyncio
    async def test_failed_email_retry_count_incremented(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """Failed emails should have their retry_count incremented."""
        await mock_queue_manager.enqueue(sample_queued_emails[:1])

        mock_email_sender._smtp.sendmail.side_effect = OSError("Timeout")

        await processor.process_queue()

        # Email should still be in queue with incremented retry count
        queue_data = mock_queue_manager._read_queue()
        assert len(queue_data) == 1
        assert queue_data[0].retry_count == 1
        assert "Timeout" in queue_data[0].last_error


class TestAuthErrorsStopProcessing:
    """Test that authentication errors stop processing immediately."""

    @pytest.mark.asyncio
    async def test_auth_error_on_connect_raises(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """Auth failure during connect should raise and not send any email."""
        await mock_queue_manager.enqueue(sample_queued_emails)
        mock_email_sender.connect.side_effect = AuthenticationError(
            "Invalid credentials"
        )

        with pytest.raises(AuthenticationError):
            await processor.process_queue()

        mock_email_sender._smtp.sendmail.assert_not_called()

    @pytest.mark.asyncio
    async def test_auth_error_during_send_stops_batch(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """Auth failure during send should stop processing remaining emails."""
        await mock_queue_manager.enqueue(sample_queued_emails)

        # First email succeeds, second raises AuthenticationError
        original_send = processor._send_single_email
        call_idx = [0]

        def patched_send(email):
            call_idx[0] += 1
            if call_idx[0] == 2:
                raise AuthenticationError("Auth failed")
            original_send(email)

        processor._send_single_email = patched_send

        sent, failed = await processor.process_queue()

        # First email sent, second failed with auth, third not attempted
        assert sent == 1
        assert failed == 1
        # Third email (email-003) should still be in queue untouched
        # Second email (email-002) also remains (mark_failed incremented
        # retry from 1 to 2, still < MAX_RETRIES=3)
        pending = await mock_queue_manager.dequeue_pending()
        pending_ids = [e.id for e in pending]
        assert "email-003" in pending_ids
        # email-003 was never attempted, so retry_count stays 0
        carol = next(e for e in pending if e.id == "email-003")
        assert carol.retry_count == 0


class TestSummaryReturnsCounts:
    """Test that process_queue returns correct sent/failed counts."""

    @pytest.mark.asyncio
    async def test_all_succeed_returns_correct_count(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        sample_queued_emails: list,
    ) -> None:
        """When all emails succeed, sent count matches batch size."""
        await mock_queue_manager.enqueue(sample_queued_emails)

        sent, failed = await processor.process_queue()

        assert sent == 3
        assert failed == 0
        assert sent + failed == 3

    @pytest.mark.asyncio
    async def test_mixed_results_returns_correct_counts(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """Mixed success/failure returns correct split counts."""
        await mock_queue_manager.enqueue(sample_queued_emails)

        # First and third succeed, second fails
        call_count = [0]

        def sendmail_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError("Network error")

        mock_email_sender._smtp.sendmail.side_effect = sendmail_side_effect

        sent, failed = await processor.process_queue()

        assert sent == 2
        assert failed == 1

    @pytest.mark.asyncio
    async def test_all_fail_returns_correct_count(
        self,
        processor: QueueProcessor,
        mock_queue_manager: EmailQueueManager,
        mock_email_sender: MagicMock,
        sample_queued_emails: list,
    ) -> None:
        """When all emails fail, failed count matches batch size."""
        await mock_queue_manager.enqueue(sample_queued_emails)
        mock_email_sender._smtp.sendmail.side_effect = OSError("Network down")

        sent, failed = await processor.process_queue()

        assert sent == 0
        assert failed == 3


class TestStartStop:
    """Test start/stop lifecycle of QueueProcessor."""

    @pytest.mark.asyncio
    async def test_start_registers_polling_callback(
        self,
        processor: QueueProcessor,
        mock_network_monitor: MagicMock,
    ) -> None:
        """start() should call network_monitor.start_polling with callback."""
        await processor.start()

        mock_network_monitor.start_polling.assert_awaited_once()
        # Verify the callback is our _on_network_change method
        args = mock_network_monitor.start_polling.call_args
        assert args[0][0] == processor._on_network_change

    @pytest.mark.asyncio
    async def test_stop_cancels_polling(
        self,
        processor: QueueProcessor,
        mock_network_monitor: MagicMock,
    ) -> None:
        """stop() should call network_monitor.stop_polling."""
        await processor.stop()

        mock_network_monitor.stop_polling.assert_awaited_once()
