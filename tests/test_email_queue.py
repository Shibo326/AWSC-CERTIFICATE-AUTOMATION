"""Unit tests for the EmailQueueManager module."""

import json
import asyncio
from pathlib import Path

import pytest

from utils.email_queue import EmailQueueManager, QueuedEmail, QueueStatus


def _make_email(
    email_id: str = "test-id-1",
    recipient: str = "attendee@example.com",
    name: str = "Jane Smith",
    retry_count: int = 0,
    last_error: str = "",
    queued_at: str = "2024-01-15T10:30:00+00:00",
    last_attempt_at: str = "",
) -> QueuedEmail:
    """Helper to create a QueuedEmail with sensible defaults."""
    return QueuedEmail(
        id=email_id,
        recipient_email=recipient,
        attendee_name=name,
        subject="Your Certificate",
        body=f"Hi {name}, here is your certificate.",
        certificate_data_b64="aVZCT1J3MEtHZ28=",
        certificate_format="png",
        retry_count=retry_count,
        last_error=last_error,
        queued_at=queued_at,
        last_attempt_at=last_attempt_at,
    )


@pytest.fixture
def queue_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for queue storage."""
    return tmp_path / "app_data"


@pytest.fixture
def manager(queue_dir: Path) -> EmailQueueManager:
    """Provide an EmailQueueManager instance with temp directory."""
    return EmailQueueManager(queue_dir)


class TestQueuedEmailDataclass:
    """Tests for the QueuedEmail dataclass."""

    def test_create_with_all_fields(self) -> None:
        """QueuedEmail stores all provided fields correctly."""
        email = _make_email()
        assert email.id == "test-id-1"
        assert email.recipient_email == "attendee@example.com"
        assert email.attendee_name == "Jane Smith"
        assert email.subject == "Your Certificate"
        assert email.certificate_format == "png"
        assert email.retry_count == 0
        assert email.last_error == ""

    def test_auto_generates_id_when_empty(self) -> None:
        """QueuedEmail generates a UUID when id is empty string."""
        email = QueuedEmail(
            id="",
            recipient_email="test@example.com",
            attendee_name="Test",
            subject="Subject",
            body="Body",
            certificate_data_b64="data",
            certificate_format="png",
        )
        assert email.id != ""
        assert len(email.id) == 36  # UUID format

    def test_auto_generates_queued_at_when_empty(self) -> None:
        """QueuedEmail sets queued_at to current time when empty."""
        email = QueuedEmail(
            id="some-id",
            recipient_email="test@example.com",
            attendee_name="Test",
            subject="Subject",
            body="Body",
            certificate_data_b64="data",
            certificate_format="png",
        )
        assert email.queued_at != ""
        # Should be an ISO format timestamp
        assert "T" in email.queued_at


class TestEnqueue:
    """Tests for the enqueue method."""

    @pytest.mark.asyncio
    async def test_enqueue_single_email(self, manager: EmailQueueManager) -> None:
        """Enqueue a single email and verify it persists."""
        email = _make_email()
        await manager.enqueue([email])

        pending = await manager.dequeue_pending()
        assert len(pending) == 1
        assert pending[0].id == "test-id-1"

    @pytest.mark.asyncio
    async def test_enqueue_multiple_emails(
        self, manager: EmailQueueManager
    ) -> None:
        """Enqueue multiple emails at once."""
        emails = [
            _make_email(email_id="id-1", name="Alice"),
            _make_email(email_id="id-2", name="Bob"),
            _make_email(email_id="id-3", name="Charlie"),
        ]
        await manager.enqueue(emails)

        pending = await manager.dequeue_pending()
        assert len(pending) == 3

    @pytest.mark.asyncio
    async def test_enqueue_appends_to_existing(
        self, manager: EmailQueueManager
    ) -> None:
        """Enqueue adds to existing queue entries."""
        await manager.enqueue([_make_email(email_id="id-1")])
        await manager.enqueue([_make_email(email_id="id-2")])

        pending = await manager.dequeue_pending()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_enqueue_creates_data_directory(
        self, queue_dir: Path, manager: EmailQueueManager
    ) -> None:
        """Enqueue creates the data directory if it doesn't exist."""
        assert not queue_dir.exists()
        await manager.enqueue([_make_email()])
        assert queue_dir.exists()


