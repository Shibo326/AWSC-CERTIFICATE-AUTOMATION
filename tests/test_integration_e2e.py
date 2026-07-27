"""Integration tests for CertFlow end-to-end workflows.

Tests cover:
- End-to-end certificate generation with real PNG template from sample/
- Email queue lifecycle (enqueue offline -> mark_failed -> retry -> permanently fail)
- Credential store fallback (secure storage fails -> TOML file)
- App state persist -> restore round-trip
"""

import asyncio
import base64
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from utils.app_state_manager import AppStateManager
from utils.certificate_generator import CertificateGenerator
from utils.credential_store import (
    CredentialStore,
    _encode_value,
    _decode_value,
)
from utils.email_queue import EmailQueueManager, QueuedEmail
from utils.font_config import FontConfiguration
from utils.models import GmailCredentials


# Path to the real sample template
SAMPLE_TEMPLATE = Path(__file__).parent.parent / "sample" / "template_sample.png"


class TestEndToEndCertificateGeneration:
    """Integration test: end-to-end certificate generation with real template."""

    def test_generate_single_certificate_from_sample_png(self) -> None:
        """Generate a single certificate using the real sample PNG template."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        gen = CertificateGenerator(template_path=str(SAMPLE_TEMPLATE))
        try:
            output = gen.generate("Alice Johnson", vertical_position=50,
                                  vertical_as_percentage=True)

            assert output.attendee_name == "Alice Johnson"
            assert output.format == "png"
            assert isinstance(output.certificate, Image.Image)
            assert output.certificate.size[0] > 0
            assert output.certificate.size[1] > 0
        finally:
            gen.cleanup()

    def test_generate_batch_from_sample_png(self) -> None:
        """Generate a batch of certificates using the real sample template."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        names = ["Bob Smith", "Carol White", "Dave Brown", "Eve Green"]

        gen = CertificateGenerator(template_path=str(SAMPLE_TEMPLATE))
        try:
            result = gen.generate_batch(names, vertical_position=50,
                                        vertical_as_percentage=True)

            assert len(result.certificates) + len(result.errors) == len(names)
            # At least some should succeed with short names
            assert len(result.certificates) > 0
            for cert in result.certificates:
                assert cert.format == "png"
                assert isinstance(cert.certificate, Image.Image)
        finally:
            gen.cleanup()

    def test_generate_certificate_from_bytes(self) -> None:
        """Generate certificate from in-memory PNG bytes."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        template_bytes = SAMPLE_TEMPLATE.read_bytes()
        gen = CertificateGenerator(
            template_bytes=template_bytes, template_format="png"
        )
        try:
            output = gen.generate("Test User")
            assert output.format == "png"
            assert isinstance(output.certificate, Image.Image)
        finally:
            gen.cleanup()

    def test_output_format_matches_input_format(self) -> None:
        """Output format is always the same as input template format."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        gen = CertificateGenerator(template_path=str(SAMPLE_TEMPLATE))
        try:
            output = gen.generate("Format Test")
            assert output.format == "png"
        finally:
            gen.cleanup()

    def test_batch_with_custom_font_config(self) -> None:
        """Generate certificates with a custom font configuration."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        font_config = FontConfiguration(font_size=30, font_color=(255, 0, 0))
        gen = CertificateGenerator(
            template_path=str(SAMPLE_TEMPLATE), font_config=font_config
        )
        try:
            output = gen.generate("Red Font Test", vertical_position=60,
                                  vertical_as_percentage=True)
            assert output.attendee_name == "Red Font Test"
            assert output.format == "png"
        finally:
            gen.cleanup()


class TestEmailQueueLifecycle:
    """Integration test: email queue full lifecycle.

    Enqueue offline -> mark_failed -> retry -> permanently fail.
    """

    def test_full_queue_lifecycle(self, tmp_path: Path) -> None:
        """Full lifecycle: enqueue, fail, retry, permanently fail."""
        manager = EmailQueueManager(tmp_path)

        # 1. Enqueue 3 emails (simulating offline)
        emails = [
            QueuedEmail(
                id=str(uuid.uuid4()),
                recipient_email=f"attendee{i}@example.com",
                attendee_name=f"Attendee {i}",
                subject="Your Certificate",
                body=f"Hi Attendee {i}, here is your cert.",
                certificate_data_b64=base64.b64encode(
                    b"fake_cert_png_data"
                ).decode(),
                certificate_format="png",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            for i in range(3)
        ]

        asyncio.run(manager.enqueue(emails))

        # Verify all 3 are queued
        status = asyncio.run(manager.get_status())
        assert status.pending_count == 3
        assert status.failed_count == 0

        # 2. First attempt fails for all 3
        for email in emails:
            asyncio.run(manager.mark_failed(email.id, "Connection timeout"))

        status = asyncio.run(manager.get_status())
        assert status.pending_count == 3  # retry_count=1, still < 3
        assert status.failed_count == 0

        # 3. Second attempt fails
        for email in emails:
            asyncio.run(manager.mark_failed(email.id, "Network unreachable"))

        status = asyncio.run(manager.get_status())
        assert status.pending_count == 3  # retry_count=2, still < 3
        assert status.failed_count == 0

        # 4. Third attempt fails -> permanently failed
        for email in emails:
            asyncio.run(manager.mark_failed(email.id, "SMTP error"))

        status = asyncio.run(manager.get_status())
        assert status.pending_count == 0
        assert status.failed_count == 3

        # 5. Verify permanently failed list
        failed = asyncio.run(manager.get_permanently_failed())
        assert len(failed) == 3
        for f in failed:
            assert f.retry_count == 3
            assert f.last_error == "SMTP error"

    def test_partial_success_partial_failure(self, tmp_path: Path) -> None:
        """Some emails succeed, some exhaust retries."""
        manager = EmailQueueManager(tmp_path)

        email_success = QueuedEmail(
            id=str(uuid.uuid4()),
            recipient_email="success@example.com",
            attendee_name="Success User",
            subject="Cert",
            body="Here you go",
            certificate_data_b64=base64.b64encode(b"data").decode(),
            certificate_format="pdf",
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        email_fail = QueuedEmail(
            id=str(uuid.uuid4()),
            recipient_email="fail@example.com",
            attendee_name="Fail User",
            subject="Cert",
            body="Here you go",
            certificate_data_b64=base64.b64encode(b"data").decode(),
            certificate_format="pdf",
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

        asyncio.run(manager.enqueue([email_success, email_fail]))

        # Mark success as sent
        asyncio.run(manager.mark_sent(email_success.id))

        # Fail the other 3 times
        for _ in range(3):
            asyncio.run(manager.mark_failed(email_fail.id, "timeout"))

        status = asyncio.run(manager.get_status())
        assert status.pending_count == 0
        assert status.failed_count == 1

        # Only failed email remains
        queue = manager._read_queue()
        assert len(queue) == 1
        assert queue[0].id == email_fail.id

    def test_queue_persists_across_manager_instances(
        self, tmp_path: Path
    ) -> None:
        """Queue data persists between different manager instances."""
        manager1 = EmailQueueManager(tmp_path)

        email = QueuedEmail(
            id=str(uuid.uuid4()),
            recipient_email="persist@example.com",
            attendee_name="Persist User",
            subject="Subject",
            body="Body",
            certificate_data_b64=base64.b64encode(b"cert").decode(),
            certificate_format="png",
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

        asyncio.run(manager1.enqueue([email]))

        # Create a new manager instance pointing to same dir
        manager2 = EmailQueueManager(tmp_path)
        pending = asyncio.run(manager2.dequeue_pending())
        assert len(pending) == 1
        assert pending[0].id == email.id
        assert pending[0].attendee_name == "Persist User"


class TestCredentialStoreFallback:
    """Integration test: credential store fallback when secure storage fails."""

    @pytest.mark.asyncio
    async def test_store_fallback_on_secure_storage_failure(
        self, tmp_path: Path
    ) -> None:
        """When secure storage raises, credentials fall back to TOML file."""
        page = MagicMock()
        page.client_storage = MagicMock()
        page.client_storage.set_async = AsyncMock(
            side_effect=RuntimeError("Secure storage unavailable")
        )
        page.client_storage.get_async = AsyncMock(
            side_effect=RuntimeError("Secure storage unavailable")
        )

        store = CredentialStore(page)

        test_dir = tmp_path / ".certflow"
        test_file = test_dir / "credentials.toml"

        with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
             patch("utils.credential_store.FALLBACK_FILE", test_file):
            # Store should fall back to TOML
            await store.store("testuser@gmail.com", "abcdefghijklmnop")

            # File should exist
            assert test_file.exists()

            # Load should also fall back to TOML
            result = await store.load()

        assert result is not None
        assert result.sender_email == "testuser@gmail.com"
        assert result.app_password == "abcdefghijklmnop"

    @pytest.mark.asyncio
    async def test_load_from_secure_storage_when_available(self) -> None:
        """When secure storage works, credentials are loaded from it."""
        page = MagicMock()
        page.client_storage = MagicMock()

        stored_values = {
            "certflow_email": "user@gmail.com",
            "certflow_app_password": "abcdefghijklmnop",
        }
        page.client_storage.get_async = AsyncMock(
            side_effect=lambda key: stored_values.get(key)
        )

        store = CredentialStore(page)
        result = await store.load()

        assert result is not None
        assert result.sender_email == "user@gmail.com"
        assert result.app_password == "abcdefghijklmnop"

    @pytest.mark.asyncio
    async def test_is_configured_via_fallback(self, tmp_path: Path) -> None:
        """is_configured returns True if fallback file has valid creds."""
        page = MagicMock()
        page.client_storage = MagicMock()
        page.client_storage.get_async = AsyncMock(
            side_effect=RuntimeError("unavailable")
        )

        store = CredentialStore(page)

        test_dir = tmp_path / ".certflow"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "credentials.toml"

        encoded_email = _encode_value("test@gmail.com")
        encoded_password = _encode_value("abcdefghijklmnop")
        content = (
            "[email]\n"
            f'sender = "{encoded_email}"\n'
            f'app_password = "{encoded_password}"\n'
        )
        test_file.write_text(content, encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            result = await store.is_configured()

        assert result is True

    @pytest.mark.asyncio
    async def test_clear_removes_fallback_file(self, tmp_path: Path) -> None:
        """clear() removes both secure storage keys and fallback file."""
        page = MagicMock()
        page.client_storage = MagicMock()
        page.client_storage.remove_async = AsyncMock()

        store = CredentialStore(page)

        test_file = tmp_path / "credentials.toml"
        test_file.write_text("[email]\n", encoding="utf-8")

        with patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.clear()

        assert not test_file.exists()


class TestAppStatePersistRestore:
    """Integration test: app state persist -> restore round-trip."""

    @pytest.mark.asyncio
    async def test_full_state_persist_and_restore(self) -> None:
        """Save all settings, then restore_session returns matching state."""
        page = MagicMock()
        storage_dict: dict = {}

        async def set_async(key: str, value: str) -> None:
            storage_dict[key] = value

        async def get_async(key: str):
            return storage_dict.get(key)

        async def remove_async(key: str) -> None:
            storage_dict.pop(key, None)

        page.client_storage = MagicMock()
        page.client_storage.set_async = AsyncMock(side_effect=set_async)
        page.client_storage.get_async = AsyncMock(side_effect=get_async)
        page.client_storage.remove_async = AsyncMock(side_effect=remove_async)

        manager = AppStateManager(page)

        # Save settings
        await manager.save("font_family", "Montserrat")
        await manager.save("font_size", "72")
        await manager.save("font_color", "#ff5733")
        await manager.save("vertical_position", "65")
        await manager.save("email_subject", "Congratulations {name}!")
        await manager.save("email_body", "Dear {name},\n\nWell done!")

        # Restore session
        state, warnings = await manager.restore_session()

        assert state.font_family == "Montserrat"
        assert state.font_size == 72
        assert state.font_color == "#ff5733"
        assert state.vertical_position == 65
        assert state.email_subject == "Congratulations {name}!"
        assert state.email_body == "Dear {name},\n\nWell done!"
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_restore_with_missing_file_path_warns(self) -> None:
        """Restore session warns about missing file paths."""
        page = MagicMock()
        storage_dict: dict = {
            "certflow_template_path": "/nonexistent/path/template.png",
            "certflow_font_family": "Arial",
            "certflow_font_size": "40",
            "certflow_font_color": "#000000",
            "certflow_vertical_position": "50",
            "certflow_email_subject": "Test",
            "certflow_email_body": "Body",
        }

        async def get_async(key: str):
            return storage_dict.get(key)

        async def remove_async(key: str) -> None:
            storage_dict.pop(key, None)

        page.client_storage = MagicMock()
        page.client_storage.get_async = AsyncMock(side_effect=get_async)
        page.client_storage.remove_async = AsyncMock(side_effect=remove_async)
        page.client_storage.set_async = AsyncMock()

        manager = AppStateManager(page)
        state, warnings = await manager.restore_session()

        # Should warn about the missing template
        assert len(warnings) >= 1
        assert "not found" in warnings[0].lower() or "template" in warnings[0].lower()
        # Template path should be cleared
        assert state.template_path is None

    @pytest.mark.asyncio
    async def test_restore_with_empty_storage_returns_defaults(self) -> None:
        """Restoring from empty storage returns all default values."""
        page = MagicMock()
        page.client_storage = MagicMock()
        page.client_storage.get_async = AsyncMock(return_value=None)
        page.client_storage.remove_async = AsyncMock()

        manager = AppStateManager(page)
        state, warnings = await manager.restore_session()

        assert state.font_family == "Arial"
        assert state.font_size == 40
        assert state.font_color == "#000000"
        assert state.vertical_position == 50
        assert "Certificate" in state.email_subject
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_clear_all_resets_state(self) -> None:
        """clear_all removes all persisted keys."""
        page = MagicMock()
        storage_dict: dict = {}

        async def set_async(key: str, value: str) -> None:
            storage_dict[key] = value

        async def get_async(key: str):
            return storage_dict.get(key)

        async def remove_async(key: str) -> None:
            storage_dict.pop(key, None)

        page.client_storage = MagicMock()
        page.client_storage.set_async = AsyncMock(side_effect=set_async)
        page.client_storage.get_async = AsyncMock(side_effect=get_async)
        page.client_storage.remove_async = AsyncMock(side_effect=remove_async)

        manager = AppStateManager(page)

        # Save some values
        await manager.save("font_family", "Roboto")
        await manager.save("font_size", "50")

        # Clear all
        await manager.clear_all()

        # All should be None
        loaded = await manager.load_all()
        for key in AppStateManager.KEYS:
            assert loaded[key] is None
