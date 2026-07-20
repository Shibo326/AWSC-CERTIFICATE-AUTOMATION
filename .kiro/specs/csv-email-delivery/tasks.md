# Tasks

## Task 1: Set Up Data Models

- [ ] 1.1 Create `utils/models.py` (or extend existing) with the `AttendeeRecord` dataclass containing `name: str` and `email: str` fields
- [ ] 1.2 Add the `ValidationError` dataclass with `row_number: int`, `field: str`, and `message: str` fields
- [ ] 1.3 Add the `ParseResult` dataclass with `records: List[AttendeeRecord]` (default empty list) and `errors: List[ValidationError]` (default empty list)
- [ ] 1.4 Add the `GmailCredentials` dataclass with `sender_email: str` and `app_password: str` fields
- [ ] 1.5 Add the `EmailTemplate` dataclass with `subject: str` and `body: str` fields, plus `render_subject(name: str)` and `render_body(name: str)` methods that replace `{name}` placeholder
- [ ] 1.6 Add the `DeliveryFailure` dataclass with `email: str`, `attendee_name: str`, and `error_message: str` fields
- [ ] 1.7 Add the `SendResult` dataclass with `successful: List[str]` and `failures: List[DeliveryFailure]` fields, plus `success_count` and `failure_count` properties

## Task 2: Implement CSVParser — Header Validation

- [ ] 2.1 Create `utils/csv_parser.py` with the `CSVParser` class and `EMAIL_REGEX` constant
- [ ] 2.2 Implement `_validate_headers()` method that normalizes headers to lowercase, checks for "name" and "email" presence (case-insensitive), and returns a column index mapping
- [ ] 2.3 Raise `ValueError` specifying the missing column name if "name" is absent
- [ ] 2.4 Raise `ValueError` specifying the missing column name if "email" is absent
- [ ] 2.5 Raise `ValueError` listing both missing columns if neither "name" nor "email" is present
- [ ] 2.6 Handle empty CSV (no header row) by raising `ValueError` indicating headers are missing

## Task 3: Implement CSVParser — Row Validation

