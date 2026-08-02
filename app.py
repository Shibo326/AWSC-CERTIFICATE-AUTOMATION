"""CertFlow — Automated Certificate Generator and Email Sender."""

import base64
import io
import re
import zipfile
from pathlib import Path
from typing import List, Optional

import fitz
import streamlit as st
from PIL import Image

from utils.certificate_generator import CertificateGenerator
from utils.csv_parser import CSVParser
from utils.email_sender import EmailSender
from utils.font_config import FontConfiguration
from utils.font_downloader import (
    POPULAR_FONTS,
    download_font,
    get_available_fonts,
    is_font_downloaded,
    resolve_font_path,
)
from utils.models import (
    AttendeeRecord,
    CertificateOutput,
    EmailTemplate,
    GmailCredentials,
    SendResult,
)


def get_streamlit_credentials() -> Optional[GmailCredentials]:
    """Adapt Streamlit secrets into a GmailCredentials instance.

    Reads credentials from st.secrets["email"]["sender"] and
    st.secrets["email"]["app_password"]. Returns None if the secrets
    section is missing or incomplete, allowing EmailSender to fall back
    to its own credential loading chain.

    Returns:
        GmailCredentials if st.secrets contains valid email config, else None.
    """
    try:
        email_secrets = st.secrets["email"]
        sender = email_secrets.get("sender", "")
        app_password = email_secrets.get("app_password", "")
        if sender and app_password:
            return GmailCredentials(
                sender_email=sender, app_password=app_password
            )
    except (KeyError, FileNotFoundError, AttributeError):
        pass
    return None


def _icon(name: str, size: int = 20) -> str:
    """Return an inline Material Symbols icon HTML span.

    Args:
        name: The Material Symbols icon name (e.g. 'check_circle').
        size: Icon size in pixels.

    Returns:
        HTML string rendering the icon inline.
    """
    return (
        f'<span class="material-symbols-outlined" '
        f'style="font-size:{size}px;vertical-align:middle;margin-right:4px;">'
        f'{name}</span>'
    )


def _get_active_credentials() -> Optional[GmailCredentials]:
    """Get credentials from UI input (session state) or fallback to secrets.

    Priority:
        1. User-entered credentials from the UI (session state)
        2. .streamlit/secrets.toml via get_streamlit_credentials()

    Returns:
        GmailCredentials if available from any source, else None.
    """
    ui_email = st.session_state.get("ui_email", "").strip()
    ui_app_password = st.session_state.get("ui_app_password", "").strip()
    if ui_email and ui_app_password:
        return GmailCredentials(
            sender_email=ui_email, app_password=ui_app_password
        )
    return get_streamlit_credentials()


MAX_TEMPLATE_SIZE_MB = 10
MAX_CSV_SIZE_MB = 5
APP_VERSION = "1.0.0"


# --- Page Config ------------------------------------------------------------

