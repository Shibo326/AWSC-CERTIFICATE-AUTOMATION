# Requirements Document

## Introduction

CertFlow is currently a Python application with two frontends: a Streamlit web app (`app.py`) and a Flet native app (`main.py`). This spec addresses converting CertFlow into a fully offline-capable, cross-platform native application that can be packaged and distributed as standalone installers for Android (APK), Windows (EXE), iOS (IPA), and macOS (APP). The goal is to eliminate server dependency for certificate generation while preserving email-sending capability when connectivity is available.

### QA Analysis Summary

A deep QA/tester review of the existing system reveals the following areas that need change:

1. **UI Framework Gap**: The Flet `main.py` exists but lacks feature parity with the Streamlit app (no font selection, no font manager, no download-more-fonts feature)
2. **Font Bundling**: The project bundles 43 fonts (~15MB). On mobile, this inflates APK/IPA size significantly and needs a selective bundling or lazy-download strategy
3. **File Storage**: Current code uses `tempfile` and relative paths. Mobile platforms require platform-specific storage directories
4. **Credential Storage**: `credentials.toml` and `.streamlit/secrets.toml` are not appropriate for mobile. Need secure keychain/keystore integration
5. **Streamlit Dependency**: `app.py` and `email_sender.py` still import Streamlit for secrets. The native app path must not depend on Streamlit
6. **PDF Library Constraints**: PyMuPDF (fitz) has binary dependencies that must be verified for each target platform's architecture
7. **Offline Validation**: No network-state detection — email sending will silently fail if offline
8. **Build Pipeline**: `build.bat` exists but lacks CI/CD, code signing, and platform-specific asset configuration

## Glossary

- **CertFlow_App**: The Flet-based cross-platform native application (main.py entry point)
- **Template**: A PNG, JPG, or PDF file used as the certificate background
- **Attendee_List**: A CSV or XLSX file containing name and email columns
- **Certificate_Generator**: The orchestrator module that coordinates rendering names onto templates
- **Font_Manager**: The component responsible for discovering, bundling, and loading TTF font files
- **Credential_Store**: The platform-specific secure storage for Gmail SMTP credentials (Keychain on macOS/iOS, Keystore on Android, DPAPI on Windows)
- **Offline_Mode**: Application state where no internet connection is available; certificate generation works fully, email sending is queued
- **Email_Queue**: A local persistence mechanism that stores unsent emails for later delivery when connectivity returns
- **Build_Pipeline**: The automated process that produces platform-specific distributable packages from the Python/Flet source

## Requirements

### Requirement 1: Offline Certificate Generation

**User Story:** As a user, I want to generate certificates without any internet connection, so that I can use CertFlow in environments without network access (schools, events, fieldwork).

#### Acceptance Criteria

1. THE CertFlow_App SHALL generate certificates from PNG, JPG, and PDF templates using only locally available resources, with no outbound network requests initiated during template loading, name rendering, or file output
2. THE CertFlow_App SHALL load and render all TTF font files bundled in the application assets directory without network access
3. THE CertFlow_App SHALL parse CSV and XLSX attendee lists containing up to 10,000 rows without network access
4. THE CertFlow_App SHALL produce certificate output files in the same format as the input template (PNG, JPG, or PDF) and store them in the platform-appropriate local storage directory (app sandbox on mobile, user-selected or working directory on desktop)
5. THE CertFlow_App SHALL complete all generation features (template loading, attendee parsing, name rendering, and file output) without behavioral differences regardless of device internet connectivity
6. IF the CertFlow_App detects that a required asset (font file or template) is missing from local storage, THEN THE CertFlow_App SHALL display an error message that includes the asset type, the expected file name, and the expected storage location
7. IF the CertFlow_App cannot parse the uploaded attendee file due to corruption, unsupported encoding, or missing required columns (name, email), THEN THE CertFlow_App SHALL display an error message indicating the specific parsing failure reason without attempting any network request
8. IF an attendee name exceeds the template width when rendered with the configured font and size, THEN THE CertFlow_App SHALL report a text overflow error for that attendee and continue processing the remaining attendees in the batch

### Requirement 2: Platform-Specific File Storage

**User Story:** As a user, I want generated certificates saved to an accessible location on my device, so that I can find and share them after generation.

#### Acceptance Criteria

