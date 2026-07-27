# Implementation Plan: Offline Cross-Platform App

## Overview

Convert CertFlow from a Streamlit-dependent web application into a fully offline-capable, cross-platform native application using Flet. This plan implements the architecture in phases: first eliminating Streamlit from core modules, then building platform services (storage, credentials, queue, network), revising the font manager, adding state persistence, building the Flet UI with responsive layout, and finally configuring the build pipeline for all four target platforms.

## Tasks

- [x] 1. Refactor core modules to eliminate Streamlit dependency
  - [x] 1.1 Remove Streamlit imports from EmailSender and implement platform-agnostic credential loading
    - Remove `import streamlit as st` and all `st.secrets` references from `utils/email_sender.py`
    - Implement the credential fallback chain: (1) `credentials.toml` in app directory, (2) `~/.certflow/credentials.toml`, (3) environment variables `CERTFLOW_EMAIL_SENDER` / `CERTFLOW_EMAIL_APP_PASSWORD`
    - Raise `ConfigurationError` listing all checked sources if no credentials found
    - Ensure no transitive Streamlit imports exist in any `utils/` module
    - _Requirements: 10.1, 10.2, 10.4_

  - [x] 1.2 Update FontConfiguration to resolve paths relative to bundled assets directory
    - Modify `utils/font_config.py` to resolve the default font path relative to the application's bundled assets directory as declared in `pyproject.toml [tool.flet] assets`
    - Add a helper function to determine the assets root directory at runtime (handles both development and packaged app scenarios)
    - _Requirements: 10.5_

  - [x] 1.3 Create a Streamlit adapter layer for the web frontend
    - Create `app_adapter.py` (or modify `app.py`) so that the Streamlit frontend adapts `st.secrets` into `GmailCredentials` before passing to `EmailSender`
    - Ensure `EmailSender` itself never imports Streamlit
    - _Requirements: 10.7_

  - [x] 1.4 Update pyproject.toml and requirements for native builds
    - Create a `requirements-native.txt` (or configure pyproject.toml `[tool.flet]` dependencies) that excludes Streamlit and streamlit-image-coordinates
    - Ensure all required runtime dependencies (Pillow, PyMuPDF, ReportLab, openpyxl, flet, flet-secure-storage) are listed
    - _Requirements: 10.3, 10.6_

- [x] 2. Implement PlatformStorage module
  - [x] 2.1 Create `utils/platform_storage.py` with platform-aware directory resolution
    - Implement `PlatformStorage` class with `get_output_directory()` returning platform-appropriate paths:
      - Windows: `~/Documents/CertFlow/`
      - macOS: `~/Documents/CertFlow/`
      - Android: app external files directory
      - iOS: app Documents directory
    - Implement `get_app_data_directory()` for internal app data paths
    - Implement `ensure_directory()` to create full directory tree if missing
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 2.2 Implement filename sanitization and deduplication logic
    - Implement `sanitize_filename(name, extension)`:
      - Replace non-alphanumeric/non-space characters with underscore
      - Replace spaces with underscores
      - Truncate base name to 200 characters
      - Append the correct extension
    - Implement `deduplicate_filename(filename, existing_set)` to append `_2`, `_3`, etc. for duplicates
    - _Requirements: 2.6, 2.7_

  - [x] 2.3 Implement certificate file writing with error handling
    - Implement `write_certificate(filename, data)` that writes to the output directory
    - On filesystem error (permission denied, disk full), log failure, return error message, and allow batch to continue
    - _Requirements: 2.8_

  - [ ]* 2.4 Write property tests for filename sanitization (Property 4)
    - **Property 4: Filename sanitization correctness**
    - Use hypothesis to generate arbitrary Unicode strings as attendee names
    - Verify sanitized output contains only alphanumeric + underscore, base ≤ 200 chars, ends with correct extension
    - **Validates: Requirements 2.6**

  - [ ]* 2.5 Write property tests for filename deduplication (Property 5)
    - **Property 5: Filename deduplication guarantees uniqueness**
    - Use hypothesis to generate lists of names with intentional duplicates
    - Verify all resulting filenames are unique after sanitization + deduplication
    - **Validates: Requirements 2.7**