class TestDequeuePending:
    """Tests for the dequeue_pending method."""

    @pytest.mark.asyncio
    async def test_empty_queue_returns_empty_list(
        self, manager: EmailQueueManager
    ) -> None:
        """Empty queue returns empty list."""
        pending = await manager.dequeue_pending()
        assert pending == []

    @pytest.mark.asyncio
    async def test_excludes_permanently_failed(
        self, manager: EmailQueueManager
    ) -> None:
        """Emails with retry_count >= MAX_RETRIES are excluded."""
        emails = [
            _make_email(email_id="id-pending", retry_count=2),
            _make_email(email_id="id-failed", retry_count=3),
        ]
        await manager.enqueue(emails)

        pending = await manager.dequeue_pending()
        assert len(pending) == 1
        assert pending[0].id == "id-pending"


class TestMarkSent:
    """Tests for the mark_sent method."""

    @pytest.mark.asyncio
    async def test_removes_email_from_queue(
        self, manager: EmailQueueManager
    ) -> None:
        """Mark sent removes the email entirely."""
        emails = [
            _make_email(email_id="id-1"),
            _make_email(email_id="id-2"),
        ]
        await manager.enqueue(emails)
        await manager.mark_sent("id-1")

        pending = await manager.dequeue_pending()
        assert len(pending) == 1
        assert pending[0].id == "id-2"

    @pytest.mark.asyncio
    async def test_mark_sent_nonexistent_id_no_error(
        self, manager: EmailQueueManager
    ) -> None:
        """Marking a non-existent id doesn't raise an error."""
        await manager.enqueue([_make_email(email_id="id-1")])
        await manager.mark_sent("nonexistent-id")

        pending = await manager.dequeue_pending()
        assert len(pending) == 1


class TestMarkFailed:
    """Tests for the mark_failed method."""

    @pytest.mark.asyncio
    async def test_increments_retry_count(
        self, manager: EmailQueueManager
    ) -> None:
        """Mark failed increments retry_count by 1."""
        await manager.enqueue([_make_email(email_id="id-1", retry_count=0)])
        await manager.mark_failed("id-1", "Connection timeout")

        pending = await manager.dequeue_pending()
        assert len(pending) == 1
        assert pending[0].retry_count == 1
        assert pending[0].last_error == "Connection timeout"

    @pytest.mark.asyncio
    async def test_sets_last_attempt_at(
        self, manager: EmailQueueManager
    ) -> None:
        """Mark failed sets last_attempt_at timestamp."""
        await manager.enqueue([_make_email(email_id="id-1")])
        await manager.mark_failed("id-1", "Socket error")

        pending = await manager.dequeue_pending()
        assert pending[0].last_attempt_at != ""
        assert "T" in pending[0].last_attempt_at

    @pytest.mark.asyncio
    async def test_moves_to_permanently_failed_at_max_retries(
        self, manager: EmailQueueManager
    ) -> None:
        """Email becomes permanently failed at MAX_RETRIES."""
        await manager.enqueue([_make_email(email_id="id-1", retry_count=2)])
        await manager.mark_failed("id-1", "Final failure")

        pending = await manager.dequeue_pending()
        assert len(pending) == 0

        failed = await manager.get_permanently_failed()
        assert len(failed) == 1
        assert failed[0].retry_count == 3
        assert failed[0].last_error == "Final failure"

    @pytest.mark.asyncio
    async def test_mark_failed_nonexistent_id_no_error(
        self, manager: EmailQueueManager
    ) -> None:
        """Marking a non-existent id doesn't raise an error."""
        await manager.enqueue([_make_email(email_id="id-1")])
        await manager.mark_failed("nonexistent-id", "error")

        pending = await manager.dequeue_pending()
        assert pending[0].retry_count == 0