st.set_page_config(
    page_title="CertFlow — Certificate Generator",
    page_icon=":material/school:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Custom CSS + Material Symbols Font -------------------------------------

st.markdown("""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />
<style>
    /* Main container spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Step headers */
    h2 {
        padding-top: 1.5rem !important;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 0.5rem;
    }

    /* Card-like sections */
    .stExpander {
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
    }

    /* Upload areas */
    [data-testid="stFileUploader"] {
        border-radius: 0.5rem;
    }

    /* Text inputs and text areas */
    [data-baseweb="textarea"],
    [data-baseweb="textarea"] > div,
    [data-baseweb="textarea"] textarea {
        background-color: #ffffff !important;
        color: #1e293b !important;
    }
    [data-baseweb="input"],
    [data-baseweb="input"] > div,
    [data-baseweb="input"] input {
        background-color: #ffffff !important;
        color: #1e293b !important;
    }
    textarea::placeholder,
    input::placeholder {
        color: #94a3b8 !important;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        padding: 1rem;
    }

    /* Progress area */
    .stProgress > div > div {
        border-radius: 0.5rem;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        padding-top: 1rem;
        min-width: 280px;
        width: 300px;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    [data-testid="stSidebar"] code {
        font-size: 0.75rem;
        word-break: break-all;
    }
    [data-testid="stSidebar"] .stExpander {
        overflow: hidden;
    }
    [data-testid="stSidebar"] pre {
        white-space: pre-wrap;
        word-break: break-all;
        font-size: 0.75rem;
    }

    /* Responsive columns — stack on small screens */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
        }
        [data-testid="stHorizontalBlock"] > div {
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
    }

    /* Button styling */
    .stButton > button {
        border-radius: 0.375rem;
        font-weight: 500;
    }

    /* Material icon helper */
    .material-symbols-outlined {
        font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
    }

    /* Fix Streamlit image fullscreen to actually fill the screen */
    [data-testid="stImageFullscreen"] {
        display: flex;
        align-items: center;
        justify-content: center;
        background: #ffffff !important;
    }
    [data-testid="stImageFullscreen"] img {
        max-width: 95vw !important;
        max-height: 90vh !important;
        width: auto !important;
        height: auto !important;
        object-fit: contain !important;
    }
    /* Fullscreen modal overlay */
    div[data-baseweb="modal"] {
        background: #ffffff !important;
    }
    div[data-baseweb="modal"] img {
        max-width: 95vw !important;
        max-height: 90vh !important;
        object-fit: contain !important;
    }
    /* Target the fullscreen button container's image */
    button[title="View fullscreen"] ~ div img {
        object-fit: contain !important;
    }
</style>
""", unsafe_allow_html=True)


# --- Session State Defaults -------------------------------------------------

def _init_session_state() -> None:
    """Initialize all session state keys with defaults."""
    defaults = {
        "template_file": None,
        "template_format": None,
        "csv_file": None,
        "attendees": [],
        "csv_errors": [],
        "font_size": 40,
        "font_color": "#000000",
        "vertical_position": 50,
        "email_subject": "Your Certificate — {name}",
        "email_body": (
            "Dear {name},\n\n"
            "Please find your certificate attached.\n\n"
            "Congratulations!\n"
            "Best regards"
        ),
        "send_in_progress": False,
        "send_results": None,
        "generated_certs": [],
        "zip_bytes": None,
        "show_confirm": False,
        "generation_done": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_session_state()


# --- Helper: Send Emails ----------------------------------------------------

def _do_send_emails() -> None:
    """Execute the bulk email send with progress tracking."""
    attendees = st.session_state["attendees"]
    generated = st.session_state["generated_certs"]
    template_format = st.session_state["template_format"]

    template = EmailTemplate(
        subject=st.session_state["email_subject"],
        body=st.session_state["email_body"],
    )

    cert_bytes_list: List[bytes] = []
    for cert in generated:
        if isinstance(cert.certificate, Image.Image):
            buf = io.BytesIO()
            fmt = "PNG" if cert.format == "png" else "JPEG"
            cert.certificate.save(buf, format=fmt)
            cert_bytes_list.append(buf.getvalue())
        else:
            cert_bytes_list.append(cert.certificate)

    progress_bar = st.progress(0)
    status_text = st.empty()

    def on_progress(current: int, total: int) -> None:
        progress_bar.progress(current / total)
        status_text.text(f"Sending {current} of {total}...")

    sender = EmailSender(credentials=_get_active_credentials())
    try:
        result = sender.send_bulk(
            recipients=attendees[:len(generated)],
            certificate_data=cert_bytes_list,
            certificate_format=template_format,
            template=template,
            progress_callback=on_progress,
        )
        st.session_state["send_results"] = result
        progress_bar.empty()
        status_text.empty()

        if result.failure_count == 0:
            st.success(
                f"All {result.success_count} emails sent successfully!"
            )
        else:
            st.warning(
                f"Sent {result.success_count}, "
                f"failed {result.failure_count}."
            )
        st.rerun()

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Email sending failed: {e}")


# --- Sidebar ----------------------------------------------------------------

def _render_sidebar() -> None:
    """Render the sidebar with app info and status."""
    with st.sidebar:
        # Logo in sidebar
        _logo_path = Path("image/NEW_AWSLC_LOGO-removebg-preview.png")
        if _logo_path.exists():
            st.image(str(_logo_path), width=120)
        st.markdown("**CertFlow**")
        st.caption("Property of AWSSB Global City")
        st.markdown("---")

        st.markdown("### Status")

        template_ok = st.session_state["template_file"] is not None
        csv_ok = len(st.session_state["attendees"]) > 0
        certs_ok = len(st.session_state["generated_certs"]) > 0

        check = _icon("check_circle")
        uncheck = _icon("radio_button_unchecked")
        st.markdown(
            f"{check if template_ok else uncheck} Template uploaded",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"{check if csv_ok else uncheck} Attendees loaded",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"{check if certs_ok else uncheck} Certificates generated",
            unsafe_allow_html=True,
        )

        if csv_ok:
            st.markdown("---")
            st.metric("Attendees", len(st.session_state["attendees"]))

        if certs_ok:
            st.metric("Certificates", len(st.session_state["generated_certs"]))

        # Email credentials status
        st.markdown("---")
        st.markdown("### Email")
        has_creds = (
            _get_active_credentials() is not None
            or EmailSender.check_credentials()
        )
        if has_creds:
            st.success("Gmail credentials ready")
        else:
            st.warning("No Gmail credentials")
            with st.expander("How to configure"):
                st.markdown(
                    "Enter your Gmail and App Password "
                    "in **Step 5**, or:\n\n"
                    "Add to `.streamlit/secrets.toml`:\n"
                    "```\n"
                    "[email]\n"
                    "sender = \"...\"\n"
                    "app_password = \"...\"\n"
                    "```"
                )

        st.markdown("---")
        st.markdown("### Font Manager")
        _render_font_manager()


def _render_font_manager() -> None:
    """Render the font download section in the sidebar."""
    available = get_available_fonts()
    st.caption(f"{len(available)} fonts available")

    with st.expander("Download fonts"):
        search = st.text_input(
            "Search Google Fonts", placeholder="e.g. Montserrat"
        )
        query = search.strip().lower()

        if query:
            matches = [f for f in POPULAR_FONTS if query in f.lower()]
        else:
            matches = POPULAR_FONTS[:15]

        for font_name in matches:
            col1, col2 = st.columns([3, 1])
            with col1:
                downloaded = is_font_downloaded(font_name)
                icon_name = "check_circle" if downloaded else "download"
                st.markdown(
                    f"{_icon(icon_name, 16)} {font_name}",
                    unsafe_allow_html=True,
                )
            with col2:
                if not is_font_downloaded(font_name):
                    if st.button("Get", key=f"dl_{font_name}", type="secondary"):
                        with st.spinner(f"Downloading {font_name}..."):
                            success, msg = download_font(font_name)
                        if success:
                            st.success("Done!")
                            st.rerun()
                        else:
                            st.error(msg)


_render_sidebar()


# --- Main Content -----------------------------------------------------------

logo_path = Path("image/NEW_AWSLC_LOGO-removebg-preview.png")
if logo_path.exists():
    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:16px;margin-bottom:8px;">'
        f'<img src="data:image/png;base64,{logo_b64}" height="80" style="border-radius:8px;">'
        f'<div>'
        f'<h1 style="margin:0;font-size:2.2rem;">CertFlow</h1>'
        f'<p style="margin:0;color:#64748b;font-size:0.9rem;">Automated Certificate Generator</p>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown("# CertFlow", unsafe_allow_html=True)
st.markdown(
    "Generate personalized certificates in bulk and send them via email — "
    "all from one place."
)

with st.expander("First time here? Here's how it works", expanded=False):
    st.markdown(
        "CertFlow takes your certificate design and a list of attendees, "
        "then automatically puts each person's name on their certificate "
        "and emails it to them. Here's the workflow:\n\n"
        "1. **Upload a template** — your blank certificate image or PDF\n"
        "2. **Upload attendees** — a spreadsheet with names and emails\n"
        "3. **Customize** — pick the font, size, color, and position\n"
        "4. **Generate** — CertFlow creates one certificate per person\n"
        "5. **Send** — emails go out with certificates attached\n\n"
        "You can also just download the certificates as a ZIP "
        "without sending emails."
    )

st.divider()


# --- Step 1: Upload Template ------------------------------------------------

st.markdown(f'## {_icon("upload_file")} Step 1: Upload Template', unsafe_allow_html=True)
st.caption(
    "Upload your certificate template image. "
    "This will be the background for every certificate."
)

uploaded_template = st.file_uploader(
    "Choose your template file (PNG, JPG, or PDF)",
    type=["png", "jpg", "jpeg", "pdf"],
    help=(
        "Supported formats: PNG, JPG, PDF. Max size: 10MB. "
        "Tip: design your template in Canva or PowerPoint, "
        "then export as PNG or PDF."
    ),
    key="template_uploader",
)
st.caption("Supported: PNG, JPG, PDF (max 10MB)")

if uploaded_template is not None:
    if uploaded_template.size > MAX_TEMPLATE_SIZE_MB * 1024 * 1024:
        st.error(
            f"File exceeds {MAX_TEMPLATE_SIZE_MB}MB limit. "
            "Please use a smaller template."
        )
    else:
        ext = uploaded_template.name.rsplit(".", 1)[-1].lower()
        if ext == "jpeg":
            ext = "jpg"

        st.session_state["template_file"] = uploaded_template
        st.session_state["template_format"] = ext

        st.success(
            f"Template uploaded: **{uploaded_template.name}** ({ext.upper()})"
        )

        if ext in ("png", "jpg"):
            preview_image = Image.open(uploaded_template)
            st.image(
                preview_image,
                caption="Template Preview",
                width=500,
            )
            uploaded_template.seek(0)
        elif ext == "pdf":
            uploaded_template.seek(0)
            pdf_bytes = uploaded_template.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=100)
            preview_img = Image.frombytes(
                "RGB", [pix.width, pix.height], pix.samples
            )
            st.image(
                preview_img,
                caption="Template Preview (Page 1)",
                width=500,
            )
            doc.close()
            uploaded_template.seek(0)

st.divider()


# --- Step 2: Upload Attendees -----------------------------------------------

st.markdown(f'## {_icon("group")} Step 2: Upload Attendee List', unsafe_allow_html=True)
st.caption(
    "Upload a spreadsheet with your attendees' names and email addresses. "
    "CertFlow will create one certificate per person."
)

with st.expander("Required file format", expanded=False):
    st.markdown(
        "Your CSV or Excel file **must** have a header row with these exact column names:\n\n"
        "| name | email |\n"
        "|------|-------|\n"
        "| Juan Dela Cruz | juan@gmail.com |\n"
        "| Maria Santos | maria@gmail.com |\n\n"
        "**Rules:**\n"
        "- Column headers must be exactly `name` and `email` (case doesn't matter)\n"
        "- Each row = one attendee who will receive a certificate\n"
        "- Duplicates are automatically removed (first occurrence is kept)\n"
        "- Accepted formats: `.csv` or `.xlsx`\n"
        "- Max file size: 5MB\n\n"
        "**Tip:** Create your list in any spreadsheet app (Excel, Google Sheets, "
        "LibreOffice, WPS Office) — just use `name` and `email` as column headers. "
        "Save as .csv or .xlsx to upload."
    )

if st.session_state["template_file"] is None:
    st.info("Upload a certificate template first (Step 1).")
else:
    uploaded_csv = st.file_uploader(
        "Choose your attendee file (CSV or Excel)",
        type=["csv", "xlsx"],
        help=(
            "Your file needs at least two columns: 'name' and 'email'. "
            "You can create this in Excel, Google Sheets, or LibreOffice — "
            "just save/export as CSV or XLSX. Max size: 5MB."
        ),
        key="csv_uploader",
    )
    st.caption("Supported: CSV, XLSX from Excel/Google Sheets/LibreOffice (max 5MB)")

    if uploaded_csv is not None:
        if uploaded_csv.size > MAX_CSV_SIZE_MB * 1024 * 1024:
            st.error(f"File exceeds {MAX_CSV_SIZE_MB}MB limit.")
        else:
            parser = CSVParser()
            try:
                uploaded_csv.seek(0)
                if uploaded_csv.name.endswith(".xlsx"):
                    result = parser.parse_xlsx(uploaded_csv.read())
                else:
                    content = uploaded_csv.read().decode("utf-8")
                    result = parser.parse(content)

                st.session_state["attendees"] = result.records
                st.session_state["csv_errors"] = result.errors

                if result.records:
                    st.success(
                        f"Loaded **{len(result.records)}** attendees "
                        f"from **{uploaded_csv.name}** successfully."
                    )

                    with st.expander(
                        f"Attendees ({len(result.records)})",
                        expanded=False,
                    ):
                        for i, rec in enumerate(result.records[:50], 1):
                            st.text(f"{i}. {rec.name} — {rec.email}")
                        if len(result.records) > 50:
                            st.caption(
                                f"...and {len(result.records) - 50} more"
                            )

                if result.errors:
                    st.warning(
                        f"{len(result.errors)} validation issue(s) found"
                    )
                    with st.expander("View validation errors"):
                        for err in result.errors:
                            st.text(
                                f"Row {err.row_number} [{err.field}]: "
                                f"{err.message}"
                            )

            except ValueError as e:
                st.error(f"{e}")

st.divider()


# --- Step 3: Customize -----------------------------------------------------

st.markdown(f'## {_icon("palette")} Step 3: Customize Certificate', unsafe_allow_html=True)
st.caption(
    "Fine-tune how each attendee's name appears on the certificate. "
    "Changes are reflected in the live preview below."
)

if not st.session_state["attendees"]:
    st.info("Upload an attendee list first (Step 2).")
else:
    col1, col2, col3 = st.columns(3)

    with col1:
        available_fonts = get_available_fonts()
        selected_font = st.selectbox(
            "Font",
            options=available_fonts,
            help="Download more fonts from the sidebar Font Manager.",
        )

    with col2:
        font_size = st.slider(
            "Font Size",
            min_value=10,
            max_value=120,
            value=st.session_state["font_size"],
            step=2,
            key="font_size_slider",
        )
        st.session_state["font_size"] = font_size

    with col3:
        font_color = st.color_picker(
            "Font Color",
            value=st.session_state["font_color"],
        )
        st.session_state["font_color"] = font_color

    vertical_position = st.slider(
        "Name Vertical Position (%)",
        min_value=0,
        max_value=100,
        value=st.session_state["vertical_position"],
        help="0% = top, 50% = center, 100% = bottom",
        key="vertical_position_slider",
    )
    st.session_state["vertical_position"] = vertical_position

    # Live preview
    st.subheader("Preview")
    preview_name = (
        st.session_state["attendees"][0].name
        if st.session_state["attendees"]
        else "John Doe"
    )

    template_file = st.session_state["template_file"]
    template_format = st.session_state["template_format"]

    if template_file:
        try:
            template_file.seek(0)
            template_bytes = template_file.read()
            template_file.seek(0)

            font_path = resolve_font_path(selected_font)
            font_cfg = FontConfiguration(
                font_path=font_path or "assets/fonts/Arial.ttf",
                font_size=font_size,
                font_color=FontConfiguration.parse_color(font_color),
            )

            generator = CertificateGenerator(
                template_bytes=template_bytes,
                template_format=template_format,
                font_config=font_cfg,
            )

            preview_cert = generator.generate(
                preview_name,
                vertical_position=vertical_position,
                vertical_as_percentage=True,
            )

            if isinstance(preview_cert.certificate, Image.Image):
                # Show full-res image with use_container_width for responsive sizing
                # Streamlit's built-in fullscreen button will show it at full resolution
                with st.container(border=True):
                    st.image(
                        preview_cert.certificate,
                        caption=f"Preview: {preview_name}",
                        use_container_width=True,
                    )
            else:
                doc = fitz.open(
                    stream=preview_cert.certificate, filetype="pdf"
                )
                page = doc[0]
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes(
                    "RGB", [pix.width, pix.height], pix.samples
                )
                with st.container(border=True):
                    st.image(
                        img,
                        caption=f"Preview: {preview_name}",
                        use_container_width=True,
                    )
                doc.close()

            generator.cleanup()

        except Exception as e:
            st.error(f"Preview error: {e}")

st.divider()


# --- Step 4: Generate Certificates ------------------------------------------

st.markdown(f'## {_icon("bolt")} Step 4: Generate Certificates', unsafe_allow_html=True)
st.caption(
    "Once you're happy with the preview above, click the button below "
    "to create all certificates at once. You can download them as a ZIP file."
)

if not st.session_state["attendees"]:
    st.info("Complete Steps 1-3 first.")
else:
    attendees = st.session_state["attendees"]
    st.markdown(f"Ready to generate **{len(attendees)}** certificates.")

    if st.button(
        "Generate All Certificates",
        type="primary",
        icon=":material/rocket_launch:",
    ):
        template_file = st.session_state["template_file"]
        template_format = st.session_state["template_format"]
        template_file.seek(0)
        template_bytes = template_file.read()
        template_file.seek(0)

        font_path = resolve_font_path(
            selected_font if "selected_font" in dir() else "Arial (Default)"
        )
        font_cfg = FontConfiguration(
            font_path=font_path or "assets/fonts/Arial.ttf",
            font_size=st.session_state["font_size"],
            font_color=FontConfiguration.parse_color(
                st.session_state["font_color"]
            ),
        )

        generator = CertificateGenerator(
            template_bytes=template_bytes,
            template_format=template_format,
            font_config=font_cfg,
        )

        progress_bar = st.progress(0)
        status_text = st.empty()
        generated: List[CertificateOutput] = []
        errors = []

        for i, attendee in enumerate(attendees):
            try:
                cert = generator.generate(
                    attendee.name,
                    vertical_position=st.session_state["vertical_position"],
                    vertical_as_percentage=True,
                )
                generated.append(cert)
            except Exception as e:
                errors.append((attendee.name, str(e)))

            progress_bar.progress((i + 1) / len(attendees))
            status_text.text(f"Generating {i + 1} of {len(attendees)}...")

        generator.cleanup()
        status_text.empty()
        progress_bar.empty()

        st.session_state["generated_certs"] = generated
        st.session_state["generation_done"] = True

        # Build ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for cert in generated:
                sanitized = cert.attendee_name.replace(" ", "_")
                filename = f"{sanitized}.{cert.format}"
                if isinstance(cert.certificate, Image.Image):
                    img_buffer = io.BytesIO()
                    fmt = "PNG" if cert.format == "png" else "JPEG"
                    cert.certificate.save(img_buffer, format=fmt)
                    zf.writestr(filename, img_buffer.getvalue())
                else:
                    zf.writestr(filename, cert.certificate)

        st.session_state["zip_bytes"] = zip_buffer.getvalue()

        st.success(
            f"Successfully generated **{len(generated)}** certificates. "
            "Download them below or proceed to send via email."
        )
        if errors:
            st.warning(f"{len(errors)} failed:")
            with st.expander("View errors"):
                for name, msg in errors:
                    st.text(f"{name}: {msg}")

    # Download ZIP
    if st.session_state["zip_bytes"]:
        st.download_button(
            label="Download All (ZIP)",
            data=st.session_state["zip_bytes"],
            file_name="certificates.zip",
            mime="application/zip",
            type="secondary",
            icon=":material/download:",
        )

    # View generated certificates gallery
    if st.session_state["generated_certs"]:
        @st.dialog("View All Certificates", width="large")
        def _show_certificates_dialog():
            generated_certs = st.session_state["generated_certs"]
            total_certs = len(generated_certs)
            st.caption(
                f"Showing all **{total_certs}** certificates. "
                "Click a certificate to view it fullscreen."
            )

            cols_per_row = 3
            for row_start in range(0, total_certs, cols_per_row):
                cols = st.columns(cols_per_row)
                for col_idx, cert_idx in enumerate(
                    range(row_start, min(row_start + cols_per_row, total_certs))
                ):
                    cert_obj = generated_certs[cert_idx]
                    with cols[col_idx]:
                        if isinstance(cert_obj.certificate, Image.Image):
                            st.image(
                                cert_obj.certificate,
                                caption=(
                                    f"{cert_idx + 1}. "
                                    f"{cert_obj.attendee_name}"
                                ),
                                use_container_width=True,
                            )
                        else:
                            cert_doc = fitz.open(
                                stream=cert_obj.certificate, filetype="pdf"
                            )
                            cert_page = cert_doc[0]
                            cert_pix = cert_page.get_pixmap(dpi=100)
                            cert_img = Image.frombytes(
                                "RGB",
                                [cert_pix.width, cert_pix.height],
                                cert_pix.samples,
                            )
                            st.image(
                                cert_img,
                                caption=(
                                    f"{cert_idx + 1}. "
                                    f"{cert_obj.attendee_name}"
                                ),
                                use_container_width=True,
                            )
                            cert_doc.close()
                        if st.button(
                            "Zoom",
                            key=f"zoom_{cert_idx}",
                            icon=":material/zoom_in:",
                            use_container_width=True,
                        ):
                            st.session_state["zoom_cert_idx"] = cert_idx
                            st.rerun()

        @st.dialog("Certificate Fullscreen", width="large")
        def _show_zoom_dialog():
            cert_idx = st.session_state.get("zoom_cert_idx", 0)
            generated_certs = st.session_state["generated_certs"]
            total_certs = len(generated_certs)
            cert_obj = generated_certs[cert_idx]

            st.markdown(
                f"**{cert_idx + 1} of {total_certs}** — "
                f"{cert_obj.attendee_name}"
            )

            if isinstance(cert_obj.certificate, Image.Image):
                st.image(
                    cert_obj.certificate,
                    caption=cert_obj.attendee_name,
                    use_container_width=True,
                )
            else:
                cert_doc = fitz.open(
                    stream=cert_obj.certificate, filetype="pdf"
                )
                cert_page = cert_doc[0]
                cert_pix = cert_page.get_pixmap(dpi=150)
                cert_img = Image.frombytes(
                    "RGB",
                    [cert_pix.width, cert_pix.height],
                    cert_pix.samples,
                )
                st.image(
                    cert_img,
                    caption=cert_obj.attendee_name,
                    use_container_width=True,
                )
                cert_doc.close()

            # Navigation buttons
            nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])
            with nav_col1:
                if cert_idx > 0:
                    if st.button(
                        "Previous",
                        icon=":material/arrow_back:",
                        use_container_width=True,
                    ):
                        st.session_state["zoom_cert_idx"] = cert_idx - 1
                        st.rerun()
            with nav_col2:
                if st.button(
                    "Back to grid",
                    icon=":material/grid_view:",
                    use_container_width=True,
                ):
                    del st.session_state["zoom_cert_idx"]
                    st.rerun()
            with nav_col3:
                if cert_idx < total_certs - 1:
                    if st.button(
                        "Next",
                        icon=":material/arrow_forward:",
                        use_container_width=True,
                    ):
                        st.session_state["zoom_cert_idx"] = cert_idx + 1
                        st.rerun()

        # Decide which dialog to show
        if "zoom_cert_idx" in st.session_state:
            _show_zoom_dialog()
        elif st.button(
            "View All Certificates",
            key="view_certs_btn",
            icon=":material/visibility:",
        ):
            _show_certificates_dialog()

