"""Email queue with JSON persistence for offline-to-online delivery.

Provides a persistent queue for emails that cannot be sent immediately
(e.g., when the network is unavailable). Emails are stored as JSON and
retried automatically when connectivity is restored.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class QueuedEmail:
    """An email pending delivery in the offline queue.

    Attributes:
        id: Unique identifier (UUID).
        recipient_email: Recipient's email address.
        attendee_name: Name of the attendee.
        subject: Email subject line.
        body: Email body text.
        certificate_data_b64: Base64-encoded certificate attachment.
        certificate_format: Output format ('png', 'jpg', or 'pdf').
        retry_count: Number of failed delivery attempts.
        last_error: Error message from most recent failure.
        queued_at: ISO 8601 timestamp when email was queued.
        last_attempt_at: ISO 8601 timestamp of last send attempt.
    """

    id: str
    recipient_email: str
    attendee_name: str
    subject: str
    body: str
    certificate_data_b64: str
    certificate_format: str
    retry_count: int = 0
    last_error: str = ""
    queued_at: str = ""
    last_attempt_at: str = ""

    def __post_init__(self) -> None:
        """Auto-generate id and queued_at if not provided."""
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.queued_at:
            self.queued_at = datetime.now(timezone.utc).isoformat()


@dataclass
class QueueStatus:
    """Current state of the email queue.

    Attributes:
        pending_count: Number of emails still awaiting delivery.
        failed_count: Number of emails that exhausted all retries.
        last_attempt: ISO 8601 timestamp of last send attempt, or None.
    """

    pending_count: int
    failed_count: int
    last_attempt: Optional[str] = None


class EmailQueueManager:
    """Manages persistent email queue with retry logic.

    Emails are stored as a JSON file in the app data directory.
    The queue supports enqueue, dequeue, mark-sent, and mark-failed
    operations with automatic retry counting.

    Attributes:
        MAX_RETRIES: Maximum number of delivery attempts before
            marking an email as permanently failed.
    """

    MAX_RETRIES = 3
    _QUEUE_FILENAME = "email_queue.json"
    _QUEUE_VERSION = 1

    def __init__(self, data_dir: Path) -> None:
        """Initialize the queue manager.

        Args:
            data_dir: Path to the app data directory where the
                queue JSON file will be stored.
        """
        self._data_dir = data_dir
        self._queue_file = data_dir / self._QUEUE_FILENAME

    def _get_queue_path(self) -> Path:
        """Return the path to the queue JSON file."""
        return self._queue_file

    def _read_queue(self) -> List[QueuedEmail]:
        """Read and parse the queue file.

        Returns:
            List of QueuedEmail objects from the persisted file.
            Returns an empty list if the file doesn't exist or is
            corrupted.
        """
        queue_path = self._get_queue_path()
        if not queue_path.exists():
            return []

        try:
            data = json.loads(queue_path.read_text(encoding="utf-8"))
            emails_data = data.get("emails", [])
            return [QueuedEmail(**email_dict) for email_dict in emails_data]
        except (json.JSONDecodeError, TypeError, KeyError):
            return []

    def _write_queue(self, emails: List[QueuedEmail]) -> None:
        """Write the queue to the JSON file.

        Creates the data directory if it doesn't exist.

        Args:
            emails: List of QueuedEmail objects to persist.
        """
        self._data_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self._QUEUE_VERSION,
            "emails": [asdict(email) for email in emails],
        }
        self._queue_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    async def enqueue(self, emails: List[QueuedEmail]) -> None:
        """Add emails to the persistent queue.

        Sets the queued_at timestamp if not already set and generates
        an ID if the email doesn't have one.

        Args:
            emails: List of QueuedEmail objects to add to the queue.
        """
        current_queue = self._read_queue()
        now = datetime.now(timezone.utc).isoformat()

        for email in emails:
            if not email.id:
                email.id = str(uuid.uuid4())
            if not email.queued_at:
                email.queued_at = now
            current_queue.append(email)

        self._write_queue(current_queue)

    async def dequeue_pending(self) -> List[QueuedEmail]:
        """Get all emails with retry_count < MAX_RETRIES.

        Returns:
            List of QueuedEmail objects that are still eligible
            for delivery attempts.
        """
        current_queue = self._read_queue()
        return [
            email for email in current_queue
            if email.retry_count < self.MAX_RETRIES
        ]

    async def mark_sent(self, email_id: str) -> None:
        """Remove a successfully sent email from the queue.

        Args:
            email_id: The unique ID of the email to remove.
        """
        current_queue = self._read_queue()
        updated_queue = [
            email for email in current_queue if email.id != email_id
        ]
        self._write_queue(updated_queue)

    async def mark_failed(self, email_id: str, error: str) -> None:
        """Record a delivery failure for an email.

        Increments the retry count, sets the last_error message,
        and updates the last_attempt_at timestamp.

        Args:
            email_id: The unique ID of the failed email.
            error: Description of the failure.
        """
        current_queue = self._read_queue()
        now = datetime.now(timezone.utc).isoformat()

        for email in current_queue:
            if email.id == email_id:
                email.retry_count += 1
                email.last_error = error
                email.last_attempt_at = now
                break

        self._write_queue(current_queue)

    async def get_status(self) -> QueueStatus:
        """Return current queue status counts.

        Returns:
            QueueStatus with pending count, failed count, and
            last attempt timestamp.
        """
        current_queue = self._read_queue()
        pending_count = sum(
            1 for e in current_queue if e.retry_count < self.MAX_RETRIES
        )
        failed_count = sum(
            1 for e in current_queue if e.retry_count >= self.MAX_RETRIES
        )

        # Find the most recent attempt timestamp
        last_attempt: Optional[str] = None
        for email in current_queue:
            if email.last_attempt_at:
                if last_attempt is None or email.last_attempt_at > last_attempt:
                    last_attempt = email.last_attempt_at

        return QueueStatus(
            pending_count=pending_count,
            failed_count=failed_count,
            last_attempt=last_attempt,
        )

    async def get_permanently_failed(self) -> List[QueuedEmail]:
        """Return all emails that exhausted retries.

        Returns:
            List of QueuedEmail objects with retry_count >= MAX_RETRIES.
        """
        current_queue = self._read_queue()
        return [
            email for email in current_queue
            if email.retry_count >= self.MAX_RETRIES
        ]