- [x] 3. Implement CredentialStore module
  - [x] 3.1 Create `utils/credential_store.py` with secure storage integration
    - Implement `CredentialStore` class using `flet-secure-storage`
    - Implement `store(email, app_password)`, `load()`, `clear()`, `is_configured()` async methods
    - Keys: `certflow_email`, `certflow_app_password`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Implement credential validation logic
    - Implement `validate_email(email)`: accept only `local-part@gmail.com` pattern (max 254 chars)
    - Implement `validate_app_password(raw)`: strip spaces, accept exactly 16 alphabetic characters
    - Return field-specific error messages on validation failure
    - _Requirements: 3.5, 3.6_

  - [x] 3.3 Implement fallback to encrypted credentials.toml
    - If `flet-secure-storage` raises permission or availability errors, fall back to `~/.certflow/credentials.toml`
    - _Requirements: 3.7_

  - [ ]* 3.4 Write property tests for credential validation (Property 6)
    - **Property 6: Credential validation correctness**
    - Use hypothesis to generate random strings for email and password inputs
    - Verify validator accepts iff email matches `local-part@gmail.com` and password has exactly 16 alpha chars after stripping spaces
    - **Validates: Requirements 3.6**

- [x] 4. Implement EmailQueueManager module
  - [x] 4.1 Create `utils/email_queue.py` with QueuedEmail dataclass and JSON persistence
    - Define `QueuedEmail` and `QueueStatus` dataclasses
    - Implement `EmailQueueManager` class with JSON file storage at `{app_data_dir}/email_queue.json`
    - Implement `enqueue()`, `dequeue_pending()`, `mark_sent()`, `mark_failed()` methods
    - Implement `get_status()` returning pending count, failed count, last attempt timestamp
    - _Requirements: 4.2, 4.4, 4.5_

  - [x] 4.2 Implement retry logic and permanent failure marking
    - On socket error / connection timeout: increment `retry_count`, keep in pending queue
    - When `retry_count >= 3`: mark as permanently failed, remove from pending
    - Implement `get_permanently_failed()` to list exhausted emails
    - _Requirements: 4.6, 4.7_

  - [ ]* 4.3 Write property tests for offline queueing completeness (Property 7)
    - **Property 7: Offline queueing preserves entire batch**
    - Generate random batch sizes, mock network as offline, verify queue contains exactly N entries
    - **Validates: Requirements 4.2**

  - [ ]* 4.4 Write property tests for queue serialization round-trip (Property 8)
    - **Property 8: Email queue serialization round-trip**
    - Generate random lists of QueuedEmail objects, serialize to JSON, deserialize, verify field-by-field equality
    - **Validates: Requirements 4.4**

  - [ ]* 4.5 Write property tests for retry count increment (Property 9)
    - **Property 9: Socket failure increments retry count**
    - Generate emails with retry_count 0-2, simulate socket failure, verify retry_count incremented by exactly 1 and email remains pending
    - **Validates: Requirements 4.6**

- [x] 5. Implement NetworkMonitor module
  - [x] 5.1 Create `utils/network_monitor.py` with TCP probe and polling
    - Implement `NetworkMonitor` class with `is_online()` method: TCP connection to smtp.gmail.com:587 with 5-second timeout
    - Implement `start_polling(callback)` to check every 30 seconds and invoke callback on status change
    - Implement `stop_polling()` to cancel background polling
    - _Requirements: 4.1, 4.3_

  - [x] 5.2 Integrate NetworkMonitor with EmailQueueManager for auto-send
    - When network becomes available (polling detects online), trigger queue processing
    - Process pending emails from queue, call EmailSender for each
    - Display summary when all queued emails processed (sent or permanently failed)
    - _Requirements: 4.3, 4.8_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Revise FontManager for native app
  - [x] 7.1 Create `utils/font_manager.py` with bundled + imported font management
    - Implement `FontManager` class with `BUNDLED_FONTS = ["Arial", "Roboto", "Montserrat", "PlayfairDisplay", "GreatVibes"]`
    - Implement `get_available_fonts()` returning `List[FontInfo]` (bundled + imported)
    - Implement `resolve_font_path(font_name)` to get absolute path for any font
    - Store imported fonts in app's local data directory (via PlatformStorage)
    - _Requirements: 5.1, 5.3, 5.4_

  - [x] 7.2 Implement font import with validation and limits
    - Implement `import_font(file_path, file_bytes)`:
      - Validate .ttf extension
      - Validate file size <= 10 MB
      - Validate TTF structure (parse font, check for glyph table)
    - Enforce maximum of 20 imported fonts
    - Implement `remove_font(font_name)` — only for imported fonts, not bundled
    - _Requirements: 5.2, 5.5, 5.6, 5.7, 5.8_

  - [ ]* 7.3 Write property tests for font import validation (Property 10)
    - **Property 10: Font import validation**
    - Generate random bytes and valid TTF bytes using hypothesis
    - Verify accept/reject matches rules: .ttf extension, <=10MB, valid TrueType with glyph table
    - **Validates: Requirements 5.2, 5.5**

