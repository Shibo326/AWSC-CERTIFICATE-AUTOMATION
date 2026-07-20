# Design Document

## Overview

The Streamlit UI Application (`app.py`) is a single-file frontend that orchestrates the entire CertFlow workflow. Built on Streamlit's reactive execution model, the app re-runs top-to-bottom on every interaction, relying on `st.session_state` to persist data across reruns. The design decomposes the UI into discrete step-rendering functions, each gated by prerequisite checks, and delegates all heavy lifting (certificate generation, CSV parsing, email sending) to the `utils/` modules.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         app.py (Streamlit)                           │
│                                                                      │
│  ┌────────────┐  ┌────────────┐  ┌───────────┐  ┌───────┐  ┌─────┐│
│  │  Step 1:   │  │  Step 2:   │  │  Step 3:  │  │Step 4:│  │Step ││
│  │  Upload    │→ │  Upload    │→ │Customize  │→ │Preview│→ │ 5:  ││
│  │  Template  │  │  CSV       │  │ Font/Email│  │       │  │Send ││
│  └─────┬──────┘  └─────┬──────┘  └─────┬─────┘  └───┬───┘  └──┬──┘│
│        │                │               │            │          │   │
│  ┌─────┴────────────────┴───────────────┴────────────┴──────────┴─┐ │
│  │                    st.session_state                             │ │
│  │  (template_file, attendees, font_size, send_results, ...)      │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌───────────┐                                                       │
│  │ Sidebar   │  Gmail status, app info                               │
│  └───────────┘                                                       │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ imports
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐  ┌──────────────┐  ┌────────────────────┐
│  csv_parser   │  │ email_sender │  │certificate_generator│
│  .parse()     │  │ .send_bulk() │  │ .generate()         │
│  .validate()  │  │ .check_creds │  │ .generate_batch()   │
└───────────────┘  └──────────────┘  └────────────────────┘
```

## File Structure

```
certflow/
├── app.py                  # Single Streamlit file: UI layout + orchestration
├── .streamlit/
│   └── secrets.toml        # Gmail credentials (NEVER commit)
└── utils/
    ├── certificate_generator.py
    ├── csv_parser.py
    └── email_sender.py
```

## Session State Schema

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `template_file` | `UploadedFile \| None` | `None` | Raw uploaded template file object |
| `template_format` | `str \| None` | `None` | File format: `"png"`, `"jpg"`, or `"pdf"` |
| `csv_file` | `UploadedFile \| None` | `None` | Raw uploaded CSV file object |
| `attendees` | `List[AttendeeRecord]` | `[]` | Parsed valid attendee records from CSV |
| `csv_errors` | `List[ValidationError]` | `[]` | Validation errors from CSV parsing |
| `font_size` | `int` | `40` | Font size in points (range 10–120) |
| `font_color` | `str` | `"#000000"` | Hex color string for font color |
| `vertical_position` | `int` | `50` | Vertical position as percentage (0–100) |
| `email_subject` | `str` | `""` | Email subject line (supports `{name}`) |
| `email_body` | `str` | `""` | Email body text (supports `{name}`) |
| `send_in_progress` | `bool` | `False` | Whether a send operation is currently running |
| `show_confirm` | `bool` | `False` | Whether the confirmation dialog is visible |
| `send_results` | `SendResult \| None` | `None` | Results from the last batch send operation |
| `generated_certs` | `List[CertificateOutput]` | `[]` | Successfully generated certificate objects |
| `zip_bytes` | `bytes \| None` | `None` | ZIP archive bytes for download |

## Component Design

### main() — Entry Point

```python
def main() -> None:
    """Configure page, initialize session state, render sidebar and all steps."""
    st.set_page_config(page_title="CertFlow", layout="wide")
    init_session_state()
    render_sidebar()
    render_step_upload_template()
    render_step_upload_csv()
    render_step_customize()
    render_step_preview()
    render_step_send()
