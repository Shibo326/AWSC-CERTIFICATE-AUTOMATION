"""Property-based tests for email queue operations.

# Feature: offline-cross-platform-app, Property 7: Offline queueing preserves entire batch
# Feature: offline-cross-platform-app, Property 8: Email queue serialization round-trip
# Feature: offline-cross-platform-app, Property 9: Socket failure increments retry count
"""

import asyncio
import base64
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from utils.email_queue import EmailQueueManager, QueuedEmail


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


class TestProperty7QueueCompleteness:
    """Property 7: For any batch size N queued offline, queue contains
    exactly N entries.

    **Validates: Requirements 4.2**
    """

    @given(batch_size=st.integers(min_value=1, max_value=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_enqueue_batch_has_exactly_n_entries(
        self, batch_size: int, tmp_path: Path
    ) -> None:
        """Enqueuing N emails results in exactly N entries in queue."""
        # Feature: offline-cross-platform-app, Property 7: Queue completeness
        data_dir = tmp_path / f"q_{batch_size}"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        emails = [
            QueuedEmail(
                id=str(uuid.uuid4()),
                recipient_email=f"user{i}@example.com",
                attendee_name=f"User {i}",
                subject="Subject",
                body="Body",
                certificate_data_b64=base64.b64encode(b"data").decode(),
                certificate_format="png",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            for i in range(batch_size)
        ]

        asyncio.run(manager.enqueue(emails))
        queue = manager._read_queue()
        assert len(queue) == batch_size


class TestProperty8QueueRoundTrip:
    """Property 8: Serializing then deserializing QueuedEmail list preserves
    all fields.

    **Validates: Requirements 4.4**
    """

    @given(
        emails=st.lists(_queued_email_strategy(), min_size=0, max_size=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_serialize_deserialize_preserves_fields(
        self, emails: list, tmp_path: Path
    ) -> None:
        """Write and read back preserves all QueuedEmail fields."""
        # Feature: offline-cross-platform-app, Property 8: Queue round-trip
        data_dir = tmp_path / "rt"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        manager._write_queue(emails)
        restored = manager._read_queue()

        assert len(restored) == len(emails)
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


class TestProperty9RetryIncrement:
    """Property 9: For any email with retry_count < 3, mark_failed
    increments by exactly 1.

    **Validates: Requirements 4.6**
    """

    @given(
        initial_retry=st.integers(min_value=0, max_value=2),
        error_msg=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_mark_failed_increments_by_one(
        self, initial_retry: int, error_msg: str, tmp_path: Path
    ) -> None:
        """mark_failed increments retry_count by exactly 1."""
        # Feature: offline-cross-platform-app, Property 9: Retry increment
        data_dir = tmp_path / f"r_{initial_retry}"
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = EmailQueueManager(data_dir)

        email_id = str(uuid.uuid4())
        email = QueuedEmail(
            id=email_id,
            recipient_email="test@example.com",
            attendee_name="Test",
            subject="S",
            body="B",
            certificate_data_b64=base64.b64encode(b"d").decode(),
            certificate_format="png",
            retry_count=initial_retry,
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

        manager._write_queue([email])
        asyncio.run(manager.mark_failed(email_id, error_msg))

        queue = manager._read_queue()
        assert len(queue) == 1
        assert queue[0].retry_count == initial_retry + 1
        assert queue[0].last_error == error_msg
