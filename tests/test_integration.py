"""Comprehensive integration tests for CertFlow.

Tests cover:
- End-to-end: load template -> parse CSV -> generate batch -> write files -> verify output
- Email queue lifecycle: enqueue -> come online -> process -> verify sent
- Credential store fallback: secure storage fails -> TOML fallback works
- App state: save all -> simulate restart -> restore -> verify
"""

import asyncio
import base64
import io
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from utils.app_state_manager import AppStateManager, PersistedState
from utils.certificate_generator import CertificateGenerator
from utils.credential_store import (
    CredentialStore,
    _encode_value,
    _decode_value,
)
from utils.csv_parser import CSVParser
from utils.email_queue import EmailQueueManager, QueuedEmail
from utils.font_config import FontConfiguration, get_assets_root
from utils.models import (
    AttendeeRecord,
    BatchResult,
    CertificateOutput,
    GmailCredentials,
)
from utils.platform_storage import PlatformStorage


# Paths to real sample files
PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_DIR = PROJECT_ROOT / "sample"
SAMPLE_TEMPLATE = SAMPLE_DIR / "template_sample.png"
SAMPLE_CSV = SAMPLE_DIR / "attendees_sample.csv"
SAMPLE_XLSX = SAMPLE_DIR / "attendees_sample.xlsx"
ASSETS_DIR = get_assets_root()


