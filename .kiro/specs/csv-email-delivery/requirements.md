# Requirements Document

## Introduction

The CSV Parsing and Bulk Email Delivery module handles two core responsibilities in CertFlow: (1) parsing uploaded CSV files containing attendee information (name and email) with robust validation, and (2) sending personalized emails with certificate attachments to all attendees via Gmail SMTP. This module bridges the gap between certificate generation and delivery, enabling users to upload a CSV of attendees, validate the data, and bulk-send generated certificates as email attachments with customizable subject and body text.

## Glossary

- **CSV_Parser**: The component (utils/csv_parser.py) that reads, validates, and parses CSV files containing attendee name and email data.
- **Email_Sender**: The component (utils/email_sender.py) that connects to Gmail SMTP and sends emails with certificate attachments to attendees.
- **Attendee_Record**: A validated data object containing a name (non-empty string) and email (valid email address) for one attendee.
- **Validation_Error**: A structured error report containing the row number, the field name, and a description of the validation failure.
- **Progress_Callback**: A callable function that receives the current send index and total count, used for real-time UI progress reporting.
- **Send_Result**: A structured result for a batch send operation containing lists of successful deliveries and failed deliveries with error details.
- **Gmail_Credentials**: The sender email address and App Password used for SMTP authentication, sourced from .streamlit/secrets.toml or environment variables.
- **Email_Template**: The subject line and body text for outgoing emails, supporting a {name} placeholder for personalization.

## Requirements

### Requirement 1: Parse CSV File

**User Story:** As a user, I want to upload a CSV file containing attendee names and emails, so that the system can process the attendee list for certificate delivery.

#### Acceptance Criteria

1. WHEN a CSV file with "name" and "email" column headers is provided, THE CSV_Parser SHALL parse each row and return a list of Attendee_Record objects.
2. THE CSV_Parser SHALL treat column header matching as case-insensitive (e.g., "Name", "EMAIL", "Email" are all valid).
3. THE CSV_Parser SHALL strip leading and trailing whitespace from all cell values before validation.
4. WHEN a CSV file contains extra columns beyond "name" and "email", THE CSV_Parser SHALL ignore the extra columns and parse only "name" and "email" data.
5. IF a CSV file is empty (contains no rows after the header), THEN THE CSV_Parser SHALL return an empty list without raising an error.
6. IF a CSV file contains no header row, THEN THE CSV_Parser SHALL raise a ValueError indicating that column headers are missing.

### Requirement 2: Validate CSV Column Headers

**User Story:** As a user, I want the system to validate that my CSV has the required columns, so that I receive clear feedback if my file format is wrong.

#### Acceptance Criteria

1. WHEN a CSV file is provided, THE CSV_Parser SHALL verify that both "name" and "email" columns exist in the header row.
2. IF the "name" column is missing from the header, THEN THE CSV_Parser SHALL raise a ValueError specifying that the "name" column is required.
3. IF the "email" column is missing from the header, THEN THE CSV_Parser SHALL raise a ValueError specifying that the "email" column is required.
4. IF both "name" and "email" columns are missing, THEN THE CSV_Parser SHALL raise a ValueError listing both missing columns.

### Requirement 3: Validate Attendee Row Data

**User Story:** As a user, I want each row validated individually, so that I can see all data errors at once rather than fixing them one by one.

#### Acceptance Criteria

1. WHEN a row contains a non-empty name and a valid email address, THE CSV_Parser SHALL create an Attendee_Record for that row.
2. IF a row has an empty or whitespace-only name field, THEN THE CSV_Parser SHALL record a Validation_Error for that row indicating the name field is required.
3. IF a row has an empty email field, THEN THE CSV_Parser SHALL record a Validation_Error for that row indicating the email field is required.
4. IF a row has an email that does not match the pattern `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`, THEN THE CSV_Parser SHALL record a Validation_Error for that row indicating the email format is invalid.
5. THE CSV_Parser SHALL continue parsing all remaining rows after encountering a validation error in any row.
6. WHEN parsing completes, THE CSV_Parser SHALL return both the list of valid Attendee_Record objects and the list of Validation_Error objects.

### Requirement 4: Detect Duplicate Email Entries

**User Story:** As a user, I want the system to flag duplicate emails, so that I avoid sending multiple certificates to the same person.

#### Acceptance Criteria

1. WHEN two or more rows contain the same email address (case-insensitive comparison), THE CSV_Parser SHALL record a Validation_Error for each duplicate occurrence after the first.
2. THE CSV_Parser SHALL retain the first occurrence of a duplicated email as a valid Attendee_Record.
3. THE CSV_Parser SHALL include the row number and the duplicated email address in each duplicate Validation_Error.

### Requirement 5: Connect to Gmail SMTP

**User Story:** As a user, I want the system to connect to Gmail using my App Password, so that I can send certificates from my Gmail account.

#### Acceptance Criteria

