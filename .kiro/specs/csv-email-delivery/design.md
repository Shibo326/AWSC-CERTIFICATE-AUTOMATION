# Design Document

## Overview

The CSV Parsing and Bulk Email Delivery module is structured as two independent components: a `CSV_Parser` that handles file reading, header validation, row-level data validation, and duplicate detection; and an `Email_Sender` that manages Gmail SMTP connectivity, email composition with personalized templates and attachments, bulk sending with progress callbacks, and error recovery. Both components produce structured result objects that separate successes from failures, enabling the UI layer to provide detailed feedback without halting on individual errors.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Streamlit UI Layer                         │
│  (File upload, credential config, send trigger, progress display)│
├─────────────────────────────┬────────────────────────────────────┤
│         CSV_Parser          │           Email_Sender             │
│  (csv module, validation,   │  (smtplib, email.mime, SMTP TLS,  │
│   duplicate detection)      │   bulk send, error recovery)       │
├─────────────────────────────┼────────────────────────────────────┤
│         models.py           │         exceptions.py              │
│  (AttendeeRecord, ParseResult,│  (ConfigurationError,           │
│   ValidationError, SendResult,│   AuthenticationError)           │
│   DeliveryFailure, etc.)    │                                    │
└─────────────────────────────┴────────────────────────────────────┘
```

## File Structure

```
utils/
├── csv_parser.py         # CSV reading, header validation, row validation, duplicates
├── email_sender.py       # Gmail SMTP connection, compose, bulk send, error recovery
├── models.py             # Shared data models (dataclasses)
└── exceptions.py         # Custom exception classes

.streamlit/
└── secrets.toml          # Gmail credentials (NEVER commit)
```

## Data Models

### AttendeeRecord

```python
from dataclasses import dataclass

@dataclass
class AttendeeRecord:
    name: str
    email: str
```

### ValidationError

```python
@dataclass
class ValidationError:
    row_number: int
    field: str
    message: str
```

### ParseResult

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class ParseResult:
    records: List[AttendeeRecord] = field(default_factory=list)
    errors: List[ValidationError] = field(default_factory=list)
```

### GmailCredentials

```python
@dataclass
class GmailCredentials:
    sender_email: str
    app_password: str
```

### EmailTemplate

```python
@dataclass
class EmailTemplate:
    subject: str
    body: str

    def render_subject(self, name: str) -> str:
        """Replace {name} placeholder in subject with attendee name."""
        ...

    def render_body(self, name: str) -> str:
        """Replace {name} placeholder in body with attendee name."""
        ...
```

### DeliveryFailure

```python
@dataclass
class DeliveryFailure:
    email: str
    attendee_name: str
    error_message: str
```

### SendResult

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class SendResult:
    successful: List[str] = field(default_factory=list)       # list of email addresses
    failures: List[DeliveryFailure] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        return len(self.failures)
```

## Component Design

### CSV_Parser (utils/csv_parser.py)

Responsible for reading CSV files, validating headers, validating row data, detecting duplicates, and returning structured results.

```python
import csv
import re
from typing import List, IO

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

class CSVParser:
    def parse(self, file: IO[str]) -> ParseResult:
        """Parse a CSV file and return validated records and errors."""
        ...

    def _validate_headers(self, headers: List[str]) -> dict:
        """Validate that 'name' and 'email' headers exist (case-insensitive).

        Returns a mapping of normalized header name -> column index.
        Raises ValueError if required columns are missing.
        """
        ...

    def _validate_row(self, row_number: int, name: str, email: str) -> tuple:
        """Validate a single row's name and email fields.

        Returns (AttendeeRecord | None, List[ValidationError]).
        """
        ...

    def _detect_duplicates(
        self, records: List[AttendeeRecord], start_row: int
    ) -> tuple:
        """Detect duplicate emails (case-insensitive).

        Returns (deduplicated records, list of ValidationError for duplicates).
        """
        ...

    def format_records(self, records: List[AttendeeRecord]) -> str:
        """Format a list of AttendeeRecord objects back to a CSV string.

        Output contains 'name' and 'email' headers with rows in input order.
        """
        ...
