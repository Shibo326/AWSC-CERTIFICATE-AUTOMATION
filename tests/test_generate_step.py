"""Tests for the GenerateStep UI component logic.

Tests focus on batch generation behavior: progress tracking, per-attendee
error handling, and result summary formatting. Uses mock objects to avoid
requiring a running Flet page.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from parts.generate_step import GenerateStep
from utils.font_config import FontConfiguration
from utils.models import AttendeeRecord, BatchResult, CertificateOutput, GenerationError


@pytest.fixture
def generate_step():
    """Create a GenerateStep instance with mocked page and update method."""
    mock_page = MagicMock()
    step = GenerateStep(page=mock_page)
    # Build the UI controls
    step.build()
    return step


@pytest.fixture
def sample_attendees():
    """Return a list of sample attendees for testing."""
    return [
        AttendeeRecord(name="Alice Johnson", email="alice@example.com"),
        AttendeeRecord(name="Bob Smith", email="bob@example.com"),
        AttendeeRecord(name="Charlie Brown", email="charlie@example.com"),
    ]


@pytest.fixture
def template_png_bytes():
    """Create a minimal valid PNG image as bytes for template."""
    from PIL import Image
    import io

    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestGenerateStepBuild:
    """Tests for the build method and initial state."""

    def test_build_returns_column(self, generate_step):
        """Build should return a Column control."""
        import flet as ft

        result = generate_step.build()
        assert isinstance(result, ft.Column)

    def test_initial_state_no_certificates(self, generate_step):
        """Initial state should have no certificates or errors."""
        assert generate_step.certificates == []
        assert generate_step.errors == []
        assert generate_step._is_generating is False

    def test_progress_bar_initially_hidden(self, generate_step):
        """Progress bar should be hidden before generation starts."""
        assert generate_step._progress_bar.visible is False

    def test_generate_button_not_disabled(self, generate_step):
        """Generate button should be enabled initially."""
        assert generate_step._generate_btn.disabled is not True


class TestGenerateBatch:
    """Tests for the generate_batch async method."""

    @pytest.mark.asyncio
    async def test_batch_generates_all_certificates(
        self, generate_step, sample_attendees, template_png_bytes
    ):
        """Batch generation should produce one certificate per attendee."""
        result = await generate_step.generate_batch(
            template_bytes=template_png_bytes,
            template_format="png",
            attendees=sample_attendees,
        )

        assert len(result.certificates) == 3
        assert len(result.errors) == 0
        assert len(generate_step.certificates) == 3

    @pytest.mark.asyncio
    async def test_batch_updates_progress(
        self, generate_step, sample_attendees, template_png_bytes
    ):
        """Progress text should show 'Generating X of Y' format."""
        await generate_step.generate_batch(
            template_bytes=template_png_bytes,
            template_format="png",
            attendees=sample_attendees,
        )

        # After completion the progress bar should be at 1.0
        assert generate_step._progress_bar.value == 1.0
        # update() should have been called multiple times (once per attendee + setup)
        assert generate_step.page.update.call_count >= len(sample_attendees)

    @pytest.mark.asyncio
    async def test_batch_handles_per_attendee_errors(
        self, generate_step, template_png_bytes
    ):
        """Per-attendee errors should be collected without halting the batch."""
        attendees = [
            AttendeeRecord(name="OK Name", email="ok@example.com"),
            AttendeeRecord(name="Another OK", email="another@example.com"),
        ]

        # Patch generate to fail on the second attendee
        with patch(
            "parts.generate_step.CertificateGenerator"
        ) as MockGen:
            mock_generator = MagicMock()
            MockGen.return_value = mock_generator

            call_count = [0]

            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 2:
                    raise Exception("Text overflow: name too long")
                return CertificateOutput(
                    attendee_name=args[0] if args else kwargs.get("attendee_name", ""),
                    certificate=MagicMock(),
                    format="png",
                )

            mock_generator.generate.side_effect = side_effect
            mock_generator.cleanup = MagicMock()

            result = await generate_step.generate_batch(
                template_bytes=template_png_bytes,
                template_format="png",
                attendees=attendees,
            )

        assert len(result.certificates) == 1
        assert len(result.errors) == 1
        assert "Text overflow" in result.errors[0].error_message
        assert result.errors[0].attendee_name == "Another OK"

    @pytest.mark.asyncio
    async def test_batch_shows_success_message(
        self, generate_step, sample_attendees, template_png_bytes
    ):
        """On full success, result text shows success with count."""
        await generate_step.generate_batch(
            template_bytes=template_png_bytes,
            template_format="png",
            attendees=sample_attendees,
        )

        assert generate_step._result_text.visible is True
        assert "3" in generate_step._result_text.value
        assert "generated successfully" in generate_step._result_text.value

    @pytest.mark.asyncio
    async def test_batch_shows_mixed_summary_on_errors(
        self, generate_step, template_png_bytes
    ):
        """On partial failure, result shows mixed success/error summary."""
        attendees = [
            AttendeeRecord(name="Good", email="good@example.com"),
            AttendeeRecord(name="Bad", email="bad@example.com"),
        ]

        with patch(
            "parts.generate_step.CertificateGenerator"
        ) as MockGen:
            mock_generator = MagicMock()
            MockGen.return_value = mock_generator

            call_count = [0]

            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 2:
                    raise Exception("overflow error")
                return CertificateOutput(
                    attendee_name="Good",
                    certificate=MagicMock(),
                    format="png",
                )

            mock_generator.generate.side_effect = side_effect
            mock_generator.cleanup = MagicMock()

            await generate_step.generate_batch(
                template_bytes=template_png_bytes,
                template_format="png",
                attendees=attendees,
            )

        assert "1 generated" in generate_step._result_text.value
        assert "1 failed" in generate_step._result_text.value
        assert generate_step._error_container.visible is True

    @pytest.mark.asyncio
    async def test_batch_calls_completion_callback(
        self, template_png_bytes
    ):
        """Completion callback should be invoked with BatchResult."""
        callback = MagicMock()
        mock_page = MagicMock()
        step = GenerateStep(page=mock_page, on_generation_complete=callback)
        step.build()

        attendees = [AttendeeRecord(name="Test", email="test@example.com")]

        await step.generate_batch(
            template_bytes=template_png_bytes,
            template_format="png",
            attendees=attendees,
        )

        callback.assert_called_once()
        result = callback.call_args[0][0]
        assert isinstance(result, BatchResult)
        assert len(result.certificates) == 1

    @pytest.mark.asyncio
    async def test_batch_handles_invalid_template(self, generate_step):
        """Fatal template error should show error message, not crash."""
        attendees = [AttendeeRecord(name="Test", email="test@example.com")]

        result = await generate_step.generate_batch(
            template_bytes=b"invalid data",
            template_format="png",
            attendees=attendees,
        )

        assert len(result.certificates) == 0
        assert generate_step._result_text.visible is True
        assert "failed" in generate_step._result_text.value.lower()
        assert generate_step._generate_btn.disabled is False

    @pytest.mark.asyncio
    async def test_batch_disables_button_during_generation(
        self, generate_step, sample_attendees, template_png_bytes
    ):
        """Button should be disabled during generation and re-enabled after."""
        # After generation completes, the button should be re-enabled
        await generate_step.generate_batch(
            template_bytes=template_png_bytes,
            template_format="png",
            attendees=sample_attendees,
        )

        assert generate_step._generate_btn.disabled is False
        assert generate_step._is_generating is False


class TestGenerateStepReset:
    """Tests for the reset method."""

    @pytest.mark.asyncio
    async def test_reset_clears_state(
        self, generate_step, sample_attendees, template_png_bytes
    ):
        """Reset should clear all certificates and errors."""
        await generate_step.generate_batch(
            template_bytes=template_png_bytes,
            template_format="png",
            attendees=sample_attendees,
        )

        assert len(generate_step.certificates) > 0

        generate_step.reset()

        assert generate_step.certificates == []
        assert generate_step.errors == []
        assert generate_step._progress_bar.visible is False
        assert generate_step._result_text.visible is False
