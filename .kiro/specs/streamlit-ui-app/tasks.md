# Tasks

## Task 1: Set Up app.py Skeleton with main() and init_session_state()

- [ ] 1.1 Create `app.py` with imports for `streamlit`, `zipfile`, `io`, and utility modules (`utils.certificate_generator`, `utils.csv_parser`, `utils.email_sender`, `utils.font_config`, `utils.models`)
- [ ] 1.2 Implement `main()` function that calls `st.set_page_config(page_title="CertFlow", layout="wide")`, then invokes `init_session_state()`, `render_sidebar()`, and all five step-rendering functions in order
- [ ] 1.3 Implement `init_session_state()` that sets default values for all session state keys: `template_file`, `template_format`, `csv_file`, `attendees`, `csv_errors`, `font_size`, `font_color`, `vertical_position`, `email_subject`, `email_body`, `send_in_progress`, `show_confirm`, `send_results`, `generated_certs`, `zip_bytes`
- [ ] 1.4 Add the `if __name__ == "__main__": main()` entry point guard
- [ ] 1.5 Add stub functions for `render_sidebar()`, `render_step_upload_template()`, `render_step_upload_csv()`, `render_step_customize()`, `render_step_preview()`, `render_step_send()` with placeholder `st.header()` calls

## Task 2: Implement render_sidebar()

- [ ] 2.1 Implement `render_sidebar()` using `st.sidebar` to display the app title "CertFlow" and version information
- [ ] 2.2 Display a brief application description ("Bulk certificate generator and email sender") in the sidebar
- [ ] 2.3 Add Gmail connection status check by calling `EmailSender.check_credentials()` and displaying `st.success("Gmail: Connected")` or `st.warning("Gmail: Not configured — email sending will not work")`
- [ ] 2.4 Handle the case where `.streamlit/secrets.toml` is missing or credentials are absent, displaying the appropriate warning

## Task 3: Implement render_step_upload_template() with File Validation and Preview

- [ ] 3.1 Display `st.header("Step 1: Upload Certificate Template")` and render `st.file_uploader` accepting `["png", "jpg", "jpeg", "pdf"]` types
- [ ] 3.2 Implement file size validation: if uploaded file exceeds 10MB, display `st.error` with size limit message and skip further processing
- [ ] 3.3 On valid upload, determine format from file extension, store the file and format in `st.session_state["template_file"]` and `st.session_state["template_format"]`
- [ ] 3.4 For PNG/JPG templates, display a preview thumbnail using `st.image()`
- [ ] 3.5 For PDF templates, render the first page using PyMuPDF (`fitz.open(stream).load_page(0).get_pixmap()`) and display as an image
- [ ] 3.6 Clear cached preview and `generated_certs` when a new template replaces an existing one
- [ ] 3.7 Display `st.success("✅ Step 1 complete")` when a valid template is stored in session state

## Task 4: Implement render_step_upload_csv() with Parsing Integration

- [ ] 4.1 Display `st.header("Step 2: Upload Attendee CSV")` and render `st.file_uploader` accepting `["csv"]` type
- [ ] 4.2 Implement file size validation: if uploaded CSV exceeds 5MB, display `st.error` with size limit message and skip further processing
- [ ] 4.3 On valid upload, call `CSVParser.parse(file)` to get `(attendees, errors)` and store both in `st.session_state["attendees"]` and `st.session_state["csv_errors"]`
- [ ] 4.4 Display the total attendee count using `st.info(f"Found {count} attendees")`
- [ ] 4.5 If parsing errors exist, display `st.warning` with error count and an expandable `st.expander` section listing each error detail
- [ ] 4.6 Clear cached preview and `generated_certs` when a new CSV replaces an existing one
- [ ] 4.7 Display `st.success("✅ Step 2 complete")` when at least one valid attendee is stored in session state

## Task 5: Implement render_step_customize() with Font and Email Controls

- [ ] 5.1 Display `st.header("Step 3: Customize Settings")` with two sub-sections using `st.subheader`: "Font & Position" and "Email Settings"
- [ ] 5.2 Implement font size slider: `st.slider("Font Size", 10, 120, value=st.session_state["font_size"])` storing the result back to session state
- [ ] 5.3 Implement font color picker: `st.color_picker("Font Color", value=st.session_state["font_color"])` storing the result back to session state
- [ ] 5.4 Implement vertical position slider: `st.slider("Vertical Position (%)", 0, 100, value=st.session_state["vertical_position"])` storing the result back to session state
- [ ] 5.5 Implement email subject text input: `st.text_input("Email Subject", value=st.session_state["email_subject"])` storing the result back to session state
- [ ] 5.6 Implement email body text area: `st.text_area("Email Body", value=st.session_state["email_body"])` with helper text explaining the `{name}` placeholder syntax, storing the result back to session state
- [ ] 5.7 Display validation warnings when email subject or body is empty (only when Steps 1 and 2 are complete)

