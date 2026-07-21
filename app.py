"""Prototype Cert Automation — Automated Certificate Generator & Email Sender.

Modern Streamlit UI with Lucide SVG icons and professional light theme.
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
    "sun": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>',
    "mouse-pointer": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/><path d="M13 13l6 6"/></svg>',
    "target": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    "pencil": '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/></svg>',
    "plus": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>',
    "minus": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/></svg>',
    "refresh": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>',
    "alert-triangle": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
}


def svg(name: str) -> str:
    """Return inline SVG by name."""
    return ICONS.get(name, "")


def inject_css() -> None:
    """Inject professional light mode CSS."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"],
    .main, .main .block-container {
        background-color: #FFFFFF !important; color: #1E293B !important;
        font-family: 'Inter', sans-serif !important;
    }
    #MainMenu, footer { visibility: hidden; }
    header [data-testid="stToolbar"] { visibility: visible !important; }
    /* Ensure sidebar toggle is always visible */
    button[kind="header"] { visibility: visible !important; }
    .stApp p, .stApp span, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] span,
    [data-testid="stText"] { color: #1E293B !important; }
    [data-testid="stCaptionContainer"] p, .stApp small { color: #64748b !important; }
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"] { background-color: #F1F5F9 !important; }
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] li,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span {
        color: #1E293B !important;
    }
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: #64748b !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(0,0,0,0.1) !important; }
    section[data-testid="stSidebar"] .stButton > button {
        background-color: #F8FAFC !important; color: #1E293B !important;
        border: 1px solid rgba(0,0,0,0.12) !important; border-radius: 8px;
    }
    section[data-testid="stSidebar"] svg { color: #1E293B !important; }
    [data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"] {
        background-color: #FFFFFF !important; border-color: rgba(0,0,0,0.1) !important;
    }
    [data-baseweb="input"] input, [data-baseweb="select"] input,
    [data-baseweb="select"] [data-testid="stMarkdownContainer"] p { color: #1E293B !important; }
    [data-baseweb="textarea"] textarea { background-color: #FFFFFF !important; color: #1E293B !important; }
    [data-baseweb="popover"], [data-baseweb="menu"], ul[role="listbox"] { background-color: #F8FAFC !important; }
    ul[role="listbox"] li { color: #1E293B !important; }
    [data-testid="stSlider"] p, [data-testid="stSlider"] [data-testid="stThumbValue"],
    [data-testid="stSlider"] [data-testid="stTickBarMin"],
    [data-testid="stSlider"] [data-testid="stTickBarMax"] { color: #1E293B !important; }
    [data-testid="stExpander"] { border-color: rgba(0,0,0,0.1) !important; background-color: #F8FAFC !important; }
    [data-testid="stExpander"] summary, [data-testid="stExpander"] summary span { color: #1E293B !important; }
    .stApp .stButton > button {
        border-radius: 8px; font-weight: 600; background-color: #F8FAFC !important;
        color: #1E293B !important; border: 1px solid rgba(0,0,0,0.12) !important;
    }
    .stApp .stButton > button:hover { border-color: #4F46E5 !important; color: #4F46E5 !important; }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #4F46E5, #6366F1) !important; color: #FFFFFF !important;
        border: none !important; border-radius: 8px; font-weight: 600;
    }
    .stDownloadButton > button:hover { background: linear-gradient(135deg, #4338CA, #4F46E5) !important; }
    @media (max-width: 768px) {
        .hero { padding: 1.5rem 1rem !important; margin-bottom: 1.2rem !important; }
        .hero h1 { font-size: 1.4rem !important; }
        .hero p { font-size: 0.85rem !important; }
        .kpi { padding: 0.8rem !important; }
        .kpi-val { font-size: 1.3rem !important; }
        .step-hdr { margin: 1rem 0 0.5rem 0 !important; }
        .step-lbl { font-size: 0.9rem !important; }
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
        [data-testid="stHorizontalBlock"] > div { flex: 1 1 100% !important; min-width: 100% !important; }
        section[data-testid="stSidebar"] { width: 100% !important; }
        .stButton > button, .stDownloadButton > button { min-height: 44px; }
        div[data-testid="stFileUploader"] { padding: 0.8rem; }
    }
    @media (min-width: 769px) and (max-width: 1024px) {
        .hero h1 { font-size: 1.7rem !important; }
        .kpi-val { font-size: 1.5rem !important; }
    }
    .hero {
        background: linear-gradient(135deg, #1e3a5f 0%, #4F46E5 100%); border-radius: 16px; padding: 2.5rem 2rem;
        margin-bottom: 2rem; text-align: center; border: 1px solid rgba(255,255,255,0.15);
        box-shadow: 0 20px 60px rgba(79,70,229,0.15);
    }
    .hero h1, .hero h1 span, .hero [data-testid='stMarkdownContainer'] h1 { color: #FFFFFF !important; font-size: 2rem; font-weight: 700; margin: 0; text-shadow: none; }
    .hero p { color: rgba(255,255,255,0.85) !important; font-size: 1rem; margin-top: 0.4rem; }
    .step-hdr { display: flex; align-items: center; gap: 10px; margin: 2rem 0 0.8rem 0; padding-top: 1.5rem; border-top: 1px solid rgba(0,0,0,0.06); }
    .step-num {
        background: linear-gradient(135deg, #4F46E5, #6366F1); color: #FFFFFF !important;
        width: 32px; height: 32px; border-radius: 8px;
        display: inline-flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 0.85rem; box-shadow: 0 2px 6px rgba(79,70,229,0.3);
    }
    .step-lbl { color: #1E293B !important; font-size: 1.1rem; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
    .badge { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 500; }
    .badge-ok { background: rgba(16,185,129,0.1); color: #059669 !important; border: 1px solid rgba(16,185,129,0.3); }
    .badge-warn { background: rgba(245,158,11,0.1); color: #D97706 !important; border: 1px solid rgba(245,158,11,0.3); }
    .badge-err { background: rgba(239,68,68,0.1); color: #DC2626 !important; border: 1px solid rgba(239,68,68,0.3); }
    .badge-info { background: rgba(79,70,229,0.08); color: #4F46E5 !important; border: 1px solid rgba(79,70,229,0.2); }
    .badge svg { color: inherit !important; }
    .kpi { background: #FFFFFF; border: 1px solid rgba(0,0,0,0.08); border-radius: 10px; padding: 1.2rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
    .kpi-val { font-size: 1.8rem; font-weight: 700; }
    .kpi-lbl { font-size: 0.78rem; color: #64748b !important; margin-top: 2px; }
    div[data-testid="stFileUploader"] {
        border: 2px dashed rgba(79,70,229,0.35); border-radius: 12px; padding: 0.5rem;
        background-color: rgba(79,70,229,0.03) !important;
        transition: border-color 0.2s, background-color 0.2s;
    }
    div[data-testid="stFileUploader"]:hover { border-color: #4F46E5; background-color: rgba(79,70,229,0.06) !important; }
    .sidebar-title { color: #4F46E5 !important; font-size: 1.3rem; font-weight: 700; text-align: center; }
    .font-preview-box {
        background: #F8FAFC; border: 1px solid rgba(0,0,0,0.08);
        border-radius: 8px; padding: 16px; margin: 8px 0; text-align: center;
    }
    .font-preview-box .fp-label { color: #64748b !important; font-size: 0.7rem; margin-top: 6px; }
    img { max-width: 100%; height: auto; }
    div[data-testid="stFileUploader"] button {
        background: linear-gradient(135deg, #4F46E5, #6366F1) !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    div[data-testid="stFileUploader"] section {
        color: #475569 !important;
    }
    div[data-testid="stFileUploader"] small {
        color: #64748b !important;
    }
    [data-testid="stColorPicker"] > div > div > div {
        border: 2px solid rgba(0,0,0,0.1) !important;
        border-radius: 4px;
    }
    [data-testid="stNumberInput"] button {
        color: #1E293B !important;
        border-color: rgba(0,0,0,0.1) !important;
    }
    [data-testid="stNumberInput"] button svg {
        color: #1E293B !important;
    }
    textarea::placeholder { color: #94a3b8 !important; opacity: 0.8 !important; }
    input::placeholder { color: #94a3b8 !important; opacity: 0.8 !important; }
    .hero svg { color: #FFFFFF !important; }
    .step-lbl svg { color: #4F46E5 !important; stroke: #4F46E5 !important; }
    </style>
    """, unsafe_allow_html=True)

def step_hdr(num: int, label: str, icon_name: str) -> None:
    st.markdown(f'<div class="step-hdr"><span class="step-num">{num}</span><span class="step-lbl">{svg(icon_name)} {label}</span></div>', unsafe_allow_html=True)


def bdg(text: str, variant: str = "info") -> str:
    return f'<span class="badge badge-{variant}">{text}</span>'


def main() -> None:
    st.set_page_config(page_title="Prototype Cert Automation", page_icon=None, layout="wide", initial_sidebar_state="expanded")
    inject_css()
    init_session_state()
    render_sidebar()
    st.markdown(f'''
    <div class="hero">
        <h1>{svg("globe")} Prototype Cert Automation</h1>
        <p>Automated Certificate Generation and Delivery System</p>
    </div>
    ''', unsafe_allow_html=True)
    render_step_upload_template()
    render_step_upload_csv()
    render_step_email()
    render_step_design()
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
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f'<div class="sidebar-title">{svg("globe")} AWSC GLOBAL</div>', unsafe_allow_html=True)
        st.caption(f"v{APP_VERSION}")
        st.divider()

        st.markdown(f"**{svg('mail')} Email Service**", unsafe_allow_html=True)
        if st.session_state.get("gmail_logged_in"):
            st.markdown(bdg(f"{svg('check')} " + st.session_state.get("gmail_user", ""), "ok"), unsafe_allow_html=True)
        elif EmailSender.check_credentials():
            st.markdown(bdg(f"{svg('check')} Connected (config)", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(bdg(f"{svg('warn')} Not logged in", "warn"), unsafe_allow_html=True)
        st.divider()
        st.markdown("**Workflow**")
        t = bool(st.session_state.get("template_bytes"))
        c = bool(st.session_state.get("attendees"))
        s = bool(st.session_state.get("send_results"))
        items = [("Template", t), ("Attendees", c), ("Email", True), ("Design", t and c), ("Deliver", s)]
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
                with st.expander(f"{svg('alert-triangle')} View rejected participants (IMPORTANT)", expanded=True):
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



def render_step_email() -> None:
    step_hdr(3, "Email Settings", "mail")
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

    # Gmail login form
    st.markdown("---")
    st.markdown(f"**{svg('mail')} Gmail Account**", unsafe_allow_html=True)
    if st.session_state.get("gmail_logged_in"):
        st.markdown(bdg(f"{svg('check')} Logged in as " + st.session_state.get("gmail_user", ""), "ok"), unsafe_allow_html=True)
        if st.button("Logout", key="gmail_logout_btn"):
            st.session_state["gmail_logged_in"] = False
            st.session_state["gmail_user"] = ""
            st.session_state["gmail_app_password"] = ""
            st.rerun()
    else:
        st.caption("Enter your Gmail and App Password to send from your account.")
        gmail_email = st.text_input("Gmail Address", key="gmail_email_input", placeholder="youremail@gmail.com")
        gmail_pass = st.text_input("App Password", key="gmail_pass_input", type="password", placeholder="xxxx xxxx xxxx xxxx")
        if st.button("Connect Gmail", key="gmail_login_btn", use_container_width=True):
            if gmail_email and gmail_pass:
                st.session_state["gmail_logged_in"] = True
                st.session_state["gmail_user"] = gmail_email
                st.session_state["gmail_app_password"] = gmail_pass
                st.rerun()
            else:
                st.markdown(bdg(f"{svg('x-circle')} Both fields required", "err"), unsafe_allow_html=True)
        with st.expander("How to get App Password"):
            st.markdown("1. Go to myaccount.google.com\n2. Enable 2-Step Verification\n3. Search for App Passwords\n4. Generate one for Mail\n5. Copy the 16-char password")



def render_step_design() -> None:
    step_hdr(4, "Certificate Design", "palette")
    tb = st.session_state["template_bytes"]
    att: List[AttendeeRecord] = st.session_state["attendees"]

    # --- Typography controls ---
    st.markdown("**Typography**")
    fc = st.color_picker("Font Color", st.session_state["font_color"], key="cust_fc")
    st.session_state["font_color"] = fc
    vp = st.slider("Name Position (%)", 0, 100, st.session_state["vertical_position"], key="cust_vp")
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
        f'font-size:{min(st.session_state["font_size"], 32)}px; color:{st.session_state["font_color"]};">Juan Dela Cruz</span>'
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


    # --- Certificate Preview (requires template + attendees) ---
    st.markdown("---")
    if not tb or not att:
        st.markdown(bdg("Complete steps 1 and 2 to preview", "info"), unsafe_allow_html=True)
        return

    # --- Per-attendee name overrides stored in session state ---
    if "name_overrides" not in st.session_state:
        st.session_state["name_overrides"] = {}

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

    override_fs = st.number_input(
        "Font Size (pt)", min_value=10, max_value=200, step=1,
        value=st.session_state.get("prev_fs_val", st.session_state["font_size"]),
        key="prev_fs_input",
    )
    if override_fs != st.session_state.get("prev_fs_val"):
        st.session_state["prev_fs_val"] = override_fs

    col_h, col_v = st.columns(2)
    with col_h:
        override_hp = st.number_input(
            "Horizontal Position (%)", min_value=0, max_value=100, step=1,
            value=st.session_state.get("prev_hp_val", 50),
            key="prev_hp_input",
            help="0=left, 50=center, 100=right",
        )
        if override_hp != st.session_state.get("prev_hp_val"):
            st.session_state["prev_hp_val"] = override_hp
    with col_v:
        override_vp = st.number_input(
            "Vertical Position (%)", min_value=0, max_value=100, step=1,
            value=st.session_state.get("prev_vp_val", st.session_state["vertical_position"]),
            key="prev_vp_input",
            help="0=top, 50=middle, 100=bottom",
        )
        if override_vp != st.session_state.get("prev_vp_val"):
            st.session_state["prev_vp_val"] = override_vp

    # --- Click on image to reposition ---
    st.markdown(
        f'<div style="background:rgba(79,70,229,0.06); border:1px solid rgba(79,70,229,0.2); '
        f'border-radius:8px; padding:8px 12px; margin:8px 0; font-size:0.82rem; color:#4F46E5;">'
        f'{svg("mouse-pointer")} <strong>Click on the preview image</strong> to set name position directly.</div>',
        unsafe_allow_html=True,
    )

    # --- Generate preview and show clickable image ---
    try:
        font_cfg = FontConfiguration(
            font_path=st.session_state["font_path"],
            font_size=override_fs,
            font_color=FontConfiguration.parse_color(st.session_state["font_color"]),
        )
        gen = CertificateGenerator(
            template_bytes=tb,
            template_format=st.session_state["template_format"],
            font_config=font_cfg,
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
            try:
                from streamlit_image_coordinates import (
                    streamlit_image_coordinates as st_img_coords,
                )
            except ImportError:
                st_img_coords = None

            if st_img_coords is not None:
                # Resize for display (max 800px wide to fit layout)
                display_w = min(800, preview_img.width)
                scale = display_w / preview_img.width
                display_h = int(preview_img.height * scale)
                display_img = preview_img.resize(
                    (display_w, display_h), Image.LANCZOS
                )

                coords = st_img_coords(
                    display_img,
                    key=f"cert_click_{selected_idx}",
                )

                # If user clicked, update position
                if coords is not None:
                    click_x = coords["x"]
                    click_y = coords["y"]
                    new_hp = int((click_x / display_w) * 100)
                    new_vp = int((click_y / display_h) * 100)
                    if (
                        new_hp != st.session_state.get("prev_hp_val")
                        or new_vp != st.session_state.get("prev_vp_val")
                    ):
                        st.session_state["prev_hp_val"] = new_hp
                        st.session_state["prev_vp_val"] = new_vp
                        st.rerun()
            else:
                # Fallback: show static image when package not installed
                st.image(preview_img, use_container_width=True)
                st.caption(
                    "Install streamlit-image-coordinates for click-to-position."
                )

        st.markdown(bdg(f"{svg('check')} Looks good", "ok"), unsafe_allow_html=True)
    except Exception as e:
        st.markdown(
            bdg(f"{svg('x-circle')} Preview failed: {e}", "err"),
            unsafe_allow_html=True,
        )



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

    # Clear stale gallery editing states from prior generation
    stale_keys = [k for k in st.session_state if k.startswith("editing_cert_")]
    for k in stale_keys:
        del st.session_state[k]

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

    if not tb or not att:
        st.markdown(bdg("Complete steps 1-4 first", "info"), unsafe_allow_html=True)
        return

    # ===== SUB-STEP A: GENERATE =====
    st.markdown("**Step 5a: Generate Certificates**")

    if st.button("\U0001f4e6 Generate All", use_container_width=True, key="gen_all_btn"):
        _generate_preview_batch()

    generated: List[CertificateOutput] = st.session_state.get("generated_certs", [])

    if generated:
        st.success(f"\u2705 {len(generated)} certificates generated")
        with st.expander(f"Preview ({len(generated)} certificates)", expanded=False):
            cols_per_row = 4
            for row_start in range(0, len(generated), cols_per_row):
                cols = st.columns(cols_per_row)
                for col_idx, cert_idx in enumerate(
                    range(row_start, min(row_start + cols_per_row, len(generated)))
                ):
                    cert = generated[cert_idx]
                    with cols[col_idx]:
                        try:
                            if cert.format in ("png", "jpg"):
                                st.image(cert.certificate, caption=cert.attendee_name, use_container_width=True)
                            elif cert.format == "pdf":
                                doc = fitz.open(stream=cert.certificate, filetype="pdf")
                                pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                                st.image(pix.tobytes("png"), caption=cert.attendee_name, use_container_width=True)
                                doc.close()
                        except Exception as e:
                            st.error(f"{cert.attendee_name}: {e}")

        # ===== SUB-STEP B: DOWNLOAD ZIP =====
        st.markdown("---")
        st.markdown("**Step 5b: Download ZIP**")
        zb = st.session_state.get("zip_bytes")
        if not zb:
            # Generate zip if not yet created
            zb = _make_zip(generated)
            st.session_state["zip_bytes"] = zb
        if zb:
            st.download_button(
                "\U0001f4e5 Download All Certificates (ZIP)",
                data=zb,
                file_name="certificates.zip",
                mime="application/zip",
                use_container_width=True,
            )

        # ===== SUB-STEP C: SEND TO GMAIL =====
        st.markdown("---")
        st.markdown("**Step 5c: Send to Gmail**")

        if not st.session_state.get("gmail_connected"):
            st.warning("Connect your Gmail in the sidebar first.")
            return

        ready = all([subj, body])
        if not ready:
            missing = []
            if not subj: missing.append("Subject")
            if not body: missing.append("Body")
            st.warning(f"Missing: {", ".join(missing)}")
            return

        sip = st.session_state["send_in_progress"]
        if not st.session_state["show_confirm"] and not sip:
            if st.button("\U0001f4e7 Send via Email", use_container_width=True, key="send_email_btn"):
                st.session_state["show_confirm"] = True
                st.rerun()
        if st.session_state["show_confirm"] and not sip:
            st.warning(f"About to send {len(att)} emails from {st.session_state['gmail_sender']}. Confirm?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("\u2705 Confirm Send", use_container_width=True, key="confirm_send_btn"):
                    st.session_state["show_confirm"] = False
                    _execute_send()
            with c2:
                if st.button("\u274c Cancel", use_container_width=True, key="cancel_send_btn"):
                    st.session_state["show_confirm"] = False
                    st.rerun()
        if st.session_state["send_results"]:
            _display_results()


def _get_final_names(att: List[AttendeeRecord]) -> List[str]:
    """Get the final name list applying any manual overrides from the preview step."""
    overrides = st.session_state.get("name_overrides", {})
    return [overrides.get(i, a.name) for i, a in enumerate(att)]


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

        from utils.models import GmailCredentials
        creds = None
        if st.session_state.get("gmail_logged_in"):
            creds = GmailCredentials(
                sender_email=st.session_state["gmail_user"],
                app_password=st.session_state["gmail_app_password"],
            )
        sender = EmailSender(credentials=creds)
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