- [ ] 3.1 Implement `_validate_row()` method that checks name is non-empty after whitespace stripping
- [ ] 3.2 Add validation that email is non-empty after whitespace stripping
- [ ] 3.3 Add email format validation against the regex `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
- [ ] 3.4 Return a `ValidationError` with row number and field name for each validation failure
- [ ] 3.5 Return an `AttendeeRecord` when both name and email pass validation
- [ ] 3.6 Ensure parsing continues through all rows even after encountering validation errors

## Task 4: Implement CSVParser — Duplicate Detection and Format Records

- [ ] 4.1 Implement `_detect_duplicates()` method that tracks seen emails in a case-insensitive dictionary mapping email to first row number
- [ ] 4.2 Record a `ValidationError` for each duplicate occurrence (after the first) including the row number and duplicated email address
- [ ] 4.3 Retain only the first occurrence of a duplicated email as a valid `AttendeeRecord`
- [ ] 4.4 Implement the `parse()` method that orchestrates header validation, row iteration with whitespace stripping, row validation, duplicate detection, and returns a `ParseResult`
- [ ] 4.5 Implement `format_records()` method that accepts a list of `AttendeeRecord` objects and returns a CSV string with "name" and "email" headers, preserving input order

## Task 5: Implement EmailSender — Credential Loading and SMTP Connection

- [ ] 5.1 Create `utils/email_sender.py` with the `EmailSender` class and constants `GMAIL_SMTP_HOST`, `GMAIL_SMTP_PORT`, `GMAIL_DAILY_LIMIT_WARNING`
- [ ] 5.2 Implement `load_credentials()` method that first attempts to read `.streamlit/secrets.toml` under `[email]` section for "sender" and "app_password"
- [ ] 5.3 Add fallback to environment variables `CERTFLOW_EMAIL_SENDER` and `CERTFLOW_EMAIL_APP_PASSWORD` if secrets.toml is unavailable
- [ ] 5.4 Raise `ConfigurationError` listing both checked sources if neither contains valid credentials
- [ ] 5.5 Validate the sender email format before returning `GmailCredentials`
- [ ] 5.6 Implement `connect()` method that creates an SMTP connection to smtp.gmail.com:587, calls `starttls()`, and authenticates with the loaded credentials
- [ ] 5.7 Raise `ConnectionError` with host and port details on network failure or timeout
- [ ] 5.8 Raise `AuthenticationError` on SMTP authentication failure
- [ ] 5.9 Implement `disconnect()` method that gracefully closes the SMTP connection

## Task 6: Implement EmailSender — Email Composition

- [ ] 6.1 Implement `_get_mime_type()` method that maps `.png` to `('image', 'png')`, `.jpg`/`.jpeg` to `('image', 'jpeg')`, and `.pdf` to `('application', 'pdf')`
- [ ] 6.2 Implement `_compose_email()` method that creates a `MIMEMultipart` message with From, To, and personalized Subject headers
- [ ] 6.3 Attach the personalized body text as `MIMEText` (plain text) using the `EmailTemplate.render_body()` method
- [ ] 6.4 Read the certificate file in binary mode, determine MIME type via `_get_mime_type()`, create `MIMEBase` with base64 encoding, and attach with original filename in `Content-Disposition`

## Task 7: Implement EmailSender — Bulk Send and Error Recovery

- [ ] 7.1 Implement `send_bulk()` method that iterates recipients with corresponding attachment paths, composing and sending one email per attendee
- [ ] 7.2 Invoke `progress_callback(current_index, total)` after each send attempt (1-based index)
- [ ] 7.3 Log a warning when batch size exceeds 450 (proximity to Gmail's daily 500 limit)
- [ ] 7.4 On `SMTPRecipientsRefused`, record a `DeliveryFailure` with the recipient email and SMTP rejection message, then continue
- [ ] 7.5 On `SMTPServerDisconnected`, implement `_attempt_reconnect()` that closes the existing connection and attempts a fresh `connect()` call
- [ ] 7.6 If reconnection succeeds, retry the current email; if reconnection fails, mark all remaining emails as failed with a connection error and stop the batch
- [ ] 7.7 Handle attachment size exceeding 25 MB by recording a `DeliveryFailure` indicating the attachment exceeds maximum allowed size
- [ ] 7.8 Return a `SendResult` containing all successful email addresses and all `DeliveryFailure` objects, preserving input order
- [ ] 7.9 Reuse a single SMTP connection for the entire batch (connect once before the loop, disconnect after)

## Task 8: Add Custom Exceptions

- [ ] 8.1 Create or extend `utils/exceptions.py` with `ConfigurationError(Exception)` for missing credential configuration
- [ ] 8.2 Add `AuthenticationError(Exception)` for SMTP authentication failures
- [ ] 8.3 Add descriptive docstrings to both exception classes

## Task 9: Write Unit Tests for CSVParser

- [ ] 9.1 Create `tests/test_csv_parser.py` with test fixtures (valid CSV content, invalid CSV content, CSVs with duplicates)
- [ ] 9.2 Write tests for header validation: valid headers (mixed case), missing "name", missing "email", both missing, empty file
- [ ] 9.3 Write tests for row validation: valid rows, empty name, empty email, invalid email format, whitespace stripping
- [ ] 9.4 Write tests for duplicate detection: single duplicate, multiple duplicates, case-insensitive matching, first occurrence retained
- [ ] 9.5 Write tests for `parse()` integration: extra columns ignored, empty data rows return empty list, all errors collected across rows
- [ ] 9.6 Write tests for `format_records()`: correct CSV output, order preservation, round-trip consistency (parse → format → parse yields identical records)
- [ ] 9.7 Write property-based tests (hypothesis) for parse result completeness: `len(records) + len(error_rows) == total_data_rows` for any valid CSV input
- [ ] 9.8 Write property-based tests for round-trip consistency: `parse(format_records(records))` yields identical records for any list of valid `AttendeeRecord` objects

## Task 10: Write Unit Tests for EmailSender (Mocked SMTP)

- [ ] 10.1 Create `tests/test_email_sender.py` with fixtures for `GmailCredentials`, `EmailTemplate`, sample `AttendeeRecord` lists, and temporary certificate files
- [ ] 10.2 Write tests for `load_credentials()`: successful load from secrets.toml, fallback to env vars, `ConfigurationError` when neither exists, invalid sender email format
- [ ] 10.3 Write tests for `connect()`: successful connection (mocked SMTP), `ConnectionError` on network failure, `AuthenticationError` on bad credentials
- [ ] 10.4 Write tests for `_compose_email()`: correct headers, personalized subject/body, correct MIME type for PNG/JPG/PDF, attachment filename preserved
- [ ] 10.5 Write tests for `send_bulk()`: all succeed, partial failures, progress callback invoked correctly, send order matches input order
- [ ] 10.6 Write tests for error recovery: reconnect succeeds and resumes, reconnect fails and marks remaining as failed
- [ ] 10.7 Write tests for `SendResult` completeness: `success_count + failure_count == total_recipients` for all test scenarios
- [ ] 10.8 Write tests for batch size warning: warning logged when batch exceeds 450 recipients
