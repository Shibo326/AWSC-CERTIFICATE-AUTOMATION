# Requirements Document

## Introduction

The Streamlit UI Application (app.py) is the web-based frontend for CertFlow — a certificate automation system that generates personalized certificates and sends them to attendees via email in bulk. This module provides the complete user interface built with Streamlit, guiding users through a step-by-step workflow: uploading a certificate template, uploading an attendee CSV, customizing font and email settings, previewing a sample certificate, and executing the bulk send operation. It integrates with utils/certificate_generator.py, utils/csv_parser.py, and utils/email_sender.py as backend services.

## Glossary

- **Streamlit_App**: The main Streamlit application (app.py) that serves as the frontend interface for CertFlow.
- **Template_Uploader**: The file upload widget that accepts certificate template files (PNG, JPG, PDF) with a maximum size of 10MB.
- **CSV_Uploader**: The file upload widget that accepts attendee CSV files with a maximum size of 5MB.
- **Customization_Panel**: The section of the UI containing font size slider, color picker, vertical position slider, email subject input, and email body input.
- **Preview_Panel**: The section of the UI that renders a sample certificate using the first attendee name from the uploaded CSV.
- **Send_Controller**: The component that manages the bulk send operation including confirmation dialog, progress tracking, and error collection.
- **Progress_Tracker**: The real-time progress bar and status display that updates as each attendee certificate is generated and sent.
- **ZIP_Generator**: The component that packages all generated certificates into a single ZIP file for download.
- **Session_State**: Streamlit's session state mechanism used to persist uploaded files, configuration, and operation results across reruns.
- **Sidebar_Panel**: The left sidebar area displaying Gmail settings status and application information.
- **Error_Log**: The expandable UI section that displays details of failed certificate sends without interrupting the batch operation.

## Requirements

### Requirement 1: Application Layout and Navigation

**User Story:** As a user, I want a clear step-by-step layout, so that I can follow the certificate generation workflow without confusion.

#### Acceptance Criteria

1. THE Streamlit_App SHALL display a Sidebar_Panel containing Gmail settings connection status and application version information.
2. THE Streamlit_App SHALL organize the main content area into five sequential steps: Upload Template, Upload CSV, Customize, Preview, and Send.
3. THE Streamlit_App SHALL display a step number and descriptive heading for each workflow section.
4. THE Streamlit_App SHALL render correctly on both desktop and mobile viewport widths using Streamlit's responsive layout.

### Requirement 2: Certificate Template Upload

**User Story:** As a user, I want to upload my certificate template, so that I can use it as the base design for generating personalized certificates.

#### Acceptance Criteria

1. THE Template_Uploader SHALL accept files with extensions .png, .jpg, .jpeg, and .pdf only.
2. WHEN a file with an unsupported extension is selected, THE Template_Uploader SHALL display an error message listing the supported formats (PNG, JPG, PDF).
3. IF the uploaded template file exceeds 10MB in size, THEN THE Streamlit_App SHALL display an error message indicating the file exceeds the maximum allowed size of 10MB.
4. WHEN a valid template file is uploaded, THE Streamlit_App SHALL store the file in Session_State for use across reruns.
5. WHEN a valid template file is uploaded, THE Streamlit_App SHALL display a preview thumbnail of the template image in the Upload Template section.
6. WHEN a PDF template is uploaded, THE Streamlit_App SHALL render the first page of the PDF as the preview thumbnail.
7. THE Streamlit_App SHALL display a success indicator (green checkmark or success message) in the Upload Template step after a valid file is uploaded.

### Requirement 3: Attendee CSV Upload

**User Story:** As a user, I want to upload a CSV file of attendees, so that the system knows who to generate certificates for.

#### Acceptance Criteria