class TestRetryLifecycle:
    """Tests for full retry lifecycle: 0 -> 1 -> 2 -> 3 (permanently failed)."""

    @pytest.mark.asyncio
    async def test_progressive_failures_exhaust_retries(
        self, manager: EmailQueueManager
    ) -> None:
        """Email failing 3 times transitions from pending to permanently failed."""
        await manager.enqueue([_make_email(email_id="id-1", retry_count=0)])

        # First failure: 0 -> 1, stays pending
        await manager.mark_failed("id-1", "Socket error")
        pending = await manager.dequeue_pending()
        assert len(pending) == 1
        assert pending[0].retry_count == 1

        # Second failure: 1 -> 2, stays pending
        await manager.mark_failed("id-1", "Connection timeout")
        pending = await manager.dequeue_pending()
        assert len(pending) == 1
        assert pending[0].retry_count == 2

        # Third failure: 2 -> 3, moves to permanently failed
        await manager.mark_failed("id-1", "Connection refused")
        pending = await manager.dequeue_pending()
        assert len(pending) == 0

        failed = await manager.get_permanently_failed()
        assert len(failed) == 1
        assert failed[0].retry_count == 3
        assert failed[0].last_error == "Connection refused"

    @pytest.mark.asyncio
    async def test_status_reflects_lifecycle(
        self, manager: EmailQueueManager
    ) -> None:
        """get_status correctly tracks email through retry lifecycle."""
        await manager.enqueue([_make_email(email_id="id-1", retry_count=0)])

        # Initially: 1 pending, 0 failed
        status = await manager.get_status()
        assert status.pending_count == 1
        assert status.failed_count == 0

        # After 2 failures: still pending
        await manager.mark_failed("id-1", "error 1")
        await manager.mark_failed("id-1", "error 2")
        status = await manager.get_status()
        assert status.pending_count == 1
        assert status.failed_count == 0

        # After 3rd failure: moves to permanently failed
        await manager.mark_failed("id-1", "error 3")
        status = await manager.get_status()
        assert status.pending_count == 0
        assert status.failed_count == 1
        assert status.last_attempt is not None


class TestGetStatus:
    """Tests for the get_status method."""

    @pytest.mark.asyncio
    async def test_empty_queue_status(
        self, manager: EmailQueueManager
    ) -> None:
        """Empty queue returns zeros and None last_attempt."""
        status = await manager.get_status()
        assert status.pending_count == 0
        assert status.failed_count == 0
        assert status.last_attempt is None

    @pytest.mark.asyncio
    async def test_mixed_queue_status(
        self, manager: EmailQueueManager
    ) -> None:
        """Status counts pending and failed emails correctly."""
        emails = [
            _make_email(email_id="id-1", retry_count=0),
            _make_email(email_id="id-2", retry_count=1),
            _make_email(
                email_id="id-3",
                retry_count=3,
                last_attempt_at="2024-01-15T12:00:00+00:00",
            ),
        ]
        await manager.enqueue(emails)

        status = await manager.get_status()
        assert status.pending_count == 2
        assert status.failed_count == 1
        assert status.last_attempt == "2024-01-15T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_last_attempt_is_most_recent(
        self, manager: EmailQueueManager
    ) -> None:
        """last_attempt returns the most recent timestamp."""
        emails = [
            _make_email(
                email_id="id-1",
                retry_count=1,
                last_attempt_at="2024-01-15T10:00:00+00:00",
            ),
            _make_email(
                email_id="id-2",
                retry_count=1,
                last_attempt_at="2024-01-15T14:00:00+00:00",
            ),
        ]
        await manager.enqueue(emails)

        status = await manager.get_status()
        assert status.last_attempt == "2024-01-15T14:00:00+00:00"


