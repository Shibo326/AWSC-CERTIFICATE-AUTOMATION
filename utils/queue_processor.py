"""Queue processor that sends pending emails when network becomes available.

Integrates NetworkMonitor polling with EmailQueueManager to automatically
process queued emails upon detecting connectivity.
"""

import asyncio
import base64
import logging
import smtplib
from typing import Tuple

from utils.email_queue import EmailQueueManager
from utils.email_sender import EmailSender
from utils.exceptions import AuthenticationError
from utils.models import AttendeeRecord, EmailTemplate
from utils.network_monitor import NetworkMonitor

logger = logging.getLogger(__name__)


class QueueProcessor:
    """Processes email queue when network becomes available.

    Connects the NetworkMonitor's polling callback to queue processing.
    When network connectivity is detected, pending emails are sent via
    EmailSender. On success emails are marked sent; on socket/connection
    errors they are marked failed for retry. Auth failures stop processing
    immediately (credentials are wrong, retrying won't help).

    Attributes:
        queue_manager: The EmailQueueManager instance for queue operations.
        email_sender: The EmailSender instance for SMTP delivery.
        network_monitor: The NetworkMonitor instance for connectivity checks.
    """

    def __init__(
        self,
        queue_manager: EmailQueueManager,
        email_sender: EmailSender,
        network_monitor: NetworkMonitor,
    ) -> None:
        """Initialize the QueueProcessor.

        Args:
            queue_manager: Manages the persistent email queue.
            email_sender: Handles SMTP email delivery.
            network_monitor: Monitors network connectivity.
        """
        self.queue_manager = queue_manager
        self.email_sender = email_sender
        self.network_monitor = network_monitor
        self._processing: bool = False
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        """Start monitoring network and auto-processing queue.

        Begins polling via the NetworkMonitor. When network transitions
        to online, triggers queue processing automatically.
        """
        self._loop = asyncio.get_running_loop()
        await self.network_monitor.start_polling(self._on_network_change)

    async def stop(self) -> None:
        """Stop monitoring and processing."""
        await self.network_monitor.stop_polling()

    def _on_network_change(self, is_online: bool) -> None:
        """Callback invoked by NetworkMonitor when status changes.

        Args:
            is_online: True if network just became available, False if lost.
        """
        if is_online and not self._processing:
            if self._loop is not None and self._loop.is_running():
                self._loop.create_task(self._safe_process_queue())

    async def _safe_process_queue(self) -> None:
        """Wrapper that catches exceptions during queue processing."""
        try:
            sent, failed = await self.process_queue()
            if sent > 0 or failed > 0:
                logger.info(
                    "Queue processing complete: %d sent, %d failed",
                    sent,
                    failed,
                )
        except AuthenticationError:
            logger.error("Queue processing stopped due to authentication failure.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Queue processing error: %s", exc)
        finally:
            self._processing = False

    async def process_queue(self) -> Tuple[int, int]:
        """Process all pending emails. Returns (sent_count, failed_count).

        Dequeues pending emails and attempts delivery for each one.
        On successful send, marks the email as sent.
        On socket/connection errors, marks the email as failed with the error.
        On authentication failure, stops processing immediately.

        Returns:
            Tuple of (sent_count, failed_count) for the processing cycle.
        """
        self._processing = True
        sent_count = 0
        failed_count = 0

        pending = await self.queue_manager.dequeue_pending()
        if not pending:
            self._processing = False
            return (sent_count, failed_count)

        # Connect once for the batch
        try:
            self.email_sender.connect()
        except AuthenticationError as e:
            # Auth failure: stop processing entirely, don't retry
            logger.error(
                "Authentication failed, stopping queue processing: %s", e
            )
            self._processing = False
            raise
        except ConnectionError as e:
            # Network issue during connect — mark all as failed this cycle
            logger.warning(
                "Connection failed during queue processing: %s", e
            )
            for email in pending:
                await self.queue_manager.mark_failed(email.id, str(e))
                failed_count += 1
            self._processing = False
            return (sent_count, failed_count)

        try:
            for email in pending:
                try:
                    self._send_single_email(email)
                    await self.queue_manager.mark_sent(email.id)
                    sent_count += 1
                except AuthenticationError as e:
                    # Auth failure: stop processing, don't retry auth errors
                    logger.error(
                        "Authentication error during send, stopping: %s", e
                    )
                    await self.queue_manager.mark_failed(email.id, str(e))
                    failed_count += 1
                    break
                except (OSError, smtplib.SMTPException, ConnectionError) as e:
                    # Socket/connection errors: mark failed for retry
                    logger.warning(
                        "Delivery failed for %s: %s",
                        email.recipient_email,
                        e,
                    )
                    await self.queue_manager.mark_failed(email.id, str(e))
                    failed_count += 1
        finally:
            self.email_sender.disconnect()

        self._processing = False
        return (sent_count, failed_count)

    def _send_single_email(self, email) -> None:
        """Send a single queued email via the SMTP connection.

        Args:
            email: A QueuedEmail instance to deliver.

        Raises:
            AuthenticationError: If SMTP authentication fails.
            OSError: If a socket/network error occurs.
            smtplib.SMTPException: If an SMTP protocol error occurs.
        """
        # Decode certificate data
        cert_data = base64.b64decode(email.certificate_data_b64)

        # Build the attendee record and template for composition
        recipient = AttendeeRecord(
            name=email.attendee_name,
            email=email.recipient_email,
        )
        template = EmailTemplate(
            subject=email.subject,
            body=email.body,
        )

        # Compose the message using EmailSender's internal method
        msg = self.email_sender._compose_email(
            recipient=recipient,
            template=template,
            attachment_data=cert_data,
            attachment_filename=(
                f"{email.attendee_name.replace(' ', '_')}"
                f".{email.certificate_format}"
            ),
            file_ext=f".{email.certificate_format}",
        )

        # Send via the existing SMTP connection
        self.email_sender._smtp.sendmail(
            self.email_sender._credentials.sender_email,
            email.recipient_email,
            msg.as_string(),
        )