class TestEndToEndPipeline:
    """Integration test: load template -> parse CSV -> generate batch -> write files."""

    def test_full_pipeline_png_template_csv_attendees(
        self, tmp_path: Path
    ) -> None:
        """Complete pipeline: PNG template + CSV -> generate -> write to disk."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")
        if not SAMPLE_CSV.exists():
            pytest.skip("Sample CSV not available")

        # Step 1: Load template
        template_bytes = SAMPLE_TEMPLATE.read_bytes()
        gen = CertificateGenerator(
            template_bytes=template_bytes, template_format="png"
        )

        try:
            # Step 2: Parse CSV
            parser = CSVParser()
            csv_content = SAMPLE_CSV.read_text(encoding="utf-8")
            parse_result = parser.parse(csv_content)
            assert len(parse_result.records) > 0, "No valid attendees parsed"

            # Step 3: Generate batch
            names = [r.name for r in parse_result.records]
            batch_result = gen.generate_batch(
                names, vertical_position=50, vertical_as_percentage=True
            )

            # Verify batch completeness: certs + errors = total
            total = len(batch_result.certificates) + len(batch_result.errors)
            assert total == len(names)
            assert len(batch_result.certificates) > 0

            # Step 4: Write files to disk
            storage = PlatformStorage()
            output_dir = tmp_path / "output"
            output_dir.mkdir()

            filenames_written: set = set()
            for cert in batch_result.certificates:
                ext = f".{cert.format}"
                sanitized = storage.sanitize_filename(cert.attendee_name, ext)
                deduped = storage.deduplicate_filename(sanitized, filenames_written)
                filenames_written.add(deduped)

                # Convert to bytes
                if isinstance(cert.certificate, Image.Image):
                    buf = io.BytesIO()
                    save_fmt = "PNG" if cert.format == "png" else "JPEG"
                    cert.certificate.save(buf, format=save_fmt)
                    cert_bytes = buf.getvalue()
                else:
                    cert_bytes = cert.certificate

                (output_dir / deduped).write_bytes(cert_bytes)

            # Step 5: Verify output
            written_files = list(output_dir.iterdir())
            assert len(written_files) == len(batch_result.certificates)

            for f in written_files:
                assert f.stat().st_size > 0, f"Empty file: {f.name}"
                assert f.suffix in (".png", ".jpg", ".pdf")

        finally:
            gen.cleanup()

    def test_pipeline_with_custom_font_and_position(
        self, tmp_path: Path
    ) -> None:
        """Pipeline with custom font config produces valid certificates."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        font_path = ASSETS_DIR / "fonts" / "Roboto-Regular.ttf"
        if not font_path.exists():
            font_path = ASSETS_DIR / "fonts" / "Arial.ttf"
        if not font_path.exists():
            pytest.skip("No bundled fonts available")

        font_config = FontConfiguration(
            font_path=str(font_path),
            font_size=30,
            font_color=(0, 0, 128),  # Navy blue
        )

        gen = CertificateGenerator(
            template_path=str(SAMPLE_TEMPLATE), font_config=font_config
        )
        try:
            result = gen.generate_batch(
                ["Alice", "Bob", "Carol"],
                vertical_position=70,
                vertical_as_percentage=True,
            )
            assert len(result.certificates) == 3
            for cert in result.certificates:
                assert cert.format == "png"
                assert isinstance(cert.certificate, Image.Image)
                # Image should have same dimensions as template
                template_img = Image.open(SAMPLE_TEMPLATE)
                assert cert.certificate.size == template_img.size
        finally:
            gen.cleanup()

    def test_pipeline_batch_errors_do_not_halt_generation(self) -> None:
        """A very long name that overflows should not halt the rest."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        gen = CertificateGenerator(template_path=str(SAMPLE_TEMPLATE))
        try:
            # Mix of normal and extremely long names
            names = [
                "Short Name",
                "A" * 5000,  # Likely to overflow
                "Another Normal",
            ]
            result = gen.generate_batch(
                names, vertical_position=50, vertical_as_percentage=True
            )
            # Total should always equal input count
            assert (
                len(result.certificates) + len(result.errors) == len(names)
            )
        finally:
            gen.cleanup()

    def test_pipeline_output_format_matches_input(self) -> None:
        """Output format always matches input template format."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        # PNG template -> PNG output
        gen = CertificateGenerator(template_path=str(SAMPLE_TEMPLATE))
        try:
            output = gen.generate("Test User")
            assert output.format == "png"
        finally:
            gen.cleanup()

    def test_pipeline_xlsx_attendees(self) -> None:
        """Pipeline works with XLSX attendee file."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")
        if not SAMPLE_XLSX.exists():
            pytest.skip("Sample XLSX not available")

        parser = CSVParser()
        xlsx_bytes = SAMPLE_XLSX.read_bytes()
        parse_result = parser.parse_xlsx(xlsx_bytes)
        assert len(parse_result.records) > 0

        gen = CertificateGenerator(template_path=str(SAMPLE_TEMPLATE))
        try:
            names = [r.name for r in parse_result.records]
            result = gen.generate_batch(
                names, vertical_position=50, vertical_as_percentage=True
            )
            assert len(result.certificates) + len(result.errors) == len(names)
        finally:
            gen.cleanup()

    def test_pipeline_write_certificate_via_platform_storage(
        self, tmp_path: Path
    ) -> None:
        """write_certificate method works end-to-end."""
        if not SAMPLE_TEMPLATE.exists():
            pytest.skip("Sample template not available")

        gen = CertificateGenerator(template_path=str(SAMPLE_TEMPLATE))
        try:
            output = gen.generate(
                "Storage Test", vertical_position=50, vertical_as_percentage=True
            )

            storage = PlatformStorage()
            buf = io.BytesIO()
            output.certificate.save(buf, format="PNG")
            cert_bytes = buf.getvalue()

            with patch.object(
                storage, "get_output_directory", return_value=tmp_path
            ):
                error = asyncio.run(
                    storage.write_certificate("Storage_Test.png", cert_bytes)
                )

            assert error is None
            written = tmp_path / "Storage_Test.png"
            assert written.exists()
            assert written.stat().st_size > 0

            # Verify it's a valid PNG
            img = Image.open(written)
            assert img.size[0] > 0
        finally:
            gen.cleanup()


class TestEmailQueueLifecycleIntegration:
    """Integration test: email queue enqueue -> come online -> process -> verify."""

    def test_enqueue_offline_then_process_online(
        self, tmp_path: Path
    ) -> None:
        """Enqueue while offline, then process when online."""
        manager = EmailQueueManager(tmp_path)

        # Simulate offline: enqueue 5 emails
        emails = [
            QueuedEmail(
                id=str(uuid.uuid4()),
                recipient_email=f"attendee{i}@example.com",
                attendee_name=f"Attendee {i}",
                subject="Your Certificate",
                body=f"Hi Attendee {i}, here is your certificate.",
                certificate_data_b64=base64.b64encode(
                    b"fake_png_cert_data"
                ).decode(),
                certificate_format="png",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            for i in range(5)
        ]

        asyncio.run(manager.enqueue(emails))

        # Verify queue state
        status = asyncio.run(manager.get_status())
        assert status.pending_count == 5
        assert status.failed_count == 0

        # Simulate "coming online" -> process pending
        pending = asyncio.run(manager.dequeue_pending())
        assert len(pending) == 5

        # Mark 3 as sent, 2 as failed
        for email in pending[:3]:
            asyncio.run(manager.mark_sent(email.id))

        for email in pending[3:]:
            asyncio.run(manager.mark_failed(email.id, "Connection refused"))

        # Check status after processing
        status = asyncio.run(manager.get_status())
        assert status.pending_count == 2  # retry_count=1, still < 3
        assert status.failed_count == 0

    def test_retry_exhaustion_marks_permanently_failed(
        self, tmp_path: Path
    ) -> None:
        """After 3 retries, emails are marked permanently failed."""
        manager = EmailQueueManager(tmp_path)

        email_id = str(uuid.uuid4())
        email = QueuedEmail(
            id=email_id,
            recipient_email="fail@example.com",
            attendee_name="Fail User",
            subject="Cert",
            body="Hello",
            certificate_data_b64=base64.b64encode(b"data").decode(),
            certificate_format="pdf",
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

        asyncio.run(manager.enqueue([email]))

        # Fail 3 times
        for attempt in range(3):
            asyncio.run(
                manager.mark_failed(email_id, f"Attempt {attempt + 1} failed")
            )

        # Should now be permanently failed
        status = asyncio.run(manager.get_status())
        assert status.pending_count == 0
        assert status.failed_count == 1

        failed = asyncio.run(manager.get_permanently_failed())
        assert len(failed) == 1
        assert failed[0].retry_count == 3
        assert "Attempt 3" in failed[0].last_error

    def test_queue_survives_manager_restart(self, tmp_path: Path) -> None:
        """Queue data persists when a new manager instance is created."""
        manager1 = EmailQueueManager(tmp_path)

        emails = [
            QueuedEmail(
                id=str(uuid.uuid4()),
                recipient_email="persist@example.com",
                attendee_name="Persist User",
                subject="Subject",
                body="Body",
                certificate_data_b64=base64.b64encode(b"cert").decode(),
                certificate_format="png",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            for _ in range(3)
        ]
        asyncio.run(manager1.enqueue(emails))

        # "Restart" - new instance from same directory
        manager2 = EmailQueueManager(tmp_path)
        pending = asyncio.run(manager2.dequeue_pending())
        assert len(pending) == 3

        # Mark one as sent via new instance
        asyncio.run(manager2.mark_sent(pending[0].id))
        pending = asyncio.run(manager2.dequeue_pending())
        assert len(pending) == 2

    def test_mixed_success_and_permanent_failure(
        self, tmp_path: Path
    ) -> None:
        """Process batch: some succeed, some permanently fail after 3 retries."""
        manager = EmailQueueManager(tmp_path)

        email_ok = QueuedEmail(
            id=str(uuid.uuid4()),
            recipient_email="ok@example.com",
            attendee_name="OK User",
            subject="S",
            body="B",
            certificate_data_b64=base64.b64encode(b"d").decode(),
            certificate_format="png",
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        email_bad = QueuedEmail(
            id=str(uuid.uuid4()),
            recipient_email="bad@example.com",
            attendee_name="Bad User",
            subject="S",
            body="B",
            certificate_data_b64=base64.b64encode(b"d").decode(),
            certificate_format="png",
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

        asyncio.run(manager.enqueue([email_ok, email_bad]))

        # Send OK email successfully
        asyncio.run(manager.mark_sent(email_ok.id))

        # Fail bad email 3 times
        for _ in range(3):
            asyncio.run(manager.mark_failed(email_bad.id, "SMTP error"))

        status = asyncio.run(manager.get_status())
        assert status.pending_count == 0
        assert status.failed_count == 1

        # Verify only failed email remains in queue
        queue = manager._read_queue()
        assert len(queue) == 1
        assert queue[0].id == email_bad.id
        assert queue[0].retry_count == 3


class TestCredentialStoreFallbackIntegration:
    """Integration test: credential store fallback when secure storage fails."""

    @pytest.mark.asyncio
    async def test_full_fallback_cycle_store_load_clear(
        self, tmp_path: Path
    ) -> None:
        """Complete fallback cycle: store -> load -> verify -> clear."""
        page = MagicMock()
        page.client_storage = MagicMock()
        # Simulate secure storage always failing
        page.client_storage.set_async = AsyncMock(
            side_effect=RuntimeError("Platform secure storage unavailable")
        )
        page.client_storage.get_async = AsyncMock(
            side_effect=RuntimeError("Platform secure storage unavailable")
        )
        page.client_storage.remove_async = AsyncMock(
            side_effect=RuntimeError("Platform secure storage unavailable")
        )

        store = CredentialStore(page)
        test_dir = tmp_path / ".certflow"
        test_file = test_dir / "credentials.toml"

        with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
             patch("utils.credential_store.FALLBACK_FILE", test_file):
            # Store credentials (should fallback to TOML)
            await store.store("testuser@gmail.com", "abcdefghijklmnop")
            assert test_file.exists()

            # Load credentials from fallback
            creds = await store.load()
            assert creds is not None
            assert creds.sender_email == "testuser@gmail.com"
            assert creds.app_password == "abcdefghijklmnop"

            # is_configured should return True
            assert await store.is_configured() is True

            # Clear should remove the file
            await store.clear()
            assert not test_file.exists()

            # After clearing, load returns None
            creds = await store.load()
            assert creds is None

    @pytest.mark.asyncio
    async def test_fallback_file_not_plaintext(self, tmp_path: Path) -> None:
        """Credentials in fallback file are encoded, not plaintext."""
        page = MagicMock()
        page.client_storage = MagicMock()
        page.client_storage.set_async = AsyncMock(
            side_effect=RuntimeError("unavailable")
        )

        store = CredentialStore(page)
        test_dir = tmp_path / ".certflow"
        test_file = test_dir / "credentials.toml"

        with patch("utils.credential_store.FALLBACK_DIR", test_dir), \
             patch("utils.credential_store.FALLBACK_FILE", test_file):
            await store.store("secret@gmail.com", "mysecretpassword")

            content = test_file.read_text(encoding="utf-8")
            assert "secret@gmail.com" not in content
            assert "mysecretpassword" not in content
            assert "[email]" in content

    @pytest.mark.asyncio
    async def test_secure_storage_works_when_available(self) -> None:
        """When secure storage works, TOML fallback is not used."""
        page = MagicMock()
        stored = {}

        async def mock_set(key, value):
            stored[key] = value

        async def mock_get(key):
            return stored.get(key)

        page.client_storage = MagicMock()
        page.client_storage.set_async = AsyncMock(side_effect=mock_set)
        page.client_storage.get_async = AsyncMock(side_effect=mock_get)

        store = CredentialStore(page)
        await store.store("user@gmail.com", "abcdefghijklmnop")

        creds = await store.load()
        assert creds is not None
        assert creds.sender_email == "user@gmail.com"
        assert creds.app_password == "abcdefghijklmnop"

    @pytest.mark.asyncio
    async def test_validation_then_store_then_load(
        self, tmp_path: Path
    ) -> None:
        """Validate credentials -> store -> load -> verify full cycle."""
        page = MagicMock()
        stored = {}

        async def mock_set(key, value):
            stored[key] = value

        async def mock_get(key):
            return stored.get(key)

        page.client_storage = MagicMock()
        page.client_storage.set_async = AsyncMock(side_effect=mock_set)
        page.client_storage.get_async = AsyncMock(side_effect=mock_get)

        store = CredentialStore(page)

        # Validate first
        email = "certflow.test@gmail.com"
        password = "abcd efgh ijkl mnop"

        assert store.validate_email(email) is None
        assert store.validate_app_password(password) is None

        # Store the stripped password
        stripped_password = password.replace(" ", "")
        await store.store(email, stripped_password)

        # Load and verify
        creds = await store.load()
        assert creds.sender_email == email
        assert creds.app_password == stripped_password


class TestAppStatePersistRestoreIntegration:
    """Integration test: app state save all -> simulate restart -> restore."""

    @pytest.mark.asyncio
    async def test_save_all_restart_restore_verify(self) -> None:
        """Save all settings, create new manager (simulate restart), verify."""
        # Shared storage backend
        storage_dict: dict = {}

        def _create_page():
            page = MagicMock()

            async def set_async(key, value):
                storage_dict[key] = value

            async def get_async(key):
                return storage_dict.get(key)

            async def remove_async(key):
                storage_dict.pop(key, None)

            page.client_storage = MagicMock()
            page.client_storage.set_async = AsyncMock(side_effect=set_async)
            page.client_storage.get_async = AsyncMock(side_effect=get_async)
            page.client_storage.remove_async = AsyncMock(
                side_effect=remove_async
            )
            return page

        # Session 1: Save settings
        page1 = _create_page()
        manager1 = AppStateManager(page1)

        await manager1.save("font_family", "Montserrat")
        await manager1.save("font_size", "72")
        await manager1.save("font_color", "#ff5733")
        await manager1.save("vertical_position", "65")
        await manager1.save("email_subject", "Congratulations {name}!")
        await manager1.save("email_body", "Dear {name},\n\nGreat work!")

        # Session 2: Simulate app restart (new manager, same backing store)
        page2 = _create_page()
        manager2 = AppStateManager(page2)

        state, warnings = await manager2.restore_session()

        assert state.font_family == "Montserrat"
        assert state.font_size == 72
        assert state.font_color == "#ff5733"
        assert state.vertical_position == 65
        assert state.email_subject == "Congratulations {name}!"
        assert state.email_body == "Dear {name},\n\nGreat work!"
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_stale_file_path_detected_on_restore(self) -> None:
        """Restoring with a non-existent file path produces a warning."""
        storage_dict: dict = {
            "certflow_template_path": "/does/not/exist/template.png",
            "certflow_font_family": "Arial",
            "certflow_font_size": "40",
            "certflow_font_color": "#000000",
            "certflow_vertical_position": "50",
            "certflow_email_subject": "Hello",
            "certflow_email_body": "World",
        }

        page = MagicMock()

        async def get_async(key):
            return storage_dict.get(key)

        async def remove_async(key):
            storage_dict.pop(key, None)

        page.client_storage = MagicMock()
        page.client_storage.get_async = AsyncMock(side_effect=get_async)
        page.client_storage.remove_async = AsyncMock(side_effect=remove_async)
        page.client_storage.set_async = AsyncMock()

        manager = AppStateManager(page)
        state, warnings = await manager.restore_session()

        assert len(warnings) >= 1
        assert "not found" in warnings[0].lower()
        assert state.template_path is None

    @pytest.mark.asyncio
    async def test_corrupted_state_returns_defaults(self) -> None:
        """Corrupted/unreadable storage returns defaults without error."""
        page = MagicMock()
        page.client_storage = MagicMock()
        page.client_storage.get_async = AsyncMock(
            side_effect=RuntimeError("storage corrupted")
        )
        page.client_storage.remove_async = AsyncMock()

        manager = AppStateManager(page)
        state, warnings = await manager.restore_session()

        # Should get defaults
        assert state.font_family == "Arial"
        assert state.font_size == 40
        assert state.font_color == "#000000"
        assert state.vertical_position == 50
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_clear_all_then_restore_gives_defaults(self) -> None:
        """After clear_all, restore_session returns all defaults."""
        storage_dict: dict = {}

        page = MagicMock()

        async def set_async(key, value):
            storage_dict[key] = value

        async def get_async(key):
            return storage_dict.get(key)

        async def remove_async(key):
            storage_dict.pop(key, None)

        page.client_storage = MagicMock()
        page.client_storage.set_async = AsyncMock(side_effect=set_async)
        page.client_storage.get_async = AsyncMock(side_effect=get_async)
        page.client_storage.remove_async = AsyncMock(side_effect=remove_async)

        manager = AppStateManager(page)

        # Save then clear
        await manager.save("font_family", "Roboto")
        await manager.save("font_size", "80")
        await manager.clear_all()

        # Restore should give defaults
        state, warnings = await manager.restore_session()
        assert state.font_family == "Arial"
        assert state.font_size == 40

    @pytest.mark.asyncio
    async def test_partial_settings_restore_uses_defaults_for_missing(
        self,
    ) -> None:
        """If only some settings are saved, missing ones use defaults."""
        storage_dict: dict = {}

        page = MagicMock()

        async def set_async(key, value):
            storage_dict[key] = value

        async def get_async(key):
            return storage_dict.get(key)

        async def remove_async(key):
            storage_dict.pop(key, None)

        page.client_storage = MagicMock()
        page.client_storage.set_async = AsyncMock(side_effect=set_async)
        page.client_storage.get_async = AsyncMock(side_effect=get_async)
        page.client_storage.remove_async = AsyncMock(side_effect=remove_async)

        manager = AppStateManager(page)

        # Only save font_family
        await manager.save("font_family", "GreatVibes")

        state, warnings = await manager.restore_session()
        assert state.font_family == "GreatVibes"
        # Rest should be defaults
        assert state.font_size == 40
        assert state.font_color == "#000000"
        assert state.vertical_position == 50