st.divider()


# --- Step 5: Email Certificates ---------------------------------------------

st.markdown(f'## {_icon("send")} Step 5: Review & Send', unsafe_allow_html=True)
st.caption(
    "Download all certificates as a ZIP, or send each attendee their personalized "
    "certificate directly via email. Use {name} to insert each person's name in the message."
)

if not st.session_state["generated_certs"]:
    st.info("Generate certificates first (Step 4).")
else:
    # --- Credentials input (one-time login) ---
    st.subheader("Gmail Login")
    st.caption(
        "Enter your Gmail address and App Password below. "
        "Your credentials are stored in memory only — they are never saved to disk."
    )

    cred_col1, cred_col2 = st.columns(2)
    with cred_col1:
        input_email = st.text_input(
            "Gmail Address",
            value=st.session_state.get("ui_email", ""),
            placeholder="your-email@gmail.com",
            key="input_email_field",
        )
    with cred_col2:
        input_app_password = st.text_input(
            "App Password",
            value=st.session_state.get("ui_app_password", ""),
            type="password",
            placeholder="xxxx xxxx xxxx xxxx",
            key="input_app_password_field",
            help=(
                "Generate an App Password from your Google Account: "
                "Security > 2-Step Verification > App passwords"
            ),
        )

    # Store in session state
    if input_email:
        st.session_state["ui_email"] = input_email
    if input_app_password:
        st.session_state["ui_app_password"] = input_app_password

    # Determine if credentials are available
    ui_email = st.session_state.get("ui_email", "").strip()
    ui_app_password = st.session_state.get("ui_app_password", "").strip()
    has_ui_creds = bool(ui_email and ui_app_password)

    # Also check other credential sources as fallback
    has_file_creds = (
        get_streamlit_credentials() is not None
        or EmailSender.check_credentials()
    )

    has_creds = has_ui_creds or has_file_creds

    if not has_creds:
        st.warning(
            "Enter your Gmail and App Password above to enable sending."
        )
        with st.expander("How to get an App Password"):
            st.markdown(
                "1. Go to [Google Account Security]"
                "(https://myaccount.google.com/security)\n"
                "2. Enable **2-Step Verification** if not already on\n"
                "3. Go to **App passwords** (search for it in your account)\n"
                "4. Create a new app password — select 'Mail'\n"
                "5. Copy the 16-character password and paste it above"
            )
    else:
        if has_ui_creds:
            st.success("Gmail credentials ready.")

        st.subheader("Email Template")
        col1, col2 = st.columns(2)

        with col1:
            email_subject = st.text_input(
                "Subject",
                value=st.session_state["email_subject"],
                help="Use {name} as placeholder for attendee name.",
            )
            st.session_state["email_subject"] = email_subject

        with col2:
            st.markdown("**Available placeholders:** `{name}`")

        email_body = st.text_area(
            "Body",
            value=st.session_state["email_body"],
            height=150,
            help="Use {name} as placeholder for attendee name.",
        )
        st.session_state["email_body"] = email_body

        # Preview
        with st.expander("Email Preview"):
            preview_attendee = st.session_state["attendees"][0]
            tmpl = EmailTemplate(subject=email_subject, body=email_body)
            st.markdown(f"**To:** {preview_attendee.email}")
            st.markdown(
                f"**Subject:** {tmpl.render_subject(preview_attendee.name)}"
            )
            st.markdown("**Body:**")
            st.text(tmpl.render_body(preview_attendee.name))
            st.caption(
                f"Attachment: "
                f"{preview_attendee.name.replace(' ', '_')}"
                f".{st.session_state['template_format']}"
            )

        st.markdown("")

        # Send button with confirmation
        num_certs = len(st.session_state["generated_certs"])

        if not st.session_state.get("show_confirm"):
            if st.button(
                f"Send {num_certs} Emails",
                type="primary",
                icon=":material/send:",
            ):
                st.session_state["show_confirm"] = True
                st.rerun()
        else:
            st.warning(
                f"You are about to send **{num_certs}** emails. "
                f"This cannot be undone."
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    "Yes, send all",
                    type="primary",
                    icon=":material/check:",
                ):
                    st.session_state["show_confirm"] = False
                    _do_send_emails()
            with col2:
                if st.button("Cancel", icon=":material/close:"):
                    st.session_state["show_confirm"] = False
                    st.rerun()

        # Show results
        if st.session_state["send_results"] is not None:
            result: SendResult = st.session_state["send_results"]
            st.markdown("### Results")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Sent", result.success_count)
            with col2:
                st.metric("Failed", result.failure_count)

            if result.failures:
                with st.expander("View failures"):
                    for failure in result.failures:
                        st.text(
                            f"{failure.attendee_name} "
                            f"({failure.email}): "
                            f"{failure.error_message}"
                        )


# --- Footer -----------------------------------------------------------------

st.divider()
st.caption("CertFlow v1.0.0 \u2022 Property of AWSSB Global City \u2022 Built with Streamlit")
