"""Shared data models for CertFlow."""

from dataclasses import dataclass, field
from typing import List, Union

from PIL import Image


@dataclass
class CertificateOutput:
    """A single generated certificate.

    Attributes:
        attendee_name: Name of the attendee.
        certificate: Generated certificate (PIL Image or PDF bytes).
        format: Output format ('png', 'jpg', or 'pdf').
    """

    attendee_name: str
    certificate: Union[Image.Image, bytes]
    format: str


@dataclass
class GenerationError:
    """Error that occurred during certificate generation for one attendee.

    Attributes:
        attendee_name: Name of the attendee that failed.
        error_message: Description of what went wrong.
    """

    attendee_name: str
    error_message: str


@dataclass
class BatchResult:
    """Result of a batch certificate generation operation.

    Attributes:
        certificates: Successfully generated certificates.
        errors: List of generation failures.
    """

    certificates: List[CertificateOutput] = field(default_factory=list)
    errors: List[GenerationError] = field(default_factory=list)


@dataclass
class AttendeeRecord:
    """A validated attendee record from CSV.

    Attributes:
        name: Attendee's full name.
        email: Attendee's email address.
    """

    name: str
    email: str


@dataclass
class ValidationError:
    """A validation error for a specific CSV row.

    Attributes:
        row_number: 1-based row number in the CSV.
        field: Which field failed ('name', 'email', or 'duplicate').
        message: Human-readable error description.
    """

    row_number: int
    field: str
    message: str


@dataclass
class ParseResult:
    """Result of CSV parsing with validated records and errors.

    Attributes:
        records: List of valid attendee records.
        errors: List of validation errors found during parsing.
    """

    records: List[AttendeeRecord] = field(default_factory=list)
    errors: List[ValidationError] = field(default_factory=list)


@dataclass
class GmailCredentials:
    """Gmail SMTP credentials.

    Attributes:
        sender_email: Gmail address to send from.
        app_password: Gmail App Password (16 characters).
    """

    sender_email: str
    app_password: str


@dataclass
class EmailTemplate:
    """Email template with placeholder support.

    Attributes:
        subject: Email subject line (supports {name} placeholder).
        body: Email body text (supports {name} placeholder).
    """

    subject: str
    body: str

    def render_subject(self, name: str) -> str:
        """Replace {name} placeholder in subject with attendee name."""
        return self.subject.replace("{name}", name)

    def render_body(self, name: str) -> str:
        """Replace {name} placeholder in body with attendee name."""
        return self.body.replace("{name}", name)


@dataclass
class DeliveryFailure:
    """A failed email delivery attempt.

    Attributes:
        email: Recipient email address.
        attendee_name: Name of the attendee.
        error_message: Description of the failure.
    """

    email: str
    attendee_name: str
    error_message: str


@dataclass
class SendResult:
    """Result of a bulk email send operation.

    Attributes:
        successful: List of email addresses that received the certificate.
        failures: List of delivery failures with error details.
    """

    successful: List[str] = field(default_factory=list)
    failures: List[DeliveryFailure] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        """Number of successfully sent emails."""
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        """Number of failed email deliveries."""
        return len(self.failures)
