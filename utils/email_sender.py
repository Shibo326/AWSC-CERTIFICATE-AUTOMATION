"""Gmail SMTP email sender for CertFlow bulk certificate delivery."""

import logging
import os
import smtplib
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from utils.exceptions import AuthenticationError, ConfigurationError
from utils.models import (
    AttendeeRecord,
    DeliveryFailure,
    EmailTemplate,
    GmailCredentials,
    SendResult,
)

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587
GMAIL_DAILY_LIMIT_WARNING = 450
MAX_ATTACHMENT_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class EmailSender:
    """Manages Gmail SMTP connections and bulk email sending with attachments.

    Handles credential loading, SMTP connection lifecycle, email composition,
    progress reporting, and error recovery during batch operations.
    """

    def __init__(self, credentials: Optional[GmailCredentials] = None) -> None:
        """Initialize with optional credentials.

        Args:
            credentials: Gmail credentials. If None, auto-loads from config.
        """
        self._credentials = credentials
        self._smtp: Optional[smtplib.SMTP] = None

    def load_credentials(self) -> GmailCredentials:
        """Load Gmail credentials from config file, secrets.toml, or env vars.

        Precedence:
            1. .streamlit/secrets.toml (Streamlit Cloud compatible)
            2. credentials.toml in app directory (desktop/mobile)
            3. Environment variables (CERTFLOW_EMAIL_SENDER, CERTFLOW_EMAIL_APP_PASSWORD)

        Returns:
            GmailCredentials with sender email and app password.

        Raises:
            ConfigurationError: If no valid credentials found in any source.
        """
        # Try .streamlit/secrets.toml first (Streamlit compatibility)
        try:
            import streamlit as st
            secrets = st.secrets.get("email", {})
            sender = secrets.get("sender", "")
            app_password = secrets.get("app_password", "")
            if sender and app_password:
                return GmailCredentials(
                    sender_email=sender, app_password=app_password
                )
        except Exception:
            pass

        # Try local credentials.toml (for desktop/mobile builds)
        try:
            import tomllib
            cred_paths = [
                Path("credentials.toml"),
                Path.home() / ".certflow" / "credentials.toml",
            ]
            for cred_path in cred_paths:
                if cred_path.exists():
                    with open(cred_path, "rb") as f:
                        config = tomllib.load(f)
                    email_config = config.get("email", {})
                    sender = email_config.get("sender", "")
                    app_password = email_config.get("app_password", "")
                    if sender and app_password:
                        return GmailCredentials(
                            sender_email=sender, app_password=app_password
                        )
        except Exception:
            pass

        # Fallback to environment variables
        sender = os.environ.get("CERTFLOW_EMAIL_SENDER", "")
        app_password = os.environ.get("CERTFLOW_EMAIL_APP_PASSWORD", "")

        if sender and app_password:
            return GmailCredentials(
                sender_email=sender, app_password=app_password
            )

        raise ConfigurationError(
            "Gmail credentials not found. Checked: "
            ".streamlit/secrets.toml, credentials.toml, "
            "~/.certflow/credentials.toml, and environment variables "
            "CERTFLOW_EMAIL_SENDER / CERTFLOW_EMAIL_APP_PASSWORD"
        )

    @staticmethod
    def check_credentials() -> bool:
        """Check if Gmail credentials are available without connecting.

        Returns:
            True if credentials can be loaded, False otherwise.
        """
        try:
            sender = EmailSender()
            sender.load_credentials()
            return True
        except ConfigurationError:
            return False

    def connect(self) -> None:
        """Establish TLS connection to Gmail SMTP and authenticate.

        Raises:
            ConnectionError: On network failure or timeout.
            AuthenticationError: On invalid credentials.
        """
        if self._credentials is None:
            self._credentials = self.load_credentials()

        try:
            self._smtp = smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30)
            self._smtp.ehlo()
            self._smtp.starttls()
            self._smtp.ehlo()
            self._smtp.login(
                self._credentials.sender_email,
                self._credentials.app_password,
            )
        except smtplib.SMTPAuthenticationError as e:
            raise AuthenticationError(
                f"Gmail authentication failed: {e}. "
                "Verify your App Password is correct."
            )
        except (OSError, smtplib.SMTPException) as e:
            raise ConnectionError(
                f"Cannot connect to {GMAIL_SMTP_HOST}:{GMAIL_SMTP_PORT} — {e}"
            )

    def disconnect(self) -> None:
        """Close the SMTP connection gracefully."""
        if self._smtp:
            try:
                self._smtp.quit()
            except smtplib.SMTPException:
                pass
            self._smtp = None

    def _get_mime_type(self, file_path: Path) -> Tuple[str, str]:
        """Return (maintype, subtype) based on file extension.

        Args:
            file_path: Path to the attachment file.

        Returns:
            Tuple of (maintype, subtype) for MIME.
        """
        ext = file_path.suffix.lower()
        mime_map = {
            ".png": ("image", "png"),
            ".jpg": ("image", "jpeg"),
            ".jpeg": ("image", "jpeg"),
            ".pdf": ("application", "pdf"),
        }
        return mime_map.get(ext, ("application", "octet-stream"))

    def _compose_email(
        self,
        recipient: AttendeeRecord,
        template: EmailTemplate,
        attachment_data: bytes,
        attachment_filename: str,
        file_ext: str,
    ) -> MIMEMultipart:
        """Compose a MIME email with personalized subject/body and attachment.

        Args:
            recipient: Attendee record with name and email.
            template: Email template with subject and body.
            attachment_data: Certificate file bytes.
            attachment_filename: Filename for the attachment.
            file_ext: File extension (e.g., '.png') for MIME type detection.

        Returns:
            Composed MIMEMultipart message ready to send.
        """
        msg = MIMEMultipart()
        msg["From"] = self._credentials.sender_email
        msg["To"] = recipient.email
        msg["Subject"] = template.render_subject(recipient.name)

        # Body
        body_text = template.render_body(recipient.name)
        msg.attach(MIMEText(body_text, "plain"))

        # Attachment
        maintype, subtype = self._get_mime_type(Path(f"file{file_ext}"))
        attachment = MIMEBase(maintype, subtype)
        attachment.set_payload(attachment_data)
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=attachment_filename,
        )
        msg.attach(attachment)

        return msg

    def send_bulk(
        self,
        recipients: List[AttendeeRecord],
        certificate_data: List[bytes],
        certificate_format: str,
        template: EmailTemplate,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> SendResult:
        """Send emails to all recipients with corresponding certificate attachments.

        Args:
            recipients: List of attendee records.
            certificate_data: List of certificate file bytes (same order as recipients).
            certificate_format: File format extension ('png', 'jpg', or 'pdf').
            template: Email template for subject and body.
            progress_callback: Optional callback(current_index, total) for progress.

        Returns:
            SendResult with successful deliveries and failures.
        """
        total = len(recipients)
        result = SendResult()

        # Validate inputs
        if len(certificate_data) != total:
            raise ValueError(
                f"recipients ({total}) and certificate_data ({len(certificate_data)}) "
                f"must have the same length"
            )

        if total > GMAIL_DAILY_LIMIT_WARNING:
            logger.warning(
                f"Batch size ({total}) exceeds {GMAIL_DAILY_LIMIT_WARNING}. "
                f"Approaching Gmail daily limit of 500 emails."
            )

        # Connect
        self.connect()

        for i, (recipient, cert_bytes) in enumerate(
            zip(recipients, certificate_data)
        ):
            current = i + 1

            # Check attachment size
            if len(cert_bytes) > MAX_ATTACHMENT_SIZE_BYTES:
                result.failures.append(
                    DeliveryFailure(
                        email=recipient.email,
                        attendee_name=recipient.name,
                        error_message=(
                            f"Attachment size ({len(cert_bytes) // 1024 // 1024}MB) "
                            f"exceeds Gmail's 25MB limit"
                        ),
                    )
                )
                if progress_callback:
                    progress_callback(current, total)
                continue

            # Compose and send
            sanitized_name = recipient.name.replace(" ", "_")
            filename = f"{sanitized_name}.{certificate_format}"

            try:
                msg = self._compose_email(
                    recipient=recipient,
                    template=template,
                    attachment_data=cert_bytes,
                    attachment_filename=filename,
                    file_ext=f".{certificate_format}",
                )
                self._smtp.sendmail(
                    self._credentials.sender_email,
                    recipient.email,
                    msg.as_string(),
                )
                result.successful.append(recipient.email)

            except smtplib.SMTPDataError as e:
                # Rate limit or data rejection from Gmail
                error_code = e.smtp_code
                if error_code in (421, 450, 452):
                    logger.error(f"Gmail rate limit at email {current}/{total}: {e}")
                    result.failures.append(
                        DeliveryFailure(
                            email=recipient.email,
                            attendee_name=recipient.name,
                            error_message=f"Rate limited by Gmail (code {error_code})",
                        )
                    )
                    for j in range(i + 1, total):
                        remaining = recipients[j]
                        result.failures.append(
                            DeliveryFailure(
                                email=remaining.email,
                                attendee_name=remaining.name,
                                error_message="Batch stopped due to Gmail rate limit",
                            )
                        )
                    if progress_callback:
                        progress_callback(total, total)
                    break
                else:
                    result.failures.append(
                        DeliveryFailure(
                            email=recipient.email,
                            attendee_name=recipient.name,
                            error_message=f"SMTP data error ({error_code}): {e}",
                        )
                    )

            except smtplib.SMTPRecipientsRefused as e:
                result.failures.append(
                    DeliveryFailure(
                        email=recipient.email,
                        attendee_name=recipient.name,
                        error_message=f"Recipient rejected: {e}",
                    )
                )

            except smtplib.SMTPServerDisconnected:
                # Attempt reconnection
                if self._attempt_reconnect():
                    # Retry this email
                    try:
                        msg = self._compose_email(
                            recipient=recipient,
                            template=template,
                            attachment_data=cert_bytes,
                            attachment_filename=filename,
                            file_ext=f".{certificate_format}",
                        )
                        self._smtp.sendmail(
                            self._credentials.sender_email,
                            recipient.email,
                            msg.as_string(),
                        )
                        result.successful.append(recipient.email)
                    except Exception as retry_err:
                        result.failures.append(
                            DeliveryFailure(
                                email=recipient.email,
                                attendee_name=recipient.name,
                                error_message=f"Retry failed: {retry_err}",
                            )
                        )
                else:
                    # Mark current recipient as failed
                    result.failures.append(
                        DeliveryFailure(
                            email=recipient.email,
                            attendee_name=recipient.name,
                            error_message=(
                                "SMTP connection lost and reconnect failed"
                            ),
                        )
                    )
                    # Mark all remaining (after current) as failed
                    for j in range(i + 1, total):
                        remaining = recipients[j]
                        result.failures.append(
                            DeliveryFailure(
                                email=remaining.email,
                                attendee_name=remaining.name,
                                error_message=(
                                    "SMTP connection lost and reconnect failed"
                                ),
                            )
                        )
                    if progress_callback:
                        progress_callback(total, total)
                    break

            except smtplib.SMTPException as e:
                result.failures.append(
                    DeliveryFailure(
                        email=recipient.email,
                        attendee_name=recipient.name,
                        error_message=f"SMTP error: {e}",
                    )
                )

            if progress_callback:
                progress_callback(current, total)

            # Rate limiting: small delay between sends to avoid Gmail throttling
            if current < total:
                time.sleep(0.5)

        self.disconnect()
        return result

    def _attempt_reconnect(self) -> bool:
        """Attempt to reconnect to SMTP server once.

        Returns:
            True if reconnection succeeded, False otherwise.
        """
        try:
            self.disconnect()
            self.connect()
            return True
        except (ConnectionError, AuthenticationError):
            return False
