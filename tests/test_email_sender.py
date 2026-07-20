"""Unit tests for EmailSender with mocked SMTP."""

from unittest.mock import MagicMock, patch
import smtplib

import pytest

from utils.email_sender import EmailSender, GMAIL_SMTP_HOST, GMAIL_SMTP_PORT
from utils.exceptions import AuthenticationError, ConfigurationError
from utils.models import (
    AttendeeRecord,
    EmailTemplate,
    GmailCredentials,
    SendResult,
)


@pytest.fixture
def mock_credentials():
    """Sample Gmail credentials for testing."""
    return GmailCredentials(
        sender_email="test@example.com",
        app_password="test-app-password"
    )


@pytest.fixture
def mock_template():
    """Sample email template for testing."""
    return EmailTemplate(
        subject="Certificate for {name}",
        body="Hi {name}, here is your certificate."
    )


@pytest.fixture
def mock_recipients():
    """Sample recipient list."""
    return [
        AttendeeRecord(name="Alice", email="alice@example.com"),
        AttendeeRecord(name="Bob", email="bob@example.com"),
        AttendeeRecord(name="Charlie", email="charlie@example.com"),
    ]


@pytest.fixture
def mock_cert_data():
    """Sample certificate bytes (fake PNG data)."""
    return [b"fake-cert-1", b"fake-cert-2", b"fake-cert-3"]


class TestEmailSenderCredentials:
    """Tests for credential loading."""

    def test_check_credentials_returns_false_when_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            result = EmailSender.check_credentials()
            assert result is False

    def test_check_credentials_returns_true_with_env_vars(self):
        env = {
            "CERTFLOW_EMAIL_SENDER": "test@example.com",
            "CERTFLOW_EMAIL_APP_PASSWORD": "test-password",
        }
        with patch.dict("os.environ", env):
            sender = EmailSender()
            creds = sender.load_credentials()
            assert creds.sender_email == "test@example.com"

    def test_load_credentials_raises_when_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            sender = EmailSender()
            with pytest.raises(ConfigurationError):
                sender.load_credentials()


class TestEmailSenderConnection:
    """Tests for SMTP connection."""

    @patch("smtplib.SMTP")
    def test_connect_success(self, mock_smtp_class, mock_credentials):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        sender = EmailSender(credentials=mock_credentials)
        sender.connect()

        mock_smtp_class.assert_called_once_with(
            GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30
        )
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with(
            mock_credentials.sender_email, mock_credentials.app_password
        )

    @patch("smtplib.SMTP")
    def test_connect_auth_failure(self, mock_smtp_class, mock_credentials):
        mock_smtp = MagicMock()
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"Auth failed"
        )
        mock_smtp_class.return_value = mock_smtp

        sender = EmailSender(credentials=mock_credentials)
        with pytest.raises(AuthenticationError):
            sender.connect()

    @patch("smtplib.SMTP")
    def test_connect_network_failure(self, mock_smtp_class, mock_credentials):
        mock_smtp_class.side_effect = OSError("Network unreachable")

        sender = EmailSender(credentials=mock_credentials)
        with pytest.raises(ConnectionError):
            sender.connect()


class TestEmailSenderBulkSend:
    """Tests for bulk email sending."""

    @patch("smtplib.SMTP")
    def test_send_bulk_all_success(
        self, mock_smtp_class, mock_credentials, mock_recipients,
        mock_cert_data, mock_template
    ):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        sender = EmailSender(credentials=mock_credentials)
        result = sender.send_bulk(
            recipients=mock_recipients,
            certificate_data=mock_cert_data,
            certificate_format="png",
            template=mock_template,
        )

        assert isinstance(result, SendResult)
        assert result.success_count == 3
        assert result.failure_count == 0

    @patch("smtplib.SMTP")
    def test_send_bulk_with_progress_callback(
        self, mock_smtp_class, mock_credentials, mock_recipients,
        mock_cert_data, mock_template
    ):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        sender = EmailSender(credentials=mock_credentials)
        sender.send_bulk(
            recipients=mock_recipients,
            certificate_data=mock_cert_data,
            certificate_format="png",
            template=mock_template,
            progress_callback=on_progress,
        )

        assert len(progress_calls) == 3
        assert progress_calls[0] == (1, 3)
        assert progress_calls[1] == (2, 3)
        assert progress_calls[2] == (3, 3)

    @patch("smtplib.SMTP")
    def test_send_bulk_partial_failure(
        self, mock_smtp_class, mock_credentials, mock_recipients,
        mock_cert_data, mock_template
    ):
        mock_smtp = MagicMock()
        mock_smtp.sendmail.side_effect = [
            None,
            smtplib.SMTPRecipientsRefused(
                {"bob@example.com": (550, b"rejected")}
            ),
            None,
        ]
        mock_smtp_class.return_value = mock_smtp

        sender = EmailSender(credentials=mock_credentials)
        result = sender.send_bulk(
            recipients=mock_recipients,
            certificate_data=mock_cert_data,
            certificate_format="png",
            template=mock_template,
        )

        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.success_count + result.failure_count == 3

    @patch("smtplib.SMTP")
    def test_send_result_completeness(
        self, mock_smtp_class, mock_credentials, mock_recipients,
        mock_cert_data, mock_template
    ):
        """Success + failures always equals total recipients."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        sender = EmailSender(credentials=mock_credentials)
        result = sender.send_bulk(
            recipients=mock_recipients,
            certificate_data=mock_cert_data,
            certificate_format="png",
            template=mock_template,
        )

        assert (
            result.success_count + result.failure_count == len(mock_recipients)
        )