1. WHILE running on Windows, THE CertFlow_App SHALL store generated certificates in the user's Documents folder under a `CertFlow` subdirectory
2. WHILE running on macOS, THE CertFlow_App SHALL store generated certificates in `~/Documents/CertFlow/`
3. WHILE running on Android, THE CertFlow_App SHALL store generated certificates in the app's external files directory accessible via the system file manager
4. WHILE running on iOS, THE CertFlow_App SHALL store generated certificates in the app's Documents directory accessible via the Files app
5. IF the output directory does not exist at the time of writing certificate files, THEN THE CertFlow_App SHALL create the full directory path before writing
6. THE CertFlow_App SHALL construct each certificate filename by sanitizing the attendee name (replacing characters that are not alphanumeric or spaces with underscores, then replacing spaces with underscores), appending the output format extension (`.png`, `.jpg`, or `.pdf`), and truncating the base name to a maximum of 200 characters before the extension
7. IF two or more attendees produce the same sanitized filename within a single batch, THEN THE CertFlow_App SHALL append a numeric suffix (e.g., `_2`, `_3`) to each duplicate filename to ensure all filenames in the output directory are unique
8. IF a certificate file cannot be written to the output directory due to a filesystem error, THEN THE CertFlow_App SHALL log the failure for that attendee, skip that file, and continue processing the remaining certificates in the batch

### Requirement 3: Secure Credential Management

**User Story:** As a user, I want my Gmail credentials stored securely on my device, so that my app password is not exposed in plain text configuration files.

#### Acceptance Criteria