- [x] 8. Implement AppStateManager module
  - [x] 8.1 Create `utils/app_state_manager.py` with SharedPreferences persistence
    - Implement `AppStateManager` using Flet's client storage (SharedPreferences)
    - Define persisted keys: template_path, template_format, attendee_path, font_family, font_size, font_color, vertical_position, email_subject, email_body
    - Implement `save(key, value)`, `load_all()`, `clear(key)`, `clear_all()` methods
    - Save within 2 seconds of any setting change
    - _Requirements: 12.1, 12.9_

  - [x] 8.2 Implement session restore logic on app launch
    - On launch, load all persisted settings
    - Verify persisted file paths still exist; if not, notify user and clear that path
    - If persisted state is missing/unreadable, start with defaults silently
    - _Requirements: 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_

  - [ ]* 8.3 Write property tests for settings persistence round-trip (Property 14)
    - **Property 14: Settings persistence round-trip**
    - Generate random valid settings (font family from known list, font size 10-120, hex color, position 0-100, arbitrary subject/body strings)
    - Persist all, load back, verify equality
    - **Validates: Requirements 12.2, 12.3, 12.4, 12.5**

- [x] 9. Build Flet UI layer
  - [x] 9.1 Create main app structure with step-based navigation
    - Refactor `main.py` as the Flet app entry point
    - Implement step-based navigation flow: Upload Template -> Upload Attendees -> Customize -> Generate -> Review -> Send Email
    - Wire navigation controller to core logic modules
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 9.2 Implement template upload and preview control
    - File picker filtered to PNG, JPG, PDF (max 10 MB on iOS)
    - Display image preview within 2 seconds (render first page for PDF)
    - Display error with asset type + filename + location if file is invalid
    - _Requirements: 11.1, 1.6, 9.5_

  - [x] 9.3 Implement attendee list upload and validation display
    - File picker filtered to CSV, XLSX (max 5 MB on iOS)
    - Parse and display valid attendee count
    - Display row-specific validation errors (row number, field, message)
    - _Requirements: 11.2, 1.7_

  - [x] 9.4 Implement font and customization controls
    - Font selection dropdown showing all available fonts with preview text rendered in each font
    - Font size slider (10-120 points)
    - Font color picker (hex values)
    - Vertical position slider (0-100%)
    - Live preview update within 2 seconds on any setting change
    - _Requirements: 11.3, 11.4, 5.4_

  - [x] 9.5 Implement batch generation with progress indicator
    - Show progress "Generating X of Y" during batch generation
    - Handle text overflow errors per-attendee (report and continue)
    - Store generated certificates for review
    - _Requirements: 11.5, 1.8_

  - [x] 9.6 Implement certificate review gallery with edit capability
    - Previous/next navigation with counter "X / Y"
    - Single-certificate edit: regenerate only the edited certificate without affecting others
    - _Requirements: 11.6, 11.7_

  - [x] 9.7 Implement ZIP download and email composition
    - ZIP archive containing all certificates with sanitized filenames
    - Email composition: subject field, multi-line body, {name} placeholder support
    - Bulk send with progress "Sending X of Y" and final summary (sent/failed counts)
    - _Requirements: 11.8, 11.9, 11.10_

  - [x] 9.8 Implement responsive layout with breakpoint detection
    - Single-column layout when screen width < 600px (portrait/mobile)
    - Multi-column layout when screen width >= 600px (landscape/tablet/desktop)
    - Use Flet `ResponsiveRow` with appropriate breakpoints
    - _Requirements: 11.11, 7.7, 9.6_

  - [x] 9.9 Implement credentials setup screen
    - Gmail address field (max 254 chars) and masked App Password field
    - Field-specific validation error messages
    - Display stored/not-configured status
    - "Clear Credentials" action
    - Pre-fill email on auth failure
    - _Requirements: 3.5, 3.6, 3.8, 3.9_

  - [x] 9.10 Implement email queue status display
    - Show pending count, permanently failed count, last attempt timestamp
    - Show notification with queued count when emails are queued offline
    - Display summary when batch processing completes
    - _Requirements: 4.2, 4.5, 4.8_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Property tests for UI-related correctness properties
  - [ ]* 11.1 Write property tests for responsive layout threshold (Property 11)
    - **Property 11: Responsive layout threshold**
    - Generate random screen widths, verify single-column below 600px and multi-column at/above 600px
    - **Validates: Requirements 7.7, 9.6, 11.11**

  - [ ]* 11.2 Write property tests for single certificate edit isolation (Property 12)
    - **Property 12: Single certificate edit isolation**
    - Generate batch of certificates, edit one at random index, verify all others are byte-identical to pre-edit state
    - **Validates: Requirements 11.7**

  - [ ]* 11.3 Write property tests for ZIP archive completeness (Property 13)
    - **Property 13: ZIP archive completeness**
    - Generate random batches of certificates, create ZIP, verify it contains exactly N files with correct names and matching content
    - **Validates: Requirements 11.8**

