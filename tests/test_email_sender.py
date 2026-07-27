"""Unit tests for EmailSender with mocked SMTP."""

from unittest.mock import MagicMock, patch
from pathlib import Path
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

    def test_check_credentials_returns_false_when_missing(self, tmp_path):
        with patch.dict(
            "os.environ",
            {"CERTFLOW_EMAIL_SENDER": "", "CERTFLOW_EMAIL_APP_PASSWORD": ""},
        ):
            with patch.object(
                EmailSender, "_load_from_toml", return_value=None
            ):
                with patch("pathlib.Path.home", return_value=tmp_path):
                    result = EmailSender.check_credentials()
                    assert result is False

    def test_check_credentials_returns_true_with_env_vars(self):
        env = {
            "CERTFLOW_EMAIL_SENDER": "test@example.com",
            "CERTFLOW_EMAIL_APP_PASSWORD": "test-password",
        }
        with patch.dict("os.environ", env):
            with patch.object(
                EmailSender, "_load_from_toml", return_value=None
            ):
                sender = EmailSender()
                creds = sender.load_credentials()
                assert creds.sender_email == "test@example.com"
                assert creds.app_password == "test-password"

    def test_load_credentials_raises_when_missing(self, tmp_path):
        with patch.dict(
            "os.environ",
            {"CERTFLOW_EMAIL_SENDER": "", "CERTFLOW_EMAIL_APP_PASSWORD": ""},
        ):
            with patch("pathlib.Path.home", return_value=tmp_path):
                with patch.object(
                    EmailSender, "_load_from_toml", return_value=None
                ):
                    sender = EmailSender()
                    with pytest.raises(ConfigurationError):
                        sender.load_credentials()

    def test_load_credentials_from_app_directory_toml(self, tmp_path):
        """Credentials found in app-directory credentials.toml."""
        cred_file = tmp_path / "credentials.toml"
        cred_file.write_text(
            '[email]\nsender = "app@example.com"\n'
            'app_password = "apppassword12345"\n'
        )
        sender = EmailSender()
        creds = sender._load_from_toml(cred_file)
        assert creds is not None
        assert creds.sender_email == "app@example.com"
        assert creds.app_password == "apppassword12345"

    def test_load_credentials_from_home_directory_toml(self, tmp_path):
        """Credentials found in ~/.certflow/credentials.toml."""
        certflow_dir = tmp_path / ".certflow"
        certflow_dir.mkdir()
        cred_file = certflow_dir / "credentials.toml"
        cred_file.write_text(
            '[email]\nsender = "home@example.com"\n'
            'app_password = "homepassword1234"\n'
        )
        sender = EmailSender()
        creds = sender._load_from_toml(cred_file)
        assert creds is not None
        assert creds.sender_email == "home@example.com"
        assert creds.app_password == "homepassword1234"

    def test_load_from_toml_returns_none_when_file_missing(self, tmp_path):
        """Returns None when the TOML file does not exist."""
        missing = tmp_path / "nonexistent.toml"
        result = EmailSender._load_from_toml(missing)
        assert result is None

    def test_load_from_toml_returns_none_for_empty_fields(self, tmp_path):
        """Returns None when email section exists but fields are empty."""
        cred_file = tmp_path / "credentials.toml"
        cred_file.write_text('[email]\nsender = ""\napp_password = ""\n')
        result = EmailSender._load_from_toml(cred_file)
        assert result is None

    def test_credential_fallback_order(self, tmp_path):
        """App directory credentials.toml takes precedence over env vars."""
        cred_file = tmp_path / "credentials.toml"
        cred_file.write_text(
            '[email]\nsender = "file@example.com"\n'
            'app_password = "filepassword1234"\n'
        )
        env = {
            "CERTFLOW_EMAIL_SENDER": "env@example.com",
            "CERTFLOW_EMAIL_APP_PASSWORD": "envpassword12345",
        }
        with patch.dict("os.environ", env):
            sender = EmailSender()
            creds = sender._load_from_toml(cred_file)
            assert creds.sender_email == "file@example.com"


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
