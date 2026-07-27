"""Property-based tests for email queue operations.

# Feature: offline-cross-platform-app, Property 7: Offline queueing preserves entire batch
# Feature: offline-cross-platform-app, Property 8: Email queue serialization round-trip
# Feature: offline-cross-platform-app, Property 9: Socket failure increments retry count
"""

import asyncio
import base64
import json
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from utils.email_queue import EmailQueueManager, QueuedEmail


# Strategy for generating valid QueuedEmail objects
def _queued_email_strategy():
    """Strategy that generates valid QueuedEmail instances."""
    return st.builds(
        QueuedEmail,
        id=st.uuids().map(str),
        recipient_email=st.emails(),
        attendee_name=st.text(min_size=1, max_size=50),
        subject=st.text(min_size=1, max_size=100),
        body=st.text(min_size=1, max_size=200),
        certificate_data_b64=st.binary(min_size=10, max_size=100).map(
            lambda b: base64.b64encode(b).decode("ascii")
        ),
        certificate_format=st.sampled_from(["png", "jpg", "pdf"]),
        retry_count=st.integers(min_value=0, max_value=5),
        last_error=st.text(min_size=0, max_size=50),
        queued_at=st.just(datetime.now(timezone.utc).isoformat()),
        last_attempt_at=st.text(min_size=0, max_size=0),
    )