- [ ] 12. Property tests for certificate generation
  - [ ]* 12.1 Write property tests for output format preservation (Property 1)
    - **Property 1: Output format matches input format**
    - Generate random format choice (png/jpg/pdf) and random attendee name, verify output format matches input
    - **Validates: Requirements 1.4**

  - [ ]* 12.2 Write property tests for missing asset error completeness (Property 2)
    - **Property 2: Missing asset error message completeness**
    - Generate random asset metadata (type, filename, location), trigger missing path, verify error contains all three fields
    - **Validates: Requirements 1.6**

  - [ ]* 12.3 Write property tests for batch continuation after overflow (Property 3)
    - **Property 3: Batch generation continues after overflow errors**
    - Generate mix of short/long names, verify certificates + errors = total batch size
    - **Validates: Requirements 1.8**

- [x] 13. Configure build pipeline for all platforms
  - [x] 13.1 Configure Windows build with flet build windows
    - Configure `pyproject.toml` with Windows-specific metadata (icon, product name, version, publisher)
    - Ensure all dependencies, fonts (5 bundled), and assets are included
    - Verify build produces .exe under 100MB
    - Verify app launches within 30 seconds without Python installed
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 13.2 Configure Android APK build with flet build apk
    - Configure AndroidManifest for permissions: INTERNET, READ_EXTERNAL_STORAGE (API < 33), POST_NOTIFICATIONS (API 33+)
    - Set minimum SDK 24, target latest stable SDK
    - Configure package name `com.certflow.app`, icon, version from pyproject.toml
    - Use system photo picker / scoped storage for Android 13+
    - Verify APK under 80MB
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.8, 7.9_

  - [x] 13.3 Configure macOS build with flet build macos
    - Configure bundle identifier `com.certflow.app`, icon, version, build number
    - Configure entitlements: outbound network, user-selected file access
    - Set minimum macOS 12 (Monterey)
    - Configure code signing with Developer ID and notarization submission
    - Verify build under 120MB
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [x] 13.4 Configure iOS build with flet build ipa
    - Configure bundle identifier `com.certflow.app`, icon, version, build number
    - Set minimum iOS 16 deployment target
    - Configure minimal permissions (network access only)
    - Configure provisioning profile and signing certificate handling
    - Use iOS document picker with file type filters (PNG/JPG/PDF <=10MB, CSV/XLSX <=5MB)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.7_

- [ ] 14. Integration tests
  - [ ]* 14.1 Write integration tests for end-to-end certificate generation
    - Test full pipeline: load template -> parse CSV -> generate batch -> write files
    - Use real sample template and attendee files from `sample/` directory
    - Verify output files exist with correct format and content
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 14.2 Write integration tests for email queue lifecycle
    - Test: enqueue while offline -> come online -> auto-process -> verify sent
    - Test: enqueue -> fail 3 times -> verify permanently failed
    - Mock SMTP server for CI safety
    - _Requirements: 4.1, 4.2, 4.3, 4.6, 4.7, 4.8_

  - [ ]* 14.3 Write integration tests for credential store with fallback
    - Test secure storage happy path (mocked flet-secure-storage)
    - Test fallback to encrypted credentials.toml when secure storage unavailable
    - Test credential validation -> store -> load -> SMTP auth cycle
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7_

  - [ ]* 14.4 Write integration tests for app state persistence
    - Test save all settings -> restart simulation -> load all -> verify restored
    - Test stale file path detection and notification
    - Test corrupted state recovery (defaults without error)
    - _Requirements: 12.1, 12.6, 12.7, 12.8_

- [x] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (14 properties total)
- Unit tests validate specific examples and edge cases
- The build pipeline tasks (13.x) depend on all core modules and UI being complete
- Python is the implementation language (Flet framework for UI, hypothesis for property tests)
- All `utils/` modules must remain Streamlit-free for native builds
- The Streamlit web frontend (`app.py`) continues to work via an adapter layer

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.4"] },
    { "id": 1, "tasks": ["1.3", "2.1", "3.1", "5.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3", "4.1", "7.1", "8.1"] },
    { "id": 3, "tasks": ["2.4", "2.5", "3.4", "4.2", "5.2", "7.2", "8.2"] },
    { "id": 4, "tasks": ["4.3", "4.4", "4.5", "7.3", "8.3"] },
    { "id": 5, "tasks": ["9.1", "9.2", "9.3", "9.4"] },
    { "id": 6, "tasks": ["9.5", "9.6", "9.7", "9.8", "9.9", "9.10"] },
    { "id": 7, "tasks": ["11.1", "11.2", "11.3", "12.1", "12.2", "12.3"] },
    { "id": 8, "tasks": ["13.1", "13.2", "13.3", "13.4"] },
    { "id": 9, "tasks": ["14.1", "14.2", "14.3", "14.4"] }
  ]
}
```