1. THE CSV_Uploader SHALL accept files with the .csv extension only.
2. IF the uploaded CSV file exceeds 5MB in size, THEN THE Streamlit_App SHALL display an error message indicating the file exceeds the maximum allowed size of 5MB.
3. WHEN a valid CSV file is uploaded, THE Streamlit_App SHALL store the parsed attendee data in Session_State.
4. WHEN a valid CSV file is uploaded, THE Streamlit_App SHALL display the total number of attendees parsed from the file.
5. IF the CSV file contains parsing errors (missing name column, empty rows, invalid encoding), THEN THE Streamlit_App SHALL display a warning message listing the specific errors found.
6. WHEN a CSV file with parsing errors still contains valid attendee entries, THE Streamlit_App SHALL display both the valid attendee count and the error details.
7. THE Streamlit_App SHALL display a success indicator in the Upload CSV step after a valid file with at least one attendee is uploaded.

### Requirement 4: Font and Position Customization

**User Story:** As a user, I want to customize font settings and name position, so that the generated certificates match my design preferences.

#### Acceptance Criteria

1. THE Customization_Panel SHALL provide a slider for font size selection with a range of 10 to 120 points and a default value of 40 points.
2. THE Customization_Panel SHALL provide a color picker for font color selection with a default value of black (#000000).
3. THE Customization_Panel SHALL provide a slider for vertical position as a percentage (0-100) with a default value of 50 (vertical center).
4. WHEN the user adjusts any customization control, THE Streamlit_App SHALL store the updated value in Session_State.
5. THE Customization_Panel SHALL display the current numeric values for font size and vertical position alongside their respective sliders.

### Requirement 5: Email Configuration

**User Story:** As a user, I want to configure the email subject and body, so that attendees receive personalized emails with their certificates.

#### Acceptance Criteria

1. THE Customization_Panel SHALL provide a text input field for the email subject line.
2. THE Customization_Panel SHALL provide a text area for the email body content.
3. THE Streamlit_App SHALL support a {name} placeholder in both the email subject and email body fields that gets replaced with each attendee's name during sending.
4. THE Streamlit_App SHALL display helper text below the email body field explaining the available {name} placeholder syntax.
5. WHEN the email subject field is empty, THE Streamlit_App SHALL display a validation warning indicating the subject is required before sending.
6. WHEN the email body field is empty, THE Streamlit_App SHALL display a validation warning indicating the body is required before sending.

### Requirement 6: Live Certificate Preview

**User Story:** As a user, I want to see a preview of a generated certificate before sending, so that I can verify the font, position, and overall appearance.

#### Acceptance Criteria

1. WHEN both a template and a CSV file with at least one attendee are uploaded, THE Preview_Panel SHALL render a sample certificate using the first attendee name from the CSV.
2. THE Preview_Panel SHALL apply the current font size, font color, and vertical position settings to the preview rendering.
3. WHEN the user changes any customization setting (font size, color, or position), THE Preview_Panel SHALL re-render the preview with the updated settings.
4. THE Preview_Panel SHALL display the preview certificate as an image within the Streamlit main area.
5. IF the preview rendering fails due to an error, THEN THE Streamlit_App SHALL display an error message describing the rendering failure in the Preview section.

### Requirement 7: Send Operation with Confirmation

**User Story:** As a user, I want a confirmation step before sending, so that I do not accidentally trigger a bulk email operation.

#### Acceptance Criteria

1. THE Send_Controller SHALL disable the Send button until all required inputs are provided: a valid template, a valid CSV with at least one attendee, a non-empty email subject, and a non-empty email body.
2. WHEN the user clicks the Send button, THE Streamlit_App SHALL display a confirmation dialog showing the total number of attendees and asking the user to confirm the operation.
3. WHEN the user confirms the send operation, THE Send_Controller SHALL initiate the bulk certificate generation and email sending process.
4. WHEN the user cancels the confirmation dialog, THE Streamlit_App SHALL return to the Send step without initiating any operation.
5. WHILE a send operation is in progress, THE Send_Controller SHALL disable the Send button to prevent duplicate submissions.

### Requirement 8: Real-Time Progress Tracking

**User Story:** As a user, I want to see real-time progress during sending, so that I know how the bulk operation is progressing.

#### Acceptance Criteria

1. WHEN a send operation begins, THE Progress_Tracker SHALL display a progress bar starting at 0 percent.
2. WHILE certificates are being generated and sent, THE Progress_Tracker SHALL update the progress bar after each attendee is processed, calculated as (processed_count / total_attendees) * 100.
3. THE Progress_Tracker SHALL display a text status showing the current count in the format "Processing X of Y attendees".
4. WHEN the send operation completes, THE Progress_Tracker SHALL display a summary showing the number of successful sends and the number of failures.
5. WHEN all attendees are processed successfully, THE Streamlit_App SHALL display a success message indicating all certificates were sent.

### Requirement 9: Error Log Display

**User Story:** As a user, I want to see which sends failed and why, so that I can address issues and retry if needed.

#### Acceptance Criteria

1. WHEN one or more sends fail during a batch operation, THE Error_Log SHALL display the count of failed sends as a warning message.
2. THE Error_Log SHALL provide an expandable section containing the details of each failure, including the attendee name and the error description.
3. THE Error_Log SHALL list failed entries in the order they occurred during processing.
4. WHILE errors are being collected during a batch send, THE Error_Log SHALL not interrupt or halt the processing of remaining attendees.

### Requirement 10: ZIP Download of Generated Certificates

**User Story:** As a user, I want to download all generated certificates as a ZIP file, so that I can keep local copies without downloading them one by one.

#### Acceptance Criteria

1. WHEN a send operation completes (regardless of partial failures), THE ZIP_Generator SHALL package all successfully generated certificates into a single ZIP archive.
2. THE Streamlit_App SHALL display a download button for the ZIP file after the send operation completes.
3. THE ZIP_Generator SHALL name each certificate file inside the ZIP using the attendee name (e.g., "John_Doe.png" or "John_Doe.pdf").
4. THE ZIP_Generator SHALL preserve the original certificate file format (PNG, JPG, or PDF) inside the ZIP archive.
5. IF no certificates were successfully generated, THEN THE Streamlit_App SHALL not display the download button.

### Requirement 11: Session State Management

**User Story:** As a user, I want my uploaded files and settings to persist during the session, so that I do not lose progress when the page reruns.

#### Acceptance Criteria

1. THE Streamlit_App SHALL store the uploaded template file in Session_State upon successful upload.
2. THE Streamlit_App SHALL store the parsed attendee data in Session_State upon successful CSV upload.
3. THE Streamlit_App SHALL store all customization settings (font size, font color, vertical position, email subject, email body) in Session_State.
4. THE Streamlit_App SHALL store the send operation results (progress, successes, failures, generated certificates) in Session_State.
5. WHEN the user uploads a new template file, THE Streamlit_App SHALL replace the previously stored template in Session_State and clear any cached preview.
6. WHEN the user uploads a new CSV file, THE Streamlit_App SHALL replace the previously stored attendee data in Session_State and clear any cached preview.

### Requirement 12: Input Validation and Send Readiness

**User Story:** As a user, I want clear feedback on what is missing before I can send, so that I can complete all required steps.

#### Acceptance Criteria

1. THE Streamlit_App SHALL evaluate send readiness by verifying: a valid template is uploaded, a valid CSV with at least one attendee is uploaded, the email subject is non-empty, and the email body is non-empty.
2. WHEN any required input is missing, THE Streamlit_App SHALL display the Send button in a disabled state.
3. WHEN any required input is missing, THE Streamlit_App SHALL display a message listing which inputs still need to be provided.
4. WHEN all required inputs are provided, THE Streamlit_App SHALL enable the Send button and display a ready-to-send indicator.

### Requirement 13: Sidebar Gmail Settings Display

**User Story:** As a user, I want to see my Gmail connection status in the sidebar, so that I know the email service is properly configured before attempting to send.

#### Acceptance Criteria

1. THE Sidebar_Panel SHALL display the current Gmail settings connection status (connected or not configured).
2. WHEN Gmail settings are not configured, THE Sidebar_Panel SHALL display a warning message indicating email sending will not work until settings are provided.
3. THE Sidebar_Panel SHALL display the application name "CertFlow" and version information.
4. THE Sidebar_Panel SHALL display a brief description of the application's purpose.