class TestProperty7QueueBatchPreservation:
    """Property 7: For batch of N emails queued offline, queue contains
    exactly N entries.

    **Validates: Requirements 4.2**
    """

    @given(
        batch_size=st.integers(min_value=1, max_value=100),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_enqueue_preserves_batch_count(
        self, batch_size: int, tmp_path: Path
    ) -> None:
        """Enqueuing N emails results in exactly N entries in queue."""
        # Feature: offline-cross-platform-app, Property 7: Offline queueing preserves entire batch
        data_dir = tmp_path / f"queue_{batch_size}"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        emails = [
            QueuedEmail(
                id=str(uuid.uuid4()),
                recipient_email=f"user{i}@example.com",
                attendee_name=f"User {i}",
                subject="Test Subject",
                body="Test Body",
                certificate_data_b64=base64.b64encode(b"cert_data").decode(),
                certificate_format="png",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            for i in range(batch_size)
        ]

        asyncio.run(manager.enqueue(emails))

        # Read back from file
        queue = manager._read_queue()
        assert len(queue) == batch_size, (
            f"Expected {batch_size} entries, got {len(queue)}"
        )

    @given(
        batch_size=st.integers(min_value=1, max_value=50),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_enqueue_appends_to_existing_queue(
        self, batch_size: int, tmp_path: Path
    ) -> None:
        """Enqueuing to a non-empty queue adds exactly N new entries."""
        # Feature: offline-cross-platform-app, Property 7: Offline queueing preserves entire batch
        data_dir = tmp_path / f"queue_append_{batch_size}"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        # Pre-populate with 3 emails
        initial_emails = [
            QueuedEmail(
                id=str(uuid.uuid4()),
                recipient_email=f"initial{i}@example.com",
                attendee_name=f"Initial {i}",
                subject="Subject",
                body="Body",
                certificate_data_b64=base64.b64encode(b"data").decode(),
                certificate_format="pdf",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            for i in range(3)
        ]
        asyncio.run(manager.enqueue(initial_emails))

        # Enqueue the new batch
        new_emails = [
            QueuedEmail(
                id=str(uuid.uuid4()),
                recipient_email=f"new{i}@example.com",
                attendee_name=f"New {i}",
                subject="New Subject",
                body="New Body",
                certificate_data_b64=base64.b64encode(b"new_data").decode(),
                certificate_format="png",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            for i in range(batch_size)
        ]
        asyncio.run(manager.enqueue(new_emails))

        queue = manager._read_queue()
        assert len(queue) == 3 + batch_size


class TestProperty8QueueSerializationRoundTrip:
    """Property 8: Serialize QueuedEmail list to JSON and back - all fields
    identical.

    **Validates: Requirements 4.4**
    """

    @given(
        emails=st.lists(
            _queued_email_strategy(),
            min_size=0,
            max_size=20,
        )
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_serialize_deserialize_preserves_all_fields(
        self, emails: list, tmp_path: Path
    ) -> None:
        """Serializing queue to JSON and reading back preserves all fields."""
        # Feature: offline-cross-platform-app, Property 8: Email queue serialization round-trip
        data_dir = tmp_path / "roundtrip"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        # Write directly using internal method
        manager._write_queue(emails)

        # Read back
        restored = manager._read_queue()

        assert len(restored) == len(emails), (
            f"Expected {len(emails)} emails, got {len(restored)}"
        )

        for original, loaded in zip(emails, restored):
            assert loaded.id == original.id
            assert loaded.recipient_email == original.recipient_email
            assert loaded.attendee_name == original.attendee_name
            assert loaded.subject == original.subject
            assert loaded.body == original.body
            assert loaded.certificate_data_b64 == original.certificate_data_b64
            assert loaded.certificate_format == original.certificate_format
            assert loaded.retry_count == original.retry_count
            assert loaded.last_error == original.last_error
            assert loaded.queued_at == original.queued_at
            assert loaded.last_attempt_at == original.last_attempt_at

    @given(
        emails=st.lists(
            _queued_email_strategy(),
            min_size=1,
            max_size=10,
        )
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_json_file_is_valid_json(
        self, emails: list, tmp_path: Path
    ) -> None:
        """The queue file is always valid JSON after writing."""
        # Feature: offline-cross-platform-app, Property 8: Email queue serialization round-trip
        data_dir = tmp_path / "json_valid"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        manager._write_queue(emails)

        queue_file = data_dir / "email_queue.json"
        assert queue_file.exists()

        # Must be parseable JSON
        data = json.loads(queue_file.read_text(encoding="utf-8"))
        assert "version" in data
        assert "emails" in data
        assert isinstance(data["emails"], list)
        assert len(data["emails"]) == len(emails)


class TestProperty9RetryCountIncrement:
    """Property 9: For email with retry_count < 3, mark_failed increments
    by exactly 1.

    **Validates: Requirements 4.6**
    """

    @given(
        initial_retry=st.integers(min_value=0, max_value=2),
        error_msg=st.text(min_size=1, max_size=100),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_mark_failed_increments_retry_by_one(
        self, initial_retry: int, error_msg: str, tmp_path: Path
    ) -> None:
        """mark_failed increments retry_count by exactly 1."""
        # Feature: offline-cross-platform-app, Property 9: Socket failure increments retry count
        data_dir = tmp_path / f"retry_{initial_retry}"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        email_id = str(uuid.uuid4())
        email = QueuedEmail(
            id=email_id,
            recipient_email="test@example.com",
            attendee_name="Test User",
            subject="Test",
            body="Body",
            certificate_data_b64=base64.b64encode(b"cert").decode(),
            certificate_format="png",
            retry_count=initial_retry,
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

        # Write the email to queue
        manager._write_queue([email])

        # Mark as failed
        asyncio.run(manager.mark_failed(email_id, error_msg))

        # Read back and verify
        queue = manager._read_queue()
        assert len(queue) == 1

        updated = queue[0]
        assert updated.retry_count == initial_retry + 1, (
            f"Expected retry_count {initial_retry + 1}, "
            f"got {updated.retry_count}"
        )
        assert updated.last_error == error_msg

    @given(
        initial_retry=st.integers(min_value=0, max_value=2),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_failed_email_stays_pending_if_under_max(
        self, initial_retry: int, tmp_path: Path
    ) -> None:
        """After mark_failed with retry < MAX_RETRIES, email stays pending."""
        # Feature: offline-cross-platform-app, Property 9: Socket failure increments retry count
        data_dir = tmp_path / f"pending_{initial_retry}"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        email_id = str(uuid.uuid4())
        email = QueuedEmail(
            id=email_id,
            recipient_email="test@example.com",
            attendee_name="Test User",
            subject="Subject",
            body="Body",
            certificate_data_b64=base64.b64encode(b"data").decode(),
            certificate_format="pdf",
            retry_count=initial_retry,
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

        manager._write_queue([email])
        asyncio.run(manager.mark_failed(email_id, "connection timeout"))

        # Email should still be in pending (retry_count < MAX_RETRIES)
        pending = asyncio.run(manager.dequeue_pending())
        new_retry = initial_retry + 1

        if new_retry < manager.MAX_RETRIES:
            assert len(pending) == 1, (
                f"Email with retry_count {new_retry} should still be pending"
            )
            assert pending[0].id == email_id
        else:
            # retry_count == MAX_RETRIES means permanently failed
            assert len(pending) == 0