```

**Parsing Flow:**
1. Read the first row as headers using `csv.reader`
2. Call `_validate_headers()` — raises `ValueError` if "name" or "email" missing
3. Map header names (case-insensitive) to column indices
4. Iterate remaining rows:
   a. Strip whitespace from name and email cells
   b. Call `_validate_row()` for each row
   c. Collect valid `AttendeeRecord` objects and `ValidationError` objects
5. Call `_detect_duplicates()` on the valid records list
6. Return `ParseResult` with final deduplicated records and all errors combined

**Header Validation Logic:**
1. Normalize all headers to lowercase and strip whitespace
2. Check for presence of "name" and "email" in normalized headers
3. If one is missing, raise `ValueError` naming the missing column
4. If both are missing, raise `ValueError` listing both missing columns
5. Return `{"name": col_index, "email": col_index}` mapping

**Row Validation Logic:**
1. Check name is non-empty after stripping whitespace — error if empty
2. Check email is non-empty — error if empty
3. Match email against `EMAIL_REGEX` — error if no match
4. If all valid, return `AttendeeRecord(name, email)`

**Duplicate Detection Logic:**
1. Maintain a `seen_emails: dict[str, int]` mapping lowercase email → first row number
2. For each record, check if `email.lower()` exists in `seen_emails`
3. If duplicate: add `ValidationError` with row number and duplicate email, remove from valid list
4. If unique: add to `seen_emails` and keep in valid list

### Email_Sender (utils/email_sender.py)

Responsible for SMTP connection management, email composition, bulk sending with progress, and error recovery.

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Callable, Optional, Tuple
from pathlib import Path

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587
GMAIL_DAILY_LIMIT_WARNING = 450

class EmailSender:
    def __init__(self, credentials: Optional[GmailCredentials] = None):
        """Initialize with credentials. If None, auto-loads from config."""
        ...

    def load_credentials(self) -> GmailCredentials:
        """Load Gmail credentials from secrets.toml or environment variables.

        Precedence: secrets.toml > environment variables.
        Raises ConfigurationError if neither source has valid credentials.
        """
        ...

    def connect(self) -> None:
        """Establish TLS connection to Gmail SMTP and authenticate.

        Raises ConnectionError on network failure.
        Raises AuthenticationError on invalid credentials.
        """
        ...

    def disconnect(self) -> None:
        """Close the SMTP connection gracefully."""
        ...

    def _compose_email(
        self,
        recipient: AttendeeRecord,
        template: EmailTemplate,
        attachment_path: Path,
    ) -> MIMEMultipart:
        """Compose a MIME email with personalized subject/body and attachment.

        Detects MIME type from file extension (png, jpg/jpeg, pdf).
        """
        ...

    def _get_mime_type(self, file_path: Path) -> Tuple[str, str]:
        """Return (maintype, subtype) based on file extension.

        .png  -> ('image', 'png')
        .jpg/.jpeg -> ('image', 'jpeg')
        .pdf  -> ('application', 'pdf')
        """
        ...

    def send_bulk(
        self,
        recipients: List[AttendeeRecord],
        attachment_paths: List[Path],
        template: EmailTemplate,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> SendResult:
        """Send emails to all recipients with corresponding attachments.

        Invokes progress_callback(current_index, total) after each attempt.
        On connection loss, attempts one reconnect and resumes.
        Returns SendResult with successful/failed deliveries.
        """
        ...

    def _attempt_reconnect(self) -> bool:
        """Attempt to reconnect to SMTP server once.

        Returns True if reconnection succeeded, False otherwise.
        """
        ...
```

**Connection Flow:**
1. Create `smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30)`
2. Call `smtp.starttls()` to upgrade to TLS
3. Call `smtp.login(sender_email, app_password)`
4. Store the connection as `self._smtp`
5. On `OSError`/`socket.error` → raise `ConnectionError`
6. On `smtplib.SMTPAuthenticationError` → raise `AuthenticationError`

**Email Composition Flow:**
1. Create `MIMEMultipart` message
2. Set From, To, Subject headers (subject personalized via template)
3. Attach body as `MIMEText(rendered_body, 'plain')`
4. Open attachment file in binary mode
5. Determine MIME type from extension via `_get_mime_type()`
6. Create `MIMEBase(maintype, subtype)`, set payload, encode base64
7. Add `Content-Disposition` header with original filename
8. Attach to the multipart message
9. Return the composed message