1. WHEN Gmail_Credentials are available, THE Email_Sender SHALL establish a TLS connection to smtp.gmail.com on port 587.
2. THE Email_Sender SHALL authenticate using the sender email and App Password from the Gmail_Credentials.
3. IF Gmail_Credentials are not found in .streamlit/secrets.toml or environment variables, THEN THE Email_Sender SHALL raise a ConfigurationError indicating that Gmail credentials are missing.
4. IF SMTP authentication fails, THEN THE Email_Sender SHALL raise an AuthenticationError with a message indicating invalid credentials.
5. IF the SMTP connection cannot be established (network error or timeout), THEN THE Email_Sender SHALL raise a ConnectionError with a descriptive message including the host and port.
6. THE Email_Sender SHALL reuse a single SMTP connection for all emails in a batch send operation to minimize connection overhead.

### Requirement 6: Compose Email with Certificate Attachment

**User Story:** As a user, I want to customize the email subject and body with the attendee's name, so that each email feels personalized.

#### Acceptance Criteria

1. WHEN an Email_Template subject contains the placeholder {name}, THE Email_Sender SHALL replace it with the attendee's name from the Attendee_Record.
2. WHEN an Email_Template body contains the placeholder {name}, THE Email_Sender SHALL replace it with the attendee's name from the Attendee_Record.
3. THE Email_Sender SHALL construct a multipart MIME email with the body as plain text and the certificate file as an attachment.
4. WHEN a PNG certificate file is attached, THE Email_Sender SHALL set the attachment MIME type to image/png.
5. WHEN a JPG certificate file is attached, THE Email_Sender SHALL set the attachment MIME type to image/jpeg.
6. WHEN a PDF certificate file is attached, THE Email_Sender SHALL set the attachment MIME type to application/pdf.
7. THE Email_Sender SHALL set the attachment filename to the original certificate file name.

### Requirement 7: Send Bulk Emails with Progress Reporting

**User Story:** As a user, I want to send certificates to all attendees in one action with a progress indicator, so that I can track the delivery status in real time.

#### Acceptance Criteria

1. WHEN a list of Attendee_Record objects and corresponding certificate files are provided, THE Email_Sender SHALL send one email per attendee with the matching certificate attached.
2. THE Email_Sender SHALL invoke the Progress_Callback after each email send attempt with the current index (1-based) and the total count.
3. IF sending an email to a specific attendee fails, THEN THE Email_Sender SHALL log the error with the attendee email and error message, and continue sending to the remaining attendees.
4. WHEN bulk sending completes, THE Email_Sender SHALL return a Send_Result containing the count and list of successful sends and the count and list of failed sends with error details.
5. THE Email_Sender SHALL maintain the order of send attempts matching the order of the input Attendee_Record list.

### Requirement 8: Handle Email Sending Errors

**User Story:** As a user, I want detailed error reporting for failed sends, so that I can identify and resolve delivery issues.

#### Acceptance Criteria

1. IF an individual email send fails due to a rejected recipient address, THEN THE Email_Sender SHALL record the failure with the recipient email and the SMTP rejection message.
2. IF an individual email send fails due to an attachment exceeding Gmail's 25 MB limit, THEN THE Email_Sender SHALL record the failure indicating the attachment size exceeds the maximum allowed size.
3. IF the SMTP connection is lost during a batch send, THEN THE Email_Sender SHALL attempt to reconnect once and resume sending from the next unsent email.
4. IF reconnection fails after a connection loss, THEN THE Email_Sender SHALL stop the batch, mark all remaining emails as failed with a connection error, and return the partial Send_Result.
5. WHEN the number of emails in a batch exceeds 450, THE Email_Sender SHALL log a warning indicating proximity to Gmail's daily send limit of 500 emails.

### Requirement 9: Load Gmail Credentials

**User Story:** As a user, I want my Gmail credentials loaded automatically from config or environment, so that I don't have to enter them every time.

#### Acceptance Criteria

1. THE Email_Sender SHALL first attempt to load Gmail_Credentials from the .streamlit/secrets.toml file under the key [email] with fields "sender" and "app_password".
2. IF .streamlit/secrets.toml does not contain email credentials, THEN THE Email_Sender SHALL attempt to load credentials from environment variables CERTFLOW_EMAIL_SENDER and CERTFLOW_EMAIL_APP_PASSWORD.
3. IF neither secrets.toml nor environment variables contain valid credentials, THEN THE Email_Sender SHALL raise a ConfigurationError with a message listing both credential sources that were checked.
4. THE Email_Sender SHALL validate that the sender field contains a valid email address format before attempting SMTP connection.

### Requirement 10: Parse and Print Round-Trip Consistency

**User Story:** As a developer, I want to verify that parsing a CSV and writing it back produces an equivalent file, so that I can trust the parser does not lose or corrupt data.

#### Acceptance Criteria

1. FOR ALL valid CSV content containing "name" and "email" columns, parsing then formatting the resulting Attendee_Record list back to CSV SHALL produce a CSV that, when parsed again, yields an identical list of Attendee_Record objects (round-trip property).
2. THE CSV_Parser SHALL provide a format_records method that accepts a list of Attendee_Record objects and returns a valid CSV string with "name" and "email" headers.
3. THE format_records method SHALL produce rows in the same order as the input Attendee_Record list.