1. WHILE running on Windows, THE Credential_Store SHALL store Gmail credentials using Windows DPAPI (encrypted in the user's profile)
2. WHILE running on macOS, THE Credential_Store SHALL store Gmail credentials in the macOS Keychain
3. WHILE running on iOS, THE Credential_Store SHALL store Gmail credentials in the iOS Keychain
4. WHILE running on Android, THE Credential_Store SHALL store Gmail credentials in the Android Keystore
5. THE CertFlow_App SHALL provide a credentials setup screen containing a Gmail address text field (maximum 254 characters) and an App Password text field (masked input, accepting exactly 16 alphabetic characters with optional spaces ignored)
6. WHEN the user submits credentials on the setup screen, THE CertFlow_App SHALL validate that the email address conforms to the pattern `local-part@gmail.com` and that the app password contains exactly 16 alphabetic characters (after stripping spaces), and SHALL display a field-specific error message indicating which validation rule failed before any storage attempt
7. IF platform-specific secure storage is unavailable due to permission denial, missing system service, or runtime error, THEN THE Credential_Store SHALL fall back to an encrypted `credentials.toml` file stored in the user's home directory at `~/.certflow/credentials.toml`
8. IF stored credentials fail SMTP authentication, THEN THE CertFlow_App SHALL display the credentials setup screen with the Gmail address pre-filled and the App Password field empty, along with an error message indicating authentication failed
9. THE CertFlow_App SHALL display on the credentials setup screen whether credentials are currently stored (stored or not configured), and SHALL provide a "Clear Credentials" action that removes the stored credentials from the platform credential store and returns the screen to the not-configured state

### Requirement 4: Network-Aware Email Sending

**User Story:** As a user, I want CertFlow to handle network availability gracefully, so that I can prepare certificates offline and send emails when connectivity becomes available.

#### Acceptance Criteria

1. WHEN the user initiates email sending, THE CertFlow_App SHALL attempt a TCP connection to smtp.gmail.com:587 within 5 seconds to verify network connectivity before proceeding with SMTP authentication
2. IF the connectivity check fails or times out, THEN THE CertFlow_App SHALL queue the entire email batch in the Email_Queue and display a notification message indicating the number of emails queued and that they will be sent when connectivity returns
3. WHILE network connectivity is available, THE CertFlow_App SHALL check the Email_Queue every 30 seconds and process any pending emails automatically
4. THE Email_Queue SHALL persist unsent emails (including recipient address, attendee name, certificate attachment data, and retry count) to local storage so they survive app restarts
5. THE CertFlow_App SHALL display the current queue status including the number of pending emails, the number of permanently failed emails, and the timestamp of the last send attempt
6. IF an email delivery fails due to a socket error or connection timeout during SMTP sending (excluding authentication failures and recipient-rejected errors), THEN THE CertFlow_App SHALL increment that email's retry count and move it back to the Email_Queue for retry on the next processing cycle
7. IF an email in the Email_Queue has reached 3 failed retry attempts, THEN THE CertFlow_App SHALL mark that email as permanently failed, remove it from the pending queue, and display it in the queue status as failed with the last error reason
8. WHEN all queued emails in a batch have been processed (either sent successfully or marked as permanently failed), THE CertFlow_App SHALL display a summary notification indicating the number of emails sent successfully and the number that permanently failed

### Requirement 5: Font Management for Native Apps

**User Story:** As a user, I want access to a variety of fonts for my certificates, so that I can customize the appearance for different event types.

#### Acceptance Criteria

1. THE CertFlow_App SHALL bundle a core set of 5 default fonts (Arial, Roboto, Montserrat, PlayfairDisplay, GreatVibes) in the application package
2. THE Font_Manager SHALL allow users to import additional TTF font files from the device's file system, accepting only files with a .ttf extension and a maximum file size of 10 MB per font
3. THE Font_Manager SHALL store imported fonts in the app's local data directory and persist them across app sessions
4. THE CertFlow_App SHALL display a font selection dropdown showing all available fonts (bundled and imported) where each entry renders the font's own name in that font as preview text
5. THE Font_Manager SHALL validate that imported files are valid TTF fonts by confirming the file can be parsed and at least one glyph table is present before adding them to the font list
6. IF a font file is corrupted or unreadable, THEN THE Font_Manager SHALL display an error message indicating the file is not a valid TTF font, reject the import, and exclude the font from the selection list
7. WHEN a user selects an imported font for removal, THE Font_Manager SHALL delete the font file from local storage and remove it from the selection list within the current session
8. THE Font_Manager SHALL enforce a maximum limit of 20 imported fonts, and IF the user attempts to import a font when the limit is reached, THEN THE Font_Manager SHALL display an error message indicating the maximum number of imported fonts has been reached

### Requirement 6: Windows Desktop Build

**User Story:** As a user, I want to install CertFlow as a native Windows application, so that I can use it without Python or command-line knowledge.

#### Acceptance Criteria

1. THE Build_Pipeline SHALL produce a standalone Windows executable (.exe) using `flet build windows`
2. THE Build_Pipeline SHALL bundle all Python dependencies listed in `requirements.txt`, all font files in the `assets/fonts/` directory, and all files in the `assets/` directory into the Windows package such that the application can perform certificate generation, PDF rendering, and email sending without missing module or file errors
3. WHEN the executable is launched on a Windows 10 or later system that does not have Python, pip, or any external runtime installed, THE CertFlow_App SHALL display the main application window within 30 seconds of launch
4. THE Build_Pipeline SHALL configure the Windows executable with a CertFlow application icon and metadata (product name, version, publisher)
5. THE Build_Pipeline SHALL produce a Windows build under 100MB in total size
6. IF the `flet build windows` command exits with a non-zero exit code, THEN THE Build_Pipeline SHALL report the build as failed and output the error details to the console

### Requirement 7: Android APK Build

**User Story:** As a user, I want to install CertFlow on my Android phone, so that I can generate and send certificates from my mobile device.

#### Acceptance Criteria

1. THE Build_Pipeline SHALL produce a signed Android APK using `flet build apk` that can be installed on a physical device or emulator without errors
2. THE CertFlow_App SHALL request only the following Android permissions: INTERNET (for email), READ_EXTERNAL_STORAGE (for template/CSV import on Android 12 and below), and POST_NOTIFICATIONS (for queue status on Android 13+)
3. THE CertFlow_App SHALL support Android API level 24 (Android 7.0) as the minimum supported version and target the latest stable API level supported by the Flet/Flutter SDK at build time
4. THE Build_Pipeline SHALL configure the APK with the CertFlow application icon, package name (com.certflow.app), and version string matching the version defined in pyproject.toml
5. WHEN the user initiates a file import on Android, THE CertFlow_App SHALL launch the system file picker filtered to the accepted file types: PNG, JPG, and PDF for templates, and CSV and XLSX for attendee files
6. THE Build_Pipeline SHALL produce an APK under 80MB in total size
7. WHILE the device is in portrait orientation or the screen width is below 600dp, THE CertFlow_App SHALL display a single-column layout; WHILE the device is in landscape orientation or the screen width is 600dp or above, THE CertFlow_App SHALL display a two-column layout
8. IF the user denies a required permission (storage or notifications), THEN THE CertFlow_App SHALL display a message indicating which permission is needed and why, and SHALL allow the user to continue using features that do not require the denied permission
9. WHEN running on Android 13 or above, THE CertFlow_App SHALL use the system photo picker or scoped storage APIs for file import instead of READ_EXTERNAL_STORAGE, without requiring broad storage access

### Requirement 8: macOS Application Build

**User Story:** As a user, I want to install CertFlow as a macOS application, so that I can use it natively on my Mac.

#### Acceptance Criteria

1. THE Build_Pipeline SHALL produce a macOS application bundle (.app) using `flet build macos`
2. THE CertFlow_App SHALL start without requiring Python, pip, or Homebrew installed on the user's system
3. THE Build_Pipeline SHALL configure the macOS bundle with CertFlow application icon, bundle identifier (com.certflow.app), version string matching pyproject.toml version, and build number
4. THE Build_Pipeline SHALL code-sign the application with a Developer ID certificate and submit it to Apple's notarization service, producing a stapled .app that passes Gatekeeper verification without user override
5. THE CertFlow_App SHALL support macOS 12 (Monterey) as the minimum supported version
6. THE Build_Pipeline SHALL produce a macOS build under 120MB in total size
7. THE Build_Pipeline SHALL configure macOS entitlements to allow outbound network connections (SMTP) and user-selected file read access for loading templates and attendee lists
8. IF code signing or notarization fails, THEN THE Build_Pipeline SHALL exit with a non-zero status code and display an error message indicating the failing step and reason

### Requirement 9: iOS Application Build

**User Story:** As a user, I want to install CertFlow on my iPhone/iPad, so that I can generate certificates on the go.

#### Acceptance Criteria

1. THE Build_Pipeline SHALL produce an iOS application archive (.ipa) using `flet build ipa`
2. THE CertFlow_App SHALL request only the minimum required iOS permissions: network access (for email sending)
3. THE Build_Pipeline SHALL configure the iOS bundle with CertFlow application icon, bundle identifier (com.certflow.app), version string matching the project version in pyproject.toml, and build number
4. THE CertFlow_App SHALL support iOS 16 as the minimum deployment target
5. THE CertFlow_App SHALL use the iOS document picker for importing templates (filtered to PNG, JPG, and PDF files up to 10 MB) and attendee files (filtered to CSV and XLSX files up to 5 MB)
6. THE CertFlow_App SHALL render all UI elements without truncation or overlap on iPhone devices (screen width 320-430 points) using a single-column layout and on iPad devices (screen width 768-1024 points) using a multi-column layout where customization and email template sections appear side by side
7. IF the Apple Developer provisioning profile or signing certificate is missing or invalid, THEN THE Build_Pipeline SHALL fail the build and produce an error message indicating the signing configuration issue
8. IF network connectivity is unavailable when the user initiates email sending, THEN THE CertFlow_App SHALL display an error message indicating that network access is required and SHALL preserve all generated certificates and email settings without data loss

### Requirement 10: Eliminate Streamlit Dependency in Core Modules

**User Story:** As a developer, I want the core utility modules to have no dependency on Streamlit, so that the native app builds cleanly without web framework overhead.

#### Acceptance Criteria

1. THE Certificate_Generator module SHALL not contain any `import streamlit` or `from streamlit` statements, directly or transitively through other utils/ modules
2. THE Email_Sender module SHALL load credentials using a platform-agnostic fallback chain: first from a `credentials.toml` file (checked in the application directory, then in `~/.certflow/`), then from environment variables (`CERTFLOW_EMAIL_SENDER`, `CERTFLOW_EMAIL_APP_PASSWORD`), without importing Streamlit
3. THE native app build configuration (pyproject.toml and requirements used by `flet build`) SHALL not list Streamlit or streamlit-image-coordinates as dependencies
4. THE Email_Sender module SHALL raise a ConfigurationError with a message identifying all checked credential sources IF no valid credentials are found in any source in the fallback chain
5. THE FontConfiguration module SHALL resolve the default font path relative to the application's bundled assets directory (as declared in pyproject.toml `[tool.flet] assets`), not relative to the current working directory
6. WHEN building for native platforms (Windows, macOS, Android, iOS) using `flet build`, THE build output SHALL not include Streamlit or any of its transitive dependencies in the packaged application
7. IF the Streamlit web frontend (app.py) requires access to credentials via `st.secrets`, THEN THE web frontend SHALL adapt credentials from `st.secrets` into the same GmailCredentials model before passing them to Email_Sender, rather than Email_Sender importing Streamlit internally

### Requirement 11: Responsive UI Parity with Streamlit App

**User Story:** As a user, I want the native app to have all the features of the web version, so that switching to the native app does not reduce my capabilities.

#### Acceptance Criteria

1. WHEN the user uploads a template, THE CertFlow_App SHALL display a preview within 2 seconds showing the image for PNG/JPG files or a rendered first-page image for PDF files
2. WHEN the user uploads an attendee list, THE CertFlow_App SHALL parse the file and display the count of valid attendees, and IF validation errors exist, THEN THE CertFlow_App SHALL display each error with its row number, field name, and error message
3. THE CertFlow_App SHALL provide font selection listing all .ttf fonts found in the `assets/fonts/` directory, a font size slider with range 10-120 points, a font color picker accepting hex color values, and a vertical position slider with range 0-100% (0% = top, 100% = bottom)
4. WHEN the user adjusts any font or position setting, THE CertFlow_App SHALL update the certificate preview within 2 seconds, rendering the first attendee's name on the template with the current settings
5. WHEN the user initiates batch generation, THE CertFlow_App SHALL display a progress indicator showing the current count and total count of certificates being generated (e.g., "Generating 5 of 20")
6. WHEN batch generation completes, THE CertFlow_App SHALL display a certificate review gallery with previous/next navigation controls and a counter showing the current index and total count (e.g., "3 / 20")
7. WHEN the user edits an attendee name from the review gallery, THE CertFlow_App SHALL regenerate that single certificate with the updated name and display the result in the gallery without regenerating other certificates
8. THE CertFlow_App SHALL provide ZIP download containing all generated certificates, each named with the attendee's sanitized name and original template format extension
9. THE CertFlow_App SHALL provide email composition with a subject field, a multi-line body field, and support for a {name} placeholder that is replaced with each attendee's name on send
10. WHEN the user initiates bulk email sending, THE CertFlow_App SHALL display progress showing the current count and total (e.g., "Sending 3 of 20"), and WHEN sending completes, THE CertFlow_App SHALL report the total sent count, total failed count, and for each failure the attendee name and error description
11. WHILE the app is running in portrait orientation on a device with screen width below 600px, THE CertFlow_App SHALL render all workflow steps in a single-column layout, and WHILE in landscape orientation on a device with screen width of 600px or above, THE CertFlow_App SHALL use multi-column layout for the customization step

### Requirement 12: Application Data and State Persistence

**User Story:** As a user, I want my in-progress work preserved if I close the app, so that I do not lose my template, attendee list, and generated certificates.

#### Acceptance Criteria

1. WHEN the user modifies any persisted setting (template file path, attendee list file path, font size, font color, vertical position, email subject, or email body), THE CertFlow_App SHALL save the updated value to client storage within 2 seconds of the change
2. THE CertFlow_App SHALL persist the last-used template file path and format across app sessions
3. THE CertFlow_App SHALL persist the last-used attendee list file path across app sessions
4. THE CertFlow_App SHALL persist customization settings (font family, font size, font color, vertical position) across app sessions
5. THE CertFlow_App SHALL persist email template (subject and body) across app sessions
6. WHEN the app is launched and persisted session state exists, THE CertFlow_App SHALL restore all saved settings and display the previously used template file path and attendee list file path, enabling the user to confirm reloading those files
7. IF the app is launched and a persisted file path references a file that no longer exists or is inaccessible, THEN THE CertFlow_App SHALL display a notification indicating which file is unavailable, clear that specific path from the persisted state, and allow the user to continue with the remaining restored settings
8. IF the app is launched and the persisted state data is missing or cannot be read, THEN THE CertFlow_App SHALL start with default settings without displaying an error to the user
9. THE CertFlow_App SHALL store session state in a platform-appropriate configuration directory (AppData on Windows, Application Support on macOS, app data on mobile)