**Bulk Send Flow:**
1. Validate batch size — if `len(recipients) > 450`, log warning about Gmail limit
2. Ensure SMTP connection is active (connect if needed)
3. For each `(index, recipient, attachment_path)`:
   a. Compose email via `_compose_email()`
   b. Attempt `smtp.sendmail(sender, recipient.email, msg.as_string())`
   c. On success: append email to `successful` list
   d. On `SMTPRecipientsRefused`: record `DeliveryFailure` and continue
   e. On `SMTPServerDisconnected`: call `_attempt_reconnect()`
      - If reconnect succeeds: retry current email
      - If reconnect fails: mark all remaining as failed, break
   f. Invoke `progress_callback(index + 1, total)`
4. Call `disconnect()`
5. Return `SendResult`

**Credential Loading Flow:**
1. Attempt to read `.streamlit/secrets.toml` → look for `[email]` section
2. Extract `sender` and `app_password` fields
3. If found: validate sender email format, return `GmailCredentials`
4. If not found: check `CERTFLOW_EMAIL_SENDER` and `CERTFLOW_EMAIL_APP_PASSWORD` env vars
5. If env vars exist: validate sender email format, return `GmailCredentials`
6. If neither: raise `ConfigurationError` listing both sources checked

**Error Recovery (Reconnect):**
1. Close existing connection (if any) with `smtp.quit()` in a try/except
2. Attempt fresh `connect()` call
3. Return `True` on success, `False` on any exception

### Custom Exceptions (utils/exceptions.py)

```python
class ConfigurationError(Exception):
    """Raised when required configuration (credentials) is missing."""
    pass

class AuthenticationError(Exception):
    """Raised when SMTP authentication fails."""
    pass
```

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CSV library | Python `csv` module | Standard library, handles edge cases (quoted fields, commas in values) |
| Email validation | Regex pattern | Lightweight, covers standard formats, avoids external dependency |
| SMTP library | `smtplib` + `email.mime` | Standard library, full control over MIME construction and connection lifecycle |
| Connection strategy | Single connection, reused for batch | Reduces auth overhead, respects Gmail rate limits |
| Error recovery | Reconnect once on drop | Simple strategy that handles transient failures without infinite retry loops |
| Credential loading | secrets.toml first, env vars fallback | Matches Streamlit Cloud deployment pattern while supporting local dev via env vars |
| Duplicate detection | Case-insensitive, first-occurrence wins | Prevents double sends, deterministic behavior |
| Progress reporting | Callback function | Decouples SMTP logic from UI framework, works with any progress display |
| Batch failure mode | Log and continue | Maximizes successful deliveries, reports all failures at the end |
| MIME type detection | File extension mapping | Simple, reliable, covers the three formats CertFlow produces |

## Correctness Properties

1. **Parse result completeness**: For any CSV with N data rows, the sum of `len(parse_result.records) + len(parse_result.errors)` must equal N (every row is either a valid record or produces at least one error — counted once per row, not per field).

2. **Round-trip consistency**: For any list of valid `AttendeeRecord` objects, calling `format_records()` and then `parse()` on the resulting CSV must yield an identical list of `AttendeeRecord` objects with zero errors.

3. **Duplicate detection correctness**: For any CSV where email E appears K times (case-insensitive), the parse result must contain exactly 1 `AttendeeRecord` with email E and exactly K-1 `ValidationError` entries referencing that email.

4. **Send result completeness**: For any bulk send of N recipients, the sum of `send_result.success_count + send_result.failure_count` must equal N.

5. **Order preservation**: For an input list of recipients [R₁, R₂, ..., Rₙ], the successful sends must appear in the same relative order as their positions in the input list.

6. **Template idempotence**: Rendering an `EmailTemplate` with the same name value multiple times must produce identical subject and body strings.

7. **Header case-insensitivity**: For any CSV whose header row contains "name" and "email" in any combination of upper/lower case, the parser must successfully identify and map both columns without error.

8. **Whitespace normalization**: For any cell value V, the parsed output must equal `V.strip()` — leading and trailing whitespace is always removed.

9. **Connection reuse**: During a batch send of N emails where no connection failure occurs, exactly one SMTP connection must be opened and used for all N sends.

10. **Graceful degradation on connection loss**: If the SMTP connection drops at send index I, and reconnection succeeds, all emails from index I onward must still be attempted. If reconnection fails, all emails from index I onward must appear in `failures`.
