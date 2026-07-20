---
inclusion: fileMatch
fileMatchPattern: "app.py"
---

# CertFlow — Streamlit UI Patterns

## Session State Keys

Always use these exact session state keys for consistency:

```python
# Upload state
st.session_state["template_file"]       # Uploaded template UploadedFile object
st.session_state["template_format"]     # "png", "jpg", or "pdf"
st.session_state["csv_file"]            # Uploaded CSV UploadedFile object
st.session_state["attendees"]           # List[AttendeeRecord] from parsed CSV
st.session_state["csv_errors"]          # List[ValidationError] from CSV parsing

# Customization state
st.session_state["font_size"]           # int (10-120, default 40)
st.session_state["font_color"]          # str hex color (default "#000000")
st.session_state["vertical_position"]   # int percentage (0-100, default 50)
st.session_state["email_subject"]       # str
st.session_state["email_body"]          # str

# Operation state
st.session_state["send_in_progress"]    # bool
st.session_state["send_results"]        # SendResult object
st.session_state["generated_certs"]     # List of generated certificate bytes
st.session_state["zip_bytes"]           # bytes of ZIP archive
```

## UI Step Pattern

Each step follows this pattern:

```python
st.header("Step N: Title")

# Check prerequisites
if prerequisite_not_met:
    st.info("Complete Step N-1 first")
    return  # or use st.stop()

# Step content
# ...

# Success indicator
if step_completed:
    st.success("✅ Step N complete")
```

## File Upload Pattern

```python
uploaded_file = st.file_uploader(
    "Upload your certificate template",
    type=["png", "jpg", "jpeg", "pdf"],
    help="Supported formats: PNG, JPG, PDF. Max size: 10MB"
)

if uploaded_file is not None:
    if uploaded_file.size > 10 * 1024 * 1024:
        st.error("File exceeds 10MB limit")
    else:
        st.session_state["template_file"] = uploaded_file
        st.success("Template uploaded successfully")
```

## Progress Bar Pattern

```python
progress_bar = st.progress(0)
status_text = st.empty()

def on_progress(current: int, total: int):
    progress_bar.progress(current / total)
    status_text.text(f"Processing {current} of {total} attendees")

# Pass on_progress as the callback to email_sender
```

## Error Display Pattern

```python
if send_results.errors:
    st.warning(f"⚠️ {len(send_results.errors)} sends failed")
    with st.expander("View error details"):
        for error in send_results.errors:
            st.text(f"❌ {error.attendee_name}: {error.error_message}")
```

## Confirmation Dialog Pattern

```python
# Use a form or button combination
col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Send All Certificates", disabled=not ready_to_send):
        st.session_state["show_confirm"] = True

if st.session_state.get("show_confirm"):
    st.warning(f"You are about to send {len(attendees)} emails. Continue?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, send"):
            # Execute send
            pass
    with col2:
        if st.button("❌ Cancel"):
            st.session_state["show_confirm"] = False
```