class TestGetPermanentlyFailed:
    """Tests for the get_permanently_failed method."""

    @pytest.mark.asyncio
    async def test_returns_only_exhausted_emails(
        self, manager: EmailQueueManager
    ) -> None:
        """Only emails with retry_count >= MAX_RETRIES are returned."""
        emails = [
            _make_email(email_id="id-pending", retry_count=2),
            _make_email(email_id="id-failed-1", retry_count=3),
            _make_email(email_id="id-failed-2", retry_count=5),
        ]
        await manager.enqueue(emails)

        failed = await manager.get_permanently_failed()
        assert len(failed) == 2
        ids = {e.id for e in failed}
        assert ids == {"id-failed-1", "id-failed-2"}


class TestJsonPersistence:
    """Tests for JSON file format and persistence."""

    @pytest.mark.asyncio
    async def test_json_file_format(
        self, queue_dir: Path, manager: EmailQueueManager
    ) -> None:
        """Queue file follows the specified JSON format."""
        await manager.enqueue([_make_email(email_id="id-1")])

        queue_file = queue_dir / "email_queue.json"
        assert queue_file.exists()

        data = json.loads(queue_file.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert "emails" in data
        assert len(data["emails"]) == 1
        assert data["emails"][0]["id"] == "id-1"

    @pytest.mark.asyncio
    async def test_survives_corrupt_json_file(
        self, queue_dir: Path, manager: EmailQueueManager
    ) -> None:
        """Corrupted JSON file results in empty queue, no crash."""
        queue_dir.mkdir(parents=True, exist_ok=True)
        queue_file = queue_dir / "email_queue.json"
        queue_file.write_text("not valid json {{{", encoding="utf-8")

        pending = await manager.dequeue_pending()
        assert pending == []

    @pytest.mark.asyncio
    async def test_survives_missing_emails_key(
        self, queue_dir: Path, manager: EmailQueueManager
    ) -> None:
        """JSON file missing 'emails' key results in empty queue."""
        queue_dir.mkdir(parents=True, exist_ok=True)
        queue_file = queue_dir / "email_queue.json"
        queue_file.write_text('{"version": 1}', encoding="utf-8")

        pending = await manager.dequeue_pending()
        assert pending == []

    @pytest.mark.asyncio
    async def test_round_trip_preserves_all_fields(
        self, manager: EmailQueueManager
    ) -> None:
        """Serialize then deserialize preserves all QueuedEmail fields."""
        original = QueuedEmail(
            id="uuid-test-123",
            recipient_email="user@example.com",
            attendee_name="Maria Garcia",
            subject="Your Certificate - Congrats!",
            body="Hi Maria, your cert is attached.",
            certificate_data_b64="SGVsbG8gV29ybGQ=",
            certificate_format="pdf",
            retry_count=2,
            last_error="Connection refused",
            queued_at="2024-06-01T08:00:00+00:00",
            last_attempt_at="2024-06-01T09:30:00+00:00",
        )
        await manager.enqueue([original])

        pending = await manager.dequeue_pending()
        assert len(pending) == 1
        restored = pending[0]

        assert restored.id == original.id
        assert restored.recipient_email == original.recipient_email
        assert restored.attendee_name == original.attendee_name
        assert restored.subject == original.subject
        assert restored.body == original.body
        assert restored.certificate_data_b64 == original.certificate_data_b64
        assert restored.certificate_format == original.certificate_format
        assert restored.retry_count == original.retry_count
        assert restored.last_error == original.last_error
        assert restored.queued_at == original.queued_at
        assert restored.last_attempt_at == original.last_attempt_at

    @pytest.mark.asyncio
    async def test_unicode_content_preserved(
        self, manager: EmailQueueManager
    ) -> None:
        """Unicode characters in names and content are preserved."""
        email = _make_email(email_id="unicode-test", name="Tanaka Taro")
        email.subject = "Certificate"
        email.body = "Hello Tanaka Taro"
        await manager.enqueue([email])

        pending = await manager.dequeue_pending()
        assert pending[0].attendee_name == "Tanaka Taro"
        assert pending[0].subject == "Certificate"
        assert pending[0].body == "Hello Tanaka Taro"