```

### init_session_state()

```python
def init_session_state() -> None:
    """Set default values for all session state keys if not already present."""
    defaults = {
        "template_file": None,
        "template_format": None,
        "csv_file": None,
        "attendees": [],
        "csv_errors": [],
        "font_size": 40,
        "font_color": "#000000",
        "vertical_position": 50,
        "email_subject": "",
        "email_body": "",
        "send_in_progress": False,
        "show_confirm": False,
        "send_results": None,
        "generated_certs": [],
        "zip_bytes": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
```

### render_sidebar()

```python
def render_sidebar() -> None:
    """Render sidebar with Gmail status and app info."""
    ...
```

**Logic:**
1. Display app title "CertFlow" and version
2. Display brief app description
3. Check Gmail credentials availability via `EmailSender.check_credentials()`
4. Show `st.success("Gmail: Connected")` or `st.warning("Gmail: Not configured")`

### render_step_upload_template()

```python
def render_step_upload_template() -> None:
    """Step 1: Template file upload with size validation and preview."""
    ...
```

**Logic:**
1. Display `st.header("Step 1: Upload Certificate Template")`
2. Render `st.file_uploader` with `type=["png", "jpg", "jpeg", "pdf"]`
3. If file uploaded:
   - Validate size ≤ 10MB (`file.size > 10 * 1024 * 1024` → `st.error`)
   - Determine format from extension, store in `template_format`
   - Store file in `session_state["template_file"]`
   - For PNG/JPG: display `st.image()` thumbnail
   - For PDF: render first page via PyMuPDF `pixmap`, display as image
   - Clear cached preview when template changes
4. Show `st.success("✅ Step 1 complete")` when valid template stored

### render_step_upload_csv()

```python
def render_step_upload_csv() -> None:
    """Step 2: CSV file upload with parsing, validation, and attendee count display."""
    ...
```

**Logic:**
1. Display `st.header("Step 2: Upload Attendee CSV")`
2. Render `st.file_uploader` with `type=["csv"]`
3. If file uploaded:
   - Validate size ≤ 5MB → `st.error` on failure
   - Call `CSVParser.parse(file)` to get `(attendees, errors)`
   - Store both in session state
   - Display attendee count: `st.info(f"Found {len(attendees)} attendees")`
   - If errors present: `st.warning` with error count + expandable details
   - Clear cached preview when CSV changes
4. Show `st.success("✅ Step 2 complete")` when ≥ 1 valid attendee stored

### render_step_customize()

```python
def render_step_customize() -> None:
    """Step 3: Font, position, and email configuration controls."""
    ...
```

**Logic:**
1. Display `st.header("Step 3: Customize Settings")`
2. Split into two sub-sections using `st.subheader`:
   - **Font & Position:**
     - `st.slider("Font Size", 10, 120, default=session_state["font_size"])`
     - `st.color_picker("Font Color", value=session_state["font_color"])`
     - `st.slider("Vertical Position (%)", 0, 100, default=session_state["vertical_position"])`
   - **Email Settings:**
     - `st.text_input("Email Subject", value=session_state["email_subject"])`
     - `st.text_area("Email Body", value=session_state["email_body"])`
     - Display helper text: `"Use {name} as a placeholder for the attendee's name"`
3. Store all values back to session state on change
4. Show validation warnings if subject or body is empty (only when other steps complete)

### render_step_preview()

```python
def render_step_preview() -> None:
    """Step 4: Live certificate preview using first attendee name."""
    ...
```

**Logic:**
1. Display `st.header("Step 4: Preview Certificate")`
2. Gate: if no template or no attendees → `st.info("Complete Steps 1 and 2 to see preview")`
3. Build `FontConfiguration` from current session state values
4. Call `CertificateGenerator(template, font_config).generate(attendees[0].name)`
5. Display result as `st.image()` (for PNG/JPG) or rendered PDF page
6. Wrap in try/except: on failure display `st.error(f"Preview failed: {str(e)}")`
7. Re-renders automatically when customization values change (Streamlit reactivity)

### render_step_send()

```python
def render_step_send() -> None:
    """Step 5: Send operation with readiness check, confirmation, progress, and ZIP download."""
    ...
```

**Logic:**
1. Display `st.header("Step 5: Send Certificates")`
2. Evaluate readiness: template present AND attendees ≥ 1 AND subject non-empty AND body non-empty
3. If not ready: display disabled button + list missing inputs
4. If ready: enable "🚀 Send All Certificates" button
5. On button click: set `show_confirm = True`
6. Confirmation dialog:
   - Display attendee count warning
   - "✅ Yes, send" button → triggers `execute_send()`
   - "❌ Cancel" button → sets `show_confirm = False`
7. During send: disable button, show progress bar + status text
8. After send: display results summary, error log, ZIP download button

### execute_send()

```python
def execute_send() -> None:
    """Execute the batch send operation with progress tracking."""
    ...
```

**Logic:**
1. Set `send_in_progress = True`, `show_confirm = False`
2. Create progress bar and status placeholder
3. Build `FontConfiguration` from session state
4. Instantiate `CertificateGenerator` with template and font config
5. Call `generate_batch(attendee_names)` → get `BatchResult`
6. Instantiate `EmailSender` with credentials from secrets
7. Call `send_bulk(attendees, certificates, email_template, progress_callback)`
8. Progress callback updates: `progress_bar.progress(current/total)` + status text
9. Store results in `send_results`, `generated_certs`
10. Generate ZIP archive from successful certificates → store in `zip_bytes`
11. Set `send_in_progress = False`

### render_error_log()

```python
def render_error_log(send_results: SendResult) -> None:
    """Display failed sends in an expandable error log."""
    ...
```

**Logic:**
1. If `send_results.errors` is empty → return (no display)
2. Show `st.warning(f"⚠️ {len(errors)} sends failed")`
3. Expandable section: iterate errors in order, display attendee name + error message

### generate_zip(certificates: List[CertificateOutput]) -> bytes

```python
def generate_zip(certificates: List[CertificateOutput]) -> bytes:
    """Package all generated certificates into a ZIP archive."""
    ...
```

**Logic:**
1. Create `BytesIO` buffer
2. Open `zipfile.ZipFile` in write mode
3. For each certificate: write to ZIP with filename `{attendee_name}.{format}`
   - Sanitize name: replace spaces with underscores, remove special characters
4. Return buffer bytes

## UI Flow / State Machine

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Page Load / Rerun                             │
└───────────────┬─────────────────────────────────────────────────────┘
                ▼
        ┌───────────────┐
        │ init_session  │
        │ _state()      │
        └───────┬───────┘
                ▼
        ┌───────────────┐
        │render_sidebar │
        └───────┬───────┘
                ▼
        ┌───────────────┐       upload success
        │ Step 1:       │──────────────────────┐
        │ Upload Tmpl   │                      │ store template_file
        └───────┬───────┘                      │ + template_format
                ▼                              ▼
        ┌───────────────┐       upload success
        │ Step 2:       │──────────────────────┐
        │ Upload CSV    │                      │ store attendees
        └───────┬───────┘                      │ + csv_errors
                ▼                              ▼
        ┌───────────────┐
        │ Step 3:       │  (always renders, controls store on change)
        │ Customize     │
        └───────┬───────┘
                ▼
        ┌───────────────┐       template + attendees present?
        │ Step 4:       │──── No ────→ show info message
        │ Preview       │
        │               │──── Yes ───→ render sample certificate
        └───────┬───────┘
                ▼
        ┌───────────────┐       ready_to_send?
        │ Step 5:       │──── No ────→ disabled button + missing list
        │ Send          │
        │               │──── Yes ───→ enabled button
        └───────┬───────┘
                │ click
                ▼
        ┌───────────────┐
        │ Confirmation  │──── Cancel ──→ hide dialog
        │ Dialog        │
        │               │──── Confirm ─→ execute_send()
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ Progress Bar  │  (updates per attendee via callback)
        │ + Status Text │
        └───────┬───────┘
                ▼
        ┌───────────────┐
        │ Results:      │
        │ • Summary     │
        │ • Error Log   │
        │ • ZIP Download│
        └───────────────┘
```

## Integration Points

| UI Action | Module Called | Method | Input | Output |
|-----------|-------------|--------|-------|--------|
| Template upload (PDF preview) | `fitz` (PyMuPDF) | `fitz.open(stream).load_page(0).get_pixmap()` | PDF bytes | PIL Image for display |
| CSV upload | `utils.csv_parser.CSVParser` | `.parse(file)` | `UploadedFile` | `(List[AttendeeRecord], List[ValidationError])` |
| Preview render | `utils.certificate_generator.CertificateGenerator` | `.generate(name)` | attendee name string | `CertificateOutput` |
| Batch generate | `utils.certificate_generator.CertificateGenerator` | `.generate_batch(names)` | `List[str]` | `BatchResult` |
| Gmail status check | `utils.email_sender.EmailSender` | `.check_credentials()` | None | `bool` |
| Bulk send | `utils.email_sender.EmailSender` | `.send_bulk(attendees, certs, template, callback)` | attendees + certs + email config + callback | `SendResult` |
| ZIP generation | `zipfile` (stdlib) | `ZipFile.writestr()` | certificate bytes + filenames | ZIP bytes |

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single file | `app.py` only | Streamlit apps are conventionally single-file; keeps deployment simple on Streamlit Cloud |
| State management | `st.session_state` dict | Streamlit's built-in persistence across reruns; no external state store needed |
| Step rendering | Individual functions per step | Separation of concerns, testable logic, readable top-level flow |
| Prerequisite gating | Early-return with `st.info` | Non-blocking; user sees all steps but gets guided feedback on incomplete ones |
| File size validation | Check `uploaded_file.size` before processing | Fail fast before allocating memory for large files |
| Preview strategy | Render on every rerun when inputs change | Leverages Streamlit's reactive model; no manual refresh needed |
| Confirmation pattern | Two-button dialog via session state flag | Streamlit has no native modal; state-driven show/hide is idiomatic |
| Progress reporting | Callback function passed to `EmailSender` | Decouples UI progress display from backend send logic |
| ZIP generation | In-memory `BytesIO` + `zipfile` | No temp files on disk; works on Streamlit Cloud's ephemeral filesystem |
| Filename sanitization | Replace spaces with underscores, strip special chars | Prevents filesystem issues in ZIP entries and downloads |
| PDF preview | PyMuPDF pixmap → PIL Image | Fast first-page rendering without full PDF viewer dependency |

## Correctness Properties

1. **Session state initialization completeness**: After `init_session_state()` executes, every key in the Session State Schema table must exist in `st.session_state` with its documented default value. No KeyError may occur when accessing any defined key after initialization.

2. **File size gate precedes storage**: For any uploaded file that exceeds the size limit (10MB for templates, 5MB for CSV), the file must NOT be stored in `st.session_state`. The error path must execute before the storage path for all oversized files.

3. **Upload replacement clears dependent state**: When a new template or CSV replaces an existing one in session state, the cached preview (`generated_certs` from previous preview, if any) must be invalidated. Stale preview data must never persist after an input change.

4. **Send readiness is a pure conjunction**: The Send button is enabled if and only if ALL four conditions hold simultaneously: `template_file is not None` AND `len(attendees) >= 1` AND `email_subject != ""` AND `email_body != ""`. No subset of conditions may enable the button.

5. **Progress callback count equals attendee count**: During any batch send of N attendees, the progress callback must be invoked exactly N times with indices 1 through N inclusive, regardless of individual send successes or failures.

6. **ZIP entry count equals successful generations**: The number of entries in the generated ZIP archive must equal `len(generated_certs)` — exactly the count of successfully generated certificates, never including failed ones.

7. **Error log order preservation**: The errors displayed in the Error_Log must appear in the same chronological order as they occurred during the batch send operation, matching the order returned by `SendResult.errors`.

8. **Confirmation prevents accidental send**: The `execute_send()` function must only be callable after the user has clicked the confirm button (`show_confirm` was True and confirm was selected). A single click of the Send button without confirmation must never trigger `execute_send()`.

9. **Concurrent send prevention**: While `send_in_progress` is `True`, no second invocation of `execute_send()` may begin. The Send button must remain disabled for the entire duration of an active send operation.