## Task 6: Implement render_step_preview() with Live Certificate Rendering

- [ ] 6.1 Display `st.header("Step 4: Preview Certificate")` and check prerequisites (template and attendees must be present)
- [ ] 6.2 If prerequisites not met, display `st.info("Complete Steps 1 and 2 to see preview")` and return early
- [ ] 6.3 Build a `FontConfiguration` object from current session state values (font_size, font_color, vertical_position)
- [ ] 6.4 Call `CertificateGenerator(template, font_config).generate(attendees[0].name)` to produce the preview certificate
- [ ] 6.5 Display the preview result as `st.image()` for PNG/JPG output or render PDF first page as image for PDF output
- [ ] 6.6 Wrap rendering logic in try/except block and display `st.error(f"Preview failed: {str(e)}")` on any rendering failure

## Task 7: Implement render_step_send() with Confirmation, Progress, and Results

- [ ] 7.1 Display `st.header("Step 5: Send Certificates")` and evaluate send readiness (template present, attendees ≥ 1, subject non-empty, body non-empty)
- [ ] 7.2 When not ready, display disabled Send button and a message listing which required inputs are still missing
- [ ] 7.3 When ready, display enabled "🚀 Send All Certificates" button; on click, set `st.session_state["show_confirm"] = True`
- [ ] 7.4 Implement confirmation dialog: display attendee count, "✅ Yes, send" button to trigger `execute_send()`, and "❌ Cancel" button to set `show_confirm = False`
- [ ] 7.5 Implement `execute_send()`: set `send_in_progress = True`, create progress bar and status placeholder, build `FontConfiguration`, call `CertificateGenerator.generate_batch()` and `EmailSender.send_bulk()` with a progress callback
- [ ] 7.6 Implement progress callback that updates `st.progress(current/total)` and status text `"Processing X of Y attendees"` after each attendee is processed
- [ ] 7.7 After send completes, store results in `send_results` and `generated_certs`, display summary (successes/failures), and set `send_in_progress = False`
- [ ] 7.8 Implement `render_error_log(send_results)`: if errors exist, display warning count and an expandable section listing each failure with attendee name and error description in order
- [ ] 7.9 Disable the Send button while `send_in_progress` is True to prevent duplicate submissions

## Task 8: Implement generate_zip() for ZIP Download

- [ ] 8.1 Implement `generate_zip(certificates: List[CertificateOutput]) -> bytes` that creates a `BytesIO` buffer and opens a `zipfile.ZipFile` in write mode
- [ ] 8.2 Implement filename sanitization: replace spaces with underscores, remove special characters from attendee names for ZIP entry filenames
- [ ] 8.3 Write each certificate to the ZIP with filename format `{sanitized_name}.{format}` preserving the original file format (PNG, JPG, or PDF)
- [ ] 8.4 After send operation completes, call `generate_zip()` with successful certificates and store result in `st.session_state["zip_bytes"]`
- [ ] 8.5 Display `st.download_button("📥 Download All Certificates (ZIP)", data=zip_bytes, file_name="certificates.zip")` when `zip_bytes` is not None and at least one certificate was generated
- [ ] 8.6 Do not display the download button if no certificates were successfully generated

## Task 9: End-to-End Integration and Polish

- [ ] 9.1 Verify the full workflow runs without errors: upload template → upload CSV → customize → preview → send → download ZIP
- [ ] 9.2 Ensure session state replacement logic works correctly: uploading a new template or CSV clears stale preview and generated data
- [ ] 9.3 Validate that the Send button is correctly gated by all four readiness conditions (template, attendees, subject, body)
- [ ] 9.4 Test error handling paths: oversized files rejected, corrupted template shows error in preview, send failures appear in error log without halting batch
- [ ] 9.5 Verify progress tracking displays correctly during batch operations and updates per attendee
- [ ] 9.6 Confirm responsive layout: test sidebar, step sections, and controls render properly on desktop and narrow viewports
- [ ] 9.7 Add `requirements.txt` entries for Streamlit and any missing dependencies (if not already present)
- [ ] 9.8 Run the app with `streamlit run app.py` and verify no import errors or runtime crashes on startup
