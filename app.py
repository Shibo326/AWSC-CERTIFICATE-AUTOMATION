"""AWSC GLOBAL PROJECT — Automated Certificate Generator & Email Sender.

Modern Streamlit UI with Lucide SVG icons and custom dark theme.
"""

import io
import re
import zipfile
from typing import List

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
    SendResult,
)

MAX_TEMPLATE_SIZE_MB = 10
MAX_CSV_SIZE_MB = 5
APP_VERSION = "1.0.0"


# --- Lucide SVG Icons (ISC License, lucide.dev) ---
ICONS = {
    "award": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>',
    "upload": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>',
    "users": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "palette": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg>',
    "eye": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>',
    "send": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/></svg>',
    "mail": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>',
    "download": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>',
    "check": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>',
    "warn": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>',
    "x-circle": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>',
    "globe": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>',
    "zap": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>',
    "image": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>',
}


def svg(name: str) -> str:
    """Return inline SVG by name."""
    return ICONS.get(name, "")


def get_theme() -> str:
    """Return current theme from session state. Defaults to 'dark'."""
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "dark"
    return st.session_state["theme_mode"]



def inject_css() -> None:
    """Inject theme-aware and responsive CSS."""
    theme = get_theme()
    is_dark = theme == "dark"

    if is_dark:
        bg_primary = "#0E1117"
        bg_secondary = "#1A1F2E"
        bg_card = "#141b2d"
        text_primary = "#FAFAFA"
        text_secondary = "#94a3b8"
        text_muted = "#64748b"
        border_color = "rgba(255,255,255,0.08)"
        hero_bg = "linear-gradient(135deg, #1e3a5f 0%, #0f2027 50%, #203a43 100%)"
        hero_border = "rgba(255,255,255,0.05)"
        hero_shadow = "rgba(0,0,0,0.4)"
        hero_title = "#f0f4f8"
        hero_subtitle = "rgba(240,244,248,0.7)"
        step_num_bg = "linear-gradient(135deg, #1e3a5f, #2d5a7b)"
        step_num_color = "#a8d0e6"
        step_lbl_color = "#e2e8f0"
        uploader_border = "rgba(45,90,123,0.4)"
        uploader_hover = "rgba(45,90,123,0.8)"
        dl_btn_bg = "linear-gradient(135deg, #1e3a5f, #2d5a7b)"
        dl_btn_color = "#e2e8f0"
        sidebar_title_color = "#a8d0e6"
        sidebar_bg = "#161B22"
        font_preview_bg = "#1e293b"
        font_preview_border = "rgba(255,255,255,0.1)"
        input_bg = "#1A1F2E"
        btn_bg = "#1e293b"
        btn_border = "rgba(255,255,255,0.1)"
        btn_text = "#e2e8f0"
        check_color = "#10B981"
    else:
        bg_primary = "#FFFFFF"
        bg_secondary = "#F8FAFC"
        bg_card = "#F1F5F9"
        text_primary = "#1E293B"
        text_secondary = "#475569"
        text_muted = "#64748b"
        border_color = "rgba(0,0,0,0.1)"
        hero_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 50%, #6B73FF 100%)"
        hero_border = "rgba(255,255,255,0.2)"
        hero_shadow = "rgba(102,126,234,0.15)"
        hero_title = "#FFFFFF"
        hero_subtitle = "rgba(255,255,255,0.85)"
        step_num_bg = "linear-gradient(135deg, #667eea, #764ba2)"
        step_num_color = "#FFFFFF"
        step_lbl_color = "#1E293B"
        uploader_border = "rgba(102,126,234,0.3)"
        uploader_hover = "rgba(102,126,234,0.6)"
        dl_btn_bg = "linear-gradient(135deg, #667eea, #764ba2)"
        dl_btn_color = "#FFFFFF"
        sidebar_title_color = "#4F46E5"
        sidebar_bg = "#F1F5F9"
        font_preview_bg = "#F8FAFC"
        font_preview_border = "rgba(0,0,0,0.08)"
        input_bg = "#FFFFFF"
        btn_bg = "#F8FAFC"
        btn_border = "rgba(0,0,0,0.12)"
        btn_text = "#1E293B"
        check_color = "#059669"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"],
    .main, .main .block-container {{
        background-color: {bg_primary} !important; color: {text_primary} !important;
        font-family: 'Inter', sans-serif !important;
    }}
    #MainMenu, footer {{ visibility: hidden; }}
    .stApp p, .stApp span, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] span,
    [data-testid="stText"] {{ color: {text_primary} !important; }}
    [data-testid="stCaptionContainer"] p, .stApp small {{ color: {text_muted} !important; }}
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"] {{ background-color: {sidebar_bg} !important; }}
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] li,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span {{
        color: {text_primary} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: {text_muted} !important; }}
    section[data-testid="stSidebar"] hr {{ border-color: {border_color} !important; }}
    section[data-testid="stSidebar"] .stButton > button {{
        background-color: {btn_bg} !important; color: {btn_text} !important;
        border: 1px solid {btn_border} !important; border-radius: 8px;
    }}
    section[data-testid="stSidebar"] svg {{ color: {text_primary} !important; }}
    [data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"] {{
        background-color: {input_bg} !important; border-color: {border_color} !important;
    }}
    [data-baseweb="input"] input, [data-baseweb="select"] input,
    [data-baseweb="select"] [data-testid="stMarkdownContainer"] p {{ color: {text_primary} !important; }}
    [data-baseweb="textarea"] textarea {{ background-color: {input_bg} !important; color: {text_primary} !important; }}
    [data-baseweb="popover"], [data-baseweb="menu"], ul[role="listbox"] {{ background-color: {bg_secondary} !important; }}
    ul[role="listbox"] li {{ color: {text_primary} !important; }}
    [data-testid="stSlider"] p, [data-testid="stSlider"] [data-testid="stThumbValue"],
    [data-testid="stSlider"] [data-testid="stTickBarMin"],
    [data-testid="stSlider"] [data-testid="stTickBarMax"] {{ color: {text_primary} !important; }}
    [data-testid="stExpander"] {{ border-color: {border_color} !important; background-color: {bg_secondary} !important; }}
    [data-testid="stExpander"] summary, [data-testid="stExpander"] summary span {{ color: {text_primary} !important; }}
    .stApp .stButton > button {{
        border-radius: 8px; font-weight: 600; background-color: {btn_bg} !important;
        color: {btn_text} !important; border: 1px solid {btn_border} !important;
    }}
    .stApp .stButton > button:hover {{ border-color: {uploader_hover} !important; }}
    .stDownloadButton > button {{
        background: {dl_btn_bg} !important; color: {dl_btn_color} !important;
        border: none !important; border-radius: 8px; font-weight: 600;
    }}
    @media (max-width: 768px) {{
        .hero {{ padding: 1.5rem 1rem !important; margin-bottom: 1.2rem !important; }}
        .hero h1 {{ font-size: 1.4rem !important; }}
        .hero p {{ font-size: 0.85rem !important; }}
        .kpi {{ padding: 0.8rem !important; }}
        .kpi-val {{ font-size: 1.3rem !important; }}
        .step-hdr {{ margin: 1rem 0 0.5rem 0 !important; }}
        .step-lbl {{ font-size: 0.9rem !important; }}
        [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; }}
        [data-testid="stHorizontalBlock"] > div {{ flex: 1 1 100% !important; min-width: 100% !important; }}
        section[data-testid="stSidebar"] {{ width: 100% !important; }}
        .stButton > button, .stDownloadButton > button {{ min-height: 44px; }}
        div[data-testid="stFileUploader"] {{ padding: 0.8rem; }}
    }}
    @media (min-width: 769px) and (max-width: 1024px) {{
        .hero h1 {{ font-size: 1.7rem !important; }}
        .kpi-val {{ font-size: 1.5rem !important; }}
    }}
    .hero {{
        background: {hero_bg}; border-radius: 16px; padding: 2.5rem 2rem;
        margin-bottom: 2rem; text-align: center; border: 1px solid {hero_border};
        box-shadow: 0 20px 60px {hero_shadow};
    }}
    .hero h1 {{ color: {hero_title} !important; font-size: 2rem; font-weight: 700; margin: 0; }}
    .hero p {{ color: {hero_subtitle} !important; font-size: 1rem; margin-top: 0.4rem; }}
    .step-hdr {{ display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 0.8rem 0; }}
    .step-num {{
        background: {step_num_bg}; color: {step_num_color} !important;
        width: 28px; height: 28px; border-radius: 6px;
        display: inline-flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 0.8rem;
    }}
    .step-lbl {{ color: {step_lbl_color} !important; font-size: 1.05rem; font-weight: 600; }}
    .badge {{ display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 500; }}
    .badge-ok {{ background: rgba(16,185,129,0.12); color: {check_color} !important; border: 1px solid rgba(16,185,129,0.3); }}
    .badge-warn {{ background: rgba(245,158,11,0.12); color: #D97706 !important; border: 1px solid rgba(245,158,11,0.3); }}
    .badge-err {{ background: rgba(239,68,68,0.12); color: #DC2626 !important; border: 1px solid rgba(239,68,68,0.3); }}
    .badge-info {{ background: rgba(99,102,241,0.12); color: #6366F1 !important; border: 1px solid rgba(99,102,241,0.3); }}
    .badge svg {{ color: inherit !important; }}
    .kpi {{ background: {bg_card}; border: 1px solid {border_color}; border-radius: 10px; padding: 1.2rem; text-align: center; }}
    .kpi-val {{ font-size: 1.8rem; font-weight: 700; }}
    .kpi-lbl {{ font-size: 0.78rem; color: {text_muted} !important; margin-top: 2px; }}
    div[data-testid="stFileUploader"] {{
        border: 2px dashed {uploader_border}; border-radius: 10px; padding: 0.3rem;
        background-color: {bg_secondary} !important;
    }}
    div[data-testid="stFileUploader"]:hover {{ border-color: {uploader_hover}; }}
    .sidebar-title {{ color: {sidebar_title_color} !important; font-size: 1.3rem; font-weight: 700; text-align: center; }}
    .font-preview-box {{
        background: {font_preview_bg}; border: 1px solid {font_preview_border};
        border-radius: 8px; padding: 16px; margin: 8px 0; text-align: center;
    }}
    .font-preview-box .fp-label {{ color: {text_muted} !important; font-size: 0.7rem; margin-top: 6px; }}
    img {{ max-width: 100%; height: auto; }}
    </style>
    """, unsafe_allow_html=True)



def step_hdr(num: int, label: str, icon_name: str) -> None:
    st.markdown(f'<div class="step-hdr"><span class="step-num">{num}</span><span class="step-lbl">{svg(icon_name)} {label}</span></div>', unsafe_allow_html=True)


def bdg(text: str, variant: str = "info") -> str:
    return f'<span class="badge badge-{variant}">{text}</span>'


def main() -> None:
    st.set_page_config(page_title="AWSC GLOBAL PROJECT", page_icon=None, layout="wide", initial_sidebar_state="expanded")
    inject_css()
    init_session_state()
    render_sidebar()
    st.markdown(f'''
    <div class="hero">
        <h1>{svg("globe")} AWSC GLOBAL PROJECT</h1>
        <p>Automated Certificate Generation and Delivery System</p>
    </div>
    ''', unsafe_allow_html=True)
    render_step_upload_template()
    render_step_upload_csv()
    render_step_customize()
    render_step_preview()
    render_step_send()


def init_session_state() -> None:
    defaults = {
        "template_file": None, "template_format": None, "template_bytes": None,
        "csv_file": None, "attendees": [], "csv_errors": [],
        "font_size": 40, "font_color": "#FFFFFF", "font_path": "assets/fonts/Arial.ttf",
        "selected_font": "Arial (Default)", "vertical_position": 50,
        "email_subject": "Your Certificate of Achievement",
        "email_body": "Congratulations! Please find your certificate attached.\n\nBest regards,\nAWSC Global",
        "send_in_progress": False, "show_confirm": False,
        "send_results": None, "generated_certs": [], "zip_bytes": None,
        "theme_mode": "dark",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f'<div class="sidebar-title">{svg("globe")} AWSC GLOBAL</div>', unsafe_allow_html=True)
        st.caption(f"v{APP_VERSION}")
        st.divider()

        # Theme toggle
        theme = get_theme()
        theme_icon = "☀️" if theme == "dark" else "🌙"
        theme_label = "Light Mode" if theme == "dark" else "Dark Mode"
        if st.button(f"{theme_icon} {theme_label}", key="theme_toggle", use_container_width=True):
            st.session_state["theme_mode"] = "light" if theme == "dark" else "dark"
            st.rerun()
        st.divider()

        st.markdown(f"**{svg('mail')} Email Service**", unsafe_allow_html=True)
        if EmailSender.check_credentials():
            st.markdown(bdg(f"{svg('check')} Connected", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(bdg(f"{svg('warn')} Not configured", "warn"), unsafe_allow_html=True)
            st.caption("Add credentials to enable sending.")
        st.divider()
        st.markdown("**Workflow**")
        t = bool(st.session_state.get("template_bytes"))
        c = bool(st.session_state.get("attendees"))
        s = bool(st.session_state.get("send_results"))
        items = [("Template", t), ("Attendees", c), ("Customize", True), ("Preview", t and c), ("Deliver", s)]
        for name, done in items:
            mark = svg("check") if done else '<span style="color:#475569">--</span>'
            st.markdown(f"{mark} {name}", unsafe_allow_html=True)


def render_step_upload_template() -> None:
    step_hdr(1, "Upload Certificate Template", "image")
    uploaded = st.file_uploader("Drop template file here", type=["png","jpg","jpeg","pdf"], help="PNG, JPG, or PDF. Max 10MB.", key="tpl_up")
    if uploaded:
        if uploaded.size > MAX_TEMPLATE_SIZE_MB * 1024 * 1024:
            st.markdown(bdg(f"{svg('x-circle')} File exceeds {MAX_TEMPLATE_SIZE_MB}MB", "err"), unsafe_allow_html=True)
            return
        ext = uploaded.name.rsplit(".",1)[-1].lower()
        fmt = "jpg" if ext in ("jpg","jpeg") else ext
        fb = uploaded.read()
        st.session_state["template_file"] = uploaded
        st.session_state["template_format"] = fmt
        st.session_state["template_bytes"] = fb
        st.session_state["generated_certs"] = []
        st.session_state["zip_bytes"] = None
        if fmt in ("png","jpg"):
            st.image(fb, use_container_width=True)
        elif fmt == "pdf":
            try:
                doc = fitz.open(stream=fb, filetype="pdf")
                pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2,2))
                st.image(pix.tobytes("png"), use_container_width=True)
                doc.close()
            except Exception as e:
                st.error(f"PDF render error: {e}")
        st.markdown(bdg(f"{svg('check')} Template ready", "ok"), unsafe_allow_html=True)
    elif st.session_state["template_bytes"]:
        st.markdown(bdg(f"{svg('check')} Template loaded", "ok"), unsafe_allow_html=True)


def render_step_upload_csv() -> None:
    step_hdr(2, "Upload Attendee List", "users")
    uploaded = st.file_uploader(
        "CSV or XLSX with 'name' and 'email' columns",
        type=["csv", "xlsx"],
        help="Max 5MB",
        key="csv_up",
    )
    if uploaded:
        if uploaded.size > MAX_CSV_SIZE_MB * 1024 * 1024:
            st.markdown(bdg(f"{svg('x-circle')} Exceeds {MAX_CSV_SIZE_MB}MB", "err"), unsafe_allow_html=True)
            return
        try:
            parser = CSVParser()
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            if ext == "xlsx":
                file_bytes = uploaded.read()
                result = parser.parse_xlsx(file_bytes)
            else:
                raw_bytes = uploaded.read()
                # Handle BOM and common encodings
                try:
                    content = raw_bytes.decode("utf-8-sig")  # Handles UTF-8 with BOM
                except UnicodeDecodeError:
                    try:
                        content = raw_bytes.decode("latin-1")
                    except UnicodeDecodeError:
                        content = raw_bytes.decode("utf-8", errors="replace")
                result = parser.parse(content)
            st.session_state["attendees"] = result.records
            st.session_state["csv_errors"] = result.errors
            st.session_state["csv_file"] = uploaded
            st.session_state["generated_certs"] = []
            st.session_state["zip_bytes"] = None

            # --- Deep Validation Report ---
            # Count unique rejected rows (a row can have multiple errors)
            rejected_rows = len({err.row_number for err in result.errors})
            total_rows = len(result.records) + rejected_rows
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f'<div class="kpi"><div class="kpi-val" style="color:#818CF8">{total_rows}</div><div class="kpi-lbl">Total Rows</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="kpi"><div class="kpi-val" style="color:#10B981">{len(result.records)}</div><div class="kpi-lbl">Valid Attendees</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="kpi"><div class="kpi-val" style="color:#EF4444">{rejected_rows}</div><div class="kpi-lbl">Rejected</div></div>', unsafe_allow_html=True)

            # Alert if any attendees were rejected
            if result.errors:
                st.markdown(
                    f'<div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.3); '
                    f'border-radius:8px; padding:12px 16px; margin:8px 0;">'
                    f'{svg("x-circle")} <strong style="color:#EF4444;">'
                    f'{rejected_rows} participant(s) rejected</strong> '
                    f'— check details below to ensure nobody is missed'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                with st.expander("⚠️ View rejected participants (IMPORTANT)", expanded=True):
                    for err in result.errors:
                        st.markdown(
                            f"- **Row {err.row_number}** [{err.field}]: {err.message}",
                        )
                    st.caption(
                        "Fix these in your file and re-upload to include all participants."
                    )
            else:
                st.markdown(
                    f'<div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3); '
                    f'border-radius:8px; padding:12px 16px; margin:8px 0;">'
                    f'{svg("check")} <strong style="color:#10B981;">'
                    f'All {len(result.records)} participants validated successfully</strong> '
                    f'— no issues found'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if result.records:
                st.markdown(bdg(f"{svg('check')} Attendees loaded", "ok"), unsafe_allow_html=True)
                with st.expander("Preview list"):
                    # Build scrollable list showing all attendees
                    list_html = '<div style="max-height:300px; overflow-y:auto; padding:8px; border-radius:6px;">'
                    for i, r in enumerate(result.records, 1):
                        list_html += f'<div style="padding:4px 0; border-bottom:1px solid rgba(128,128,128,0.15); font-size:0.85rem;">{i}. {r.name} &nbsp;|&nbsp; <span style="opacity:0.7;">{r.email}</span></div>'
                    list_html += '</div>'
                    st.markdown(list_html, unsafe_allow_html=True)
                    st.caption(f"Total: {len(result.records)} attendees")
        except ValueError as e:
            st.markdown(bdg(f"{svg('x-circle')} {e}", "err"), unsafe_allow_html=True)
    elif st.session_state["attendees"]:
        st.markdown(bdg(f"{svg('check')} {len(st.session_state['attendees'])} attendees loaded", "ok"), unsafe_allow_html=True)


def render_step_customize() -> None:
    step_hdr(3, "Customize Settings", "palette")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Typography**")
        fs = st.slider("Font Size (pt)", 10, 120, st.session_state["font_size"], key="cust_fs")
        st.session_state["font_size"] = fs
        fc = st.color_picker("Font Color", st.session_state["font_color"], key="cust_fc")
        st.session_state["font_color"] = fc
        vp = st.slider("Name Position (%)", 0, 100, st.session_state["vertical_position"], key="cust_vp")
        st.session_state["vertical_position"] = vp

        # Font selection from Google Fonts
        st.markdown("**Font**")
        available = get_available_fonts()
        current_font = st.session_state.get("selected_font", "Arial (Default)")
        if current_font not in available:
            current_font = "Arial (Default)"
        idx = available.index(current_font) if current_font in available else 0
        selected = st.selectbox(
            "Choose a font",
            options=available,
            index=idx,
            key="font_selector",
        )
        font_path = resolve_font_path(selected)
        if font_path:
            st.session_state["font_path"] = font_path
            st.session_state["selected_font"] = selected
            st.markdown(bdg(f"{svg('check')} {selected}", "ok"), unsafe_allow_html=True)

        # Font preview with sample name
        preview_font_family = selected.replace(" (Default)", "")
        st.markdown(
            f'<link href="https://fonts.googleapis.com/css2?family='
            f'{preview_font_family.replace(" ", "+")}&display=swap" rel="stylesheet">'
            f'<div class="font-preview-box">'
            f'<span style="font-family:\'{preview_font_family}\', serif; '
            f'font-size:{min(fs, 32)}px; color:{fc};">Juan Dela Cruz</span>'
            f'<div class="fp-label">Font Preview</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Download new fonts section
        with st.expander("Download more fonts"):
            st.caption("Browse Google Fonts — select and download to unlock them.")
            not_downloaded = [f for f in POPULAR_FONTS if not is_font_downloaded(f)]
            if not not_downloaded:
                st.markdown(bdg(f"{svg('check')} All fonts downloaded", "ok"), unsafe_allow_html=True)
            else:
                font_to_dl = st.selectbox(
                    "Select font to download",
                    options=not_downloaded,
                    key="font_dl_select",
                )
                if st.button("Download Font", key="dl_font_btn"):
                    with st.spinner(f"Downloading {font_to_dl}..."):
                        success, msg = download_font(font_to_dl)
                    if success:
                        st.markdown(
                            bdg(f"{svg('check')} {msg}", "ok"),
                            unsafe_allow_html=True,
                        )
                        st.rerun()
                    else:
                        st.markdown(
                            bdg(f"{svg('x-circle')} {msg}", "err"),
                            unsafe_allow_html=True,
                        )

    with c2:
        st.markdown("**Email Content**")
        subj = st.text_input("Subject", st.session_state["email_subject"], key="cust_subj")
        st.session_state["email_subject"] = subj
        st.markdown(
            '<div class="font-preview-box" style="border-radius:8px 8px 0 0; '
            'text-align:left; font-family:monospace; font-size:0.9rem;">'
            'Hi {name},</div>',
            unsafe_allow_html=True,
        )
        body = st.text_area(
            "Body (after greeting)",
            st.session_state["email_body"],
            height=100,
            key="cust_body",
            label_visibility="collapsed",
        )
        st.session_state["email_body"] = body
        st.markdown(bdg(f"{svg('zap')} Greeting 'Hi {{name}},' is auto-added", "info"), unsafe_allow_html=True)


def render_step_preview() -> None:
    step_hdr(4, "Preview & Edit Certificates", "eye")
    tb = st.session_state["template_bytes"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    if not tb or not att:
        st.markdown(bdg("Complete steps 1 and 2 to preview", "info"), unsafe_allow_html=True)
        return

    # --- Per-attendee name overrides stored in session state ---
    if "name_overrides" not in st.session_state:
        st.session_state["name_overrides"] = {}

    # --- Generate All Certificates Button ---
    if st.button("Generate All Certificates", use_container_width=True, key="gen_all_btn"):
        _generate_preview_batch()

    generated: List[CertificateOutput] = st.session_state.get("generated_certs", [])

    # --- Individual attendee editor ---
    st.markdown("**Edit Individual Attendee**")
    name_list = [a.name for a in att]
    selected_idx = st.selectbox(
        "Select attendee",
        options=range(len(name_list)),
        format_func=lambda i: f"{i+1}. {name_list[i]}",
        key="preview_attendee_select",
    )

    # Editable name
    current_name = st.session_state["name_overrides"].get(
        selected_idx, att[selected_idx].name
    )
    edited_name = st.text_input(
        "Name on certificate",
        value=current_name,
        key=f"edit_name_{selected_idx}",
    )
    if edited_name != att[selected_idx].name:
        st.session_state["name_overrides"][selected_idx] = edited_name
    elif selected_idx in st.session_state["name_overrides"]:
        del st.session_state["name_overrides"][selected_idx]

    # --- Controls: font size + position sliders ---
    st.markdown("**Adjust**")

    override_fs = st.slider(
        "Font Size (pt)", 10, 200,
        st.session_state.get("prev_fs_val", st.session_state["font_size"]),
        key="prev_fs_slider",
    )
    if override_fs != st.session_state.get("prev_fs_val"):
        st.session_state["prev_fs_val"] = override_fs

    col_h, col_v = st.columns(2)
    with col_h:
        override_hp = st.slider(
            "Horizontal Position (%)", 0, 100,
            st.session_state.get("prev_hp_val", 50),
            key="prev_hp_slider",
            help="0=left, 50=center, 100=right",
        )
        if override_hp != st.session_state.get("prev_hp_val"):
            st.session_state["prev_hp_val"] = override_hp
    with col_v:
        override_vp = st.slider(
            "Vertical Position (%)", 0, 100,
            st.session_state.get("prev_vp_val", st.session_state["vertical_position"]),
            key="prev_vp_slider",
            help="0=top, 50=middle, 100=bottom",
        )
        if override_vp != st.session_state.get("prev_vp_val"):
            st.session_state["prev_vp_val"] = override_vp

    # --- Click on image to reposition ---
    st.markdown(
        '<div style="background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.3); '
        'border-radius:8px; padding:8px 12px; margin:8px 0; font-size:0.82rem; color:#a5b4fc;">'
        '🖱️ <strong>Click on the preview image</strong> to set name position directly.</div>',
        unsafe_allow_html=True,
    )

    # --- Generate preview and show clickable image ---
    try:
        fc = FontConfiguration(
            font_path=st.session_state["font_path"],
            font_size=override_fs,
            font_color=FontConfiguration.parse_color(st.session_state["font_color"]),
        )
        gen = CertificateGenerator(
            template_bytes=tb,
            template_format=st.session_state["template_format"],
            font_config=fc,
        )
        prev = _generate_single_with_position(
            gen, edited_name, override_hp, override_vp
        )

        # Convert to PIL Image for streamlit_image_coordinates
        if prev.format in ("png", "jpg"):
            preview_img = prev.certificate.copy()
        elif prev.format == "pdf":
            doc = fitz.open(stream=prev.certificate, filetype="pdf")
            pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
            preview_img = Image.open(io.BytesIO(pix.tobytes("png")))
            doc.close()
        else:
            preview_img = None

        if preview_img:
            from streamlit_image_coordinates import streamlit_image_coordinates

            # Resize for display (max 800px wide to fit layout)
            display_w = min(800, preview_img.width)
            scale = display_w / preview_img.width
            display_h = int(preview_img.height * scale)
            display_img = preview_img.resize((display_w, display_h), Image.LANCZOS)

            coords = streamlit_image_coordinates(
                display_img,
                key=f"cert_click_{selected_idx}",
            )

            # If user clicked, update position
            if coords is not None:
                click_x = coords["x"]
                click_y = coords["y"]
                new_hp = int((click_x / display_w) * 100)
                new_vp = int((click_y / display_h) * 100)
                if new_hp != st.session_state.get("prev_hp_val") or new_vp != st.session_state.get("prev_vp_val"):
                    st.session_state["prev_hp_val"] = new_hp
                    st.session_state["prev_vp_val"] = new_vp
                    st.rerun()

        st.markdown(bdg(f"{svg('check')} Looks good", "ok"), unsafe_allow_html=True)
    except Exception as e:
        st.markdown(
            bdg(f"{svg('x-circle')} Preview failed: {e}", "err"),
            unsafe_allow_html=True,
        )

    # --- Certificate Gallery (after batch generation) ---
    if generated:
        st.markdown("---")
        st.markdown(f"**Generated Certificates ({len(generated)} total)**")
        st.caption("Click 'Edit' on any certificate to adjust it above, then re-generate.")
        cols_per_row = 3
        for row_start in range(0, len(generated), cols_per_row):
            cols = st.columns(cols_per_row)
            for col_idx, cert_idx in enumerate(
                range(row_start, min(row_start + cols_per_row, len(generated)))
            ):
                cert = generated[cert_idx]
                with cols[col_idx]:
                    try:
                        if cert.format in ("png", "jpg"):
                            st.image(
                                cert.certificate,
                                caption=cert.attendee_name,
                                use_container_width=True,
                            )
                        elif cert.format == "pdf":
                            doc = fitz.open(
                                stream=cert.certificate, filetype="pdf"
                            )
                            pix = doc.load_page(0).get_pixmap(
                                matrix=fitz.Matrix(1.5, 1.5)
                            )
                            st.image(
                                pix.tobytes("png"),
                                caption=cert.attendee_name,
                                use_container_width=True,
                            )
                            doc.close()
                    except Exception as e:
                        st.markdown(
                            bdg(
                                f"{svg('x-circle')} {cert.attendee_name}: {e}",
                                "err",
                            ),
                            unsafe_allow_html=True,
                        )
                    # Edit button to jump to this attendee in the editor
                    if st.button(
                        "✏️ Edit",
                        key=f"edit_cert_{cert_idx}",
                        use_container_width=True,
                    ):
                        st.session_state["preview_attendee_select"] = cert_idx
                        st.rerun()


def _generate_single_with_position(
    gen: CertificateGenerator,
    name: str,
    horizontal_pct: int,
    vertical_pct: int,
) -> CertificateOutput:
    """Generate a single certificate with custom horizontal and vertical position.

    For horizontal positioning, we override the ImageProcessor's centering logic.
    """
    if gen._image_processor:
        # Custom rendering with horizontal control
        proc = gen._image_processor
        bbox = proc._font.getbbox(name)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Horizontal: 0=left edge, 50=center, 100=right edge
        max_x = proc._width - text_width
        x = int((horizontal_pct / 100) * max_x) if max_x > 0 else 0

        # Vertical: percentage of template height
        y = int((vertical_pct / 100) * proc._height) - text_height // 2
        y = max(0, min(y, proc._height - text_height))

        from PIL import ImageDraw

        output = proc._template.copy()
        draw = ImageDraw.Draw(output)
        draw.text(
            (x, y),
            name,
            font=proc._font,
            fill=proc._font_config.font_color,
        )
        return CertificateOutput(
            attendee_name=name, certificate=output, format=gen.format
        )
    else:
        # PDF — use vertical only (horizontal always centered in PDF processor)
        return gen.generate(
            name, vertical_position=vertical_pct, vertical_as_percentage=True
        )


def _generate_preview_batch() -> None:
    """Generate all certificates using preview settings (font size + position)."""
    tb = st.session_state["template_bytes"]
    tf = st.session_state["template_format"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    overrides = st.session_state.get("name_overrides", {})

    # Use preview step settings (not step 3 defaults)
    preview_fs = st.session_state.get("prev_fs_val", st.session_state["font_size"])
    preview_hp = st.session_state.get("prev_hp_val", 50)
    preview_vp = st.session_state.get("prev_vp_val", st.session_state["vertical_position"])

    bar = st.progress(0)
    status = st.empty()
    status.text("Generating certificates...")

    try:
        fc = FontConfiguration(
            font_path=st.session_state["font_path"],
            font_size=preview_fs,
            font_color=FontConfiguration.parse_color(st.session_state["font_color"]),
        )
        gen = CertificateGenerator(
            template_bytes=tb, template_format=tf, font_config=fc
        )
        # Apply name overrides
        names = []
        for i, a in enumerate(att):
            names.append(overrides.get(i, a.name))

        # Generate with horizontal + vertical position support
        certificates: List[CertificateOutput] = []
        errors: List = []
        for i, name in enumerate(names):
            try:
                cert = _generate_single_with_position(
                    gen, name, preview_hp, preview_vp
                )
                certificates.append(cert)
            except Exception as e:
                errors.append((name, str(e)))
            if (i + 1) % max(1, len(names) // 20) == 0:
                bar.progress((i + 1) / len(names))

        st.session_state["generated_certs"] = certificates
        st.session_state["zip_bytes"] = _make_zip(certificates)
        bar.progress(1.0)
        status.text(f"Done — {len(certificates)} certificates generated.")
        if errors:
            for name, msg in errors:
                st.markdown(
                    bdg(f"{svg('x-circle')} {name}: {msg}", "err"),
                    unsafe_allow_html=True,
                )
    except Exception as e:
        st.error(f"Generation failed: {e}")


def render_step_send() -> None:
    step_hdr(5, "Generate and Deliver", "send")
    tb = st.session_state["template_bytes"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    subj = st.session_state["email_subject"].strip()
    body = st.session_state["email_body"].strip()
    sip = st.session_state["send_in_progress"]
    ready = all([tb, att, subj, body])

    # Show download button if certificates were already generated in step 4
    zb = st.session_state.get("zip_bytes")
    if zb and not st.session_state["send_results"]:
        st.markdown(bdg(f"{svg('check')} {len(st.session_state.get('generated_certs', []))} certificates ready", "ok"), unsafe_allow_html=True)
        st.download_button(
            "Download Certificates ZIP",
            data=zb,
            file_name="certificates.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.markdown("---")

    # Show manual edits summary if any overrides exist
    overrides = st.session_state.get("name_overrides", {})
    if overrides:
        with st.expander(f"✏️ {len(overrides)} name(s) manually edited (from Preview)"):
            for idx, new_name in overrides.items():
                original = att[idx].name if idx < len(att) else "?"
                st.text(f"  {original}  →  {new_name}")
            st.caption("These edits will be applied to the final certificates.")

    if not ready:
        missing = []
        if not tb: missing.append("Template")
        if not att: missing.append("CSV")
        if not subj: missing.append("Subject")
        if not body: missing.append("Body")
        st.markdown(bdg(f"{svg('warn')} Missing: {', '.join(missing)}", "warn"), unsafe_allow_html=True)
        st.button("Send All", disabled=True, use_container_width=True)
        return
    if not st.session_state["show_confirm"] and not sip:
        c1, c2 = st.columns([2, 1])
        with c1:
            if st.button("Send All Certificates", use_container_width=True):
                st.session_state["show_confirm"] = True
                st.rerun()
        with c2:
            if st.button("Generate ZIP Only", use_container_width=True):
                _generate_only()
    if st.session_state["show_confirm"] and not sip:
        st.warning(f"Sending to {len(att)} attendees. Confirm?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm Send", use_container_width=True):
                st.session_state["show_confirm"] = False
                _execute_send()
        with c2:
            if st.button("Cancel", use_container_width=True):
                st.session_state["show_confirm"] = False
                st.rerun()
    if st.session_state["send_results"]:
        _display_results()


def _get_final_names(att: List[AttendeeRecord]) -> List[str]:
    """Get the final name list applying any manual overrides from the preview step."""
    overrides = st.session_state.get("name_overrides", {})
    return [overrides.get(i, a.name) for i, a in enumerate(att)]


def _generate_only() -> None:
    tb = st.session_state["template_bytes"]
    tf = st.session_state["template_format"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    names = _get_final_names(att)

    # Use preview settings
    preview_fs = st.session_state.get("prev_fs_val", st.session_state["font_size"])
    preview_hp = st.session_state.get("prev_hp_val", 50)
    preview_vp = st.session_state.get("prev_vp_val", st.session_state["vertical_position"])

    bar = st.progress(0)
    status = st.empty()
    status.text("Generating...")
    try:
        fc = FontConfiguration(
            font_path=st.session_state["font_path"],
            font_size=preview_fs,
            font_color=FontConfiguration.parse_color(st.session_state["font_color"]),
        )
        gen = CertificateGenerator(template_bytes=tb, template_format=tf, font_config=fc)
        certificates: List[CertificateOutput] = []
        for i, name in enumerate(names):
            cert = _generate_single_with_position(gen, name, preview_hp, preview_vp)
            certificates.append(cert)
            if (i + 1) % max(1, len(names) // 10) == 0:
                bar.progress((i + 1) / len(names) * 0.8)
        st.session_state["generated_certs"] = certificates
        bar.progress(0.9)
        st.session_state["zip_bytes"] = _make_zip(certificates)
        bar.progress(1.0)
        status.text(f"Done. {len(certificates)} certificates ready.")
    except Exception as e:
        st.error(f"Generation failed: {e}")


def _execute_send() -> None:
    st.session_state["send_in_progress"] = True
    tb = st.session_state["template_bytes"]
    tf = st.session_state["template_format"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    names = _get_final_names(att)

    # Use preview settings
    preview_fs = st.session_state.get("prev_fs_val", st.session_state["font_size"])
    preview_hp = st.session_state.get("prev_hp_val", 50)
    preview_vp = st.session_state.get("prev_vp_val", st.session_state["vertical_position"])

    bar = st.progress(0)
    status = st.empty()
    status.text(f"Generating {len(att)} certificates...")
    try:
        fc = FontConfiguration(
            font_path=st.session_state["font_path"],
            font_size=preview_fs,
            font_color=FontConfiguration.parse_color(st.session_state["font_color"]),
        )
        gen = CertificateGenerator(template_bytes=tb, template_format=tf, font_config=fc)

        # Generate with position support
        certificates: List[CertificateOutput] = []
        for i, name in enumerate(names):
            cert = _generate_single_with_position(gen, name, preview_hp, preview_vp)
            certificates.append(cert)
            if (i + 1) % max(1, len(names) // 10) == 0:
                bar.progress((i + 1) / len(names) * 0.3)

        st.session_state["generated_certs"] = certificates
        bar.progress(0.3)
        status.text("Sending emails...")
        cert_bytes: List[bytes] = []
        for cert in certificates:
            if cert.format in ("png", "jpg"):
                buf = io.BytesIO()
                if cert.format == "png":
                    cert.certificate.save(buf, format="PNG", optimize=False)
                else:
                    rgb = cert.certificate.convert("RGB") if cert.certificate.mode == "RGBA" else cert.certificate
                    rgb.save(buf, format="JPEG", quality=95, subsampling=0)
                cert_bytes.append(buf.getvalue())
            else:
                cert_bytes.append(cert.certificate)
        # Match certificates to attendees by index (order-preserving)
        ok_att = []
        cert_idx = 0
        for i, name in enumerate(names):
            if cert_idx < len(certificates) and certificates[cert_idx].attendee_name == name:
                ok_att.append(att[i])
                cert_idx += 1
        tmpl = EmailTemplate(
            subject=st.session_state["email_subject"],
            body="Hi {name},\n\n" + st.session_state["email_body"],
        )

        def prog(cur: int, tot: int) -> None:
            bar.progress(0.3 + (cur / tot) * 0.65)
            status.text(f"Sending {cur}/{tot}...")

        sender = EmailSender()
        result = sender.send_bulk(
            recipients=ok_att,
            certificate_data=cert_bytes,
            certificate_format=tf,
            template=tmpl,
            progress_callback=prog,
        )
        st.session_state["send_results"] = result
        st.session_state["zip_bytes"] = _make_zip(certificates)
        bar.progress(1.0)
        status.text("Complete.")
    except Exception as e:
        st.error(f"Send failed: {e}")
    finally:
        st.session_state["send_in_progress"] = False


def _display_results() -> None:
    sr: SendResult = st.session_state["send_results"]
    st.markdown("---")
    st.markdown(f"**{svg('award')} Delivery Report**", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="kpi"><div class="kpi-val" style="color:#10B981">{sr.success_count}</div><div class="kpi-lbl">Delivered</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi"><div class="kpi-val" style="color:#EF4444">{sr.failure_count}</div><div class="kpi-lbl">Failed</div></div>', unsafe_allow_html=True)
    with c3:
        total = sr.success_count + sr.failure_count
        rate = (sr.success_count / total * 100) if total > 0 else 0
        st.markdown(f'<div class="kpi"><div class="kpi-val" style="color:#818CF8">{rate:.0f}%</div><div class="kpi-lbl">Success Rate</div></div>', unsafe_allow_html=True)
    if sr.failures:
        with st.expander(f"{svg('x-circle')} {sr.failure_count} failed"):
            for f in sr.failures:
                st.text(f"  {f.attendee_name} ({f.email}): {f.error_message}")
    zb = st.session_state.get("zip_bytes")
    if zb:
        st.download_button("Download All Certificates", data=zb, file_name="certificates.zip", mime="application/zip", use_container_width=True)


def _make_zip(certs: List[CertificateOutput]) -> bytes:
    if not certs:
        return b""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cert in certs:
            name = re.sub(r"[^\w\s-]", "", cert.attendee_name).replace(" ", "_")
            fn = f"{name}.{cert.format}"
            if cert.format in ("png","jpg"):
                ib = io.BytesIO()
                if cert.format == "png":
                    cert.certificate.save(ib, format="PNG", optimize=False)
                else:
                    rgb = cert.certificate.convert("RGB") if cert.certificate.mode == "RGBA" else cert.certificate
                    rgb.save(ib, format="JPEG", quality=95, subsampling=0)
                zf.writestr(fn, ib.getvalue())
            else:
                zf.writestr(fn, cert.certificate)
    return buf.getvalue()


if __name__ == "__main__":
    main()
