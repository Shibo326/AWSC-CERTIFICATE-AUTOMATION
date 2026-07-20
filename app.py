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


def inject_css() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp { font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }

    .hero {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f2027 50%, #203a43 100%);
        border-radius: 16px; padding: 2.5rem 2rem; margin-bottom: 2rem;
        text-align: center; border: 1px solid rgba(255,255,255,0.05);
        box-shadow: 0 20px 60px rgba(0,0,0,0.4);
    }
    .hero h1 { color: #f0f4f8; font-size: 2rem; font-weight: 700; margin: 0; letter-spacing: 1px; }
    .hero p { color: rgba(240,244,248,0.7); font-size: 1rem; margin-top: 0.4rem; font-weight: 300; }

    .step-hdr { display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 0.8rem 0; }
    .step-num {
        background: linear-gradient(135deg, #1e3a5f, #2d5a7b);
        color: #a8d0e6; width: 28px; height: 28px; border-radius: 6px;
        display: inline-flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 0.8rem;
    }
    .step-lbl { color: #e2e8f0; font-size: 1.05rem; font-weight: 600; }

    .badge {
        display: inline-flex; align-items: center; gap: 5px;
        padding: 4px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 500;
    }
    .badge-ok { background: rgba(16,185,129,0.1); color: #10B981; border: 1px solid rgba(16,185,129,0.25); }
    .badge-warn { background: rgba(245,158,11,0.1); color: #F59E0B; border: 1px solid rgba(245,158,11,0.25); }
    .badge-err { background: rgba(239,68,68,0.1); color: #EF4444; border: 1px solid rgba(239,68,68,0.25); }
    .badge-info { background: rgba(99,102,241,0.1); color: #818CF8; border: 1px solid rgba(99,102,241,0.25); }

    .kpi { background: #141b2d; border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 1.2rem; text-align: center; }
    .kpi-val { font-size: 1.8rem; font-weight: 700; }
    .kpi-lbl { font-size: 0.78rem; color: #64748b; margin-top: 2px; }

    div[data-testid="stFileUploader"] {
        border: 2px dashed rgba(45,90,123,0.4); border-radius: 10px; padding: 0.3rem;
    }
    div[data-testid="stFileUploader"]:hover { border-color: rgba(45,90,123,0.8); }

    .stButton > button { border-radius: 8px; font-weight: 600; letter-spacing: 0.3px; }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #1e3a5f, #2d5a7b); color: #e2e8f0;
        border: none; border-radius: 8px; font-weight: 600;
    }

    .sidebar-title { color: #a8d0e6; font-size: 1.3rem; font-weight: 700; letter-spacing: 1px; text-align: center; }
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
        "font_size": 40, "font_color": "#FFFFFF", "vertical_position": 50,
        "email_subject": "Your Certificate of Achievement",
        "email_body": "Hi {name},\n\nCongratulations! Please find your certificate attached.\n\nBest regards,\nAWSC Global",
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
                content = uploaded.read().decode("utf-8")
                result = parser.parse(content)
            st.session_state["attendees"] = result.records
            st.session_state["csv_errors"] = result.errors
            st.session_state["csv_file"] = uploaded
            st.session_state["generated_certs"] = []
            st.session_state["zip_bytes"] = None
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f'<div class="kpi"><div class="kpi-val" style="color:#10B981">{len(result.records)}</div><div class="kpi-lbl">Valid Attendees</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="kpi"><div class="kpi-val" style="color:#F59E0B">{len(result.errors)}</div><div class="kpi-lbl">Issues</div></div>', unsafe_allow_html=True)
            if result.errors:
                with st.expander("View issues"):
                    for err in result.errors:
                        st.text(f"Row {err.row_number} [{err.field}]: {err.message}")
            if result.records:
                st.markdown(bdg(f"{svg('check')} Attendees loaded", "ok"), unsafe_allow_html=True)
                with st.expander("Preview list"):
                    for i, r in enumerate(result.records[:10], 1):
                        st.text(f"  {i}. {r.name}  |  {r.email}")
                    if len(result.records) > 10:
                        st.caption(f"  ... +{len(result.records)-10} more")
        except ValueError as e:
            st.markdown(bdg(f"{svg('x-circle')} {e}", "err"), unsafe_allow_html=True)
    elif st.session_state["attendees"]:
        st.markdown(bdg(f"{svg('check')} {len(st.session_state['attendees'])} attendees loaded", "ok"), unsafe_allow_html=True)


def render_step_customize() -> None:
    step_hdr(3, "Customize Settings", "palette")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Typography**")
        fs = st.slider("Font Size (pt)", 10, 120, st.session_state["font_size"], key="fs2")
        st.session_state["font_size"] = fs
        fc = st.color_picker("Font Color", st.session_state["font_color"], key="fc2")
        st.session_state["font_color"] = fc
        vp = st.slider("Name Position (%)", 0, 100, st.session_state["vertical_position"], key="vp2")
        st.session_state["vertical_position"] = vp
    with c2:
        st.markdown("**Email Content**")
        subj = st.text_input("Subject", st.session_state["email_subject"], key="es2")
        st.session_state["email_subject"] = subj
        body = st.text_area("Body", st.session_state["email_body"], height=130, key="eb2")
        st.session_state["email_body"] = body
        st.markdown(bdg(f"{svg('zap')} Use {{name}} as placeholder", "info"), unsafe_allow_html=True)


def render_step_preview() -> None:
    step_hdr(4, "Preview Certificate", "eye")
    tb = st.session_state["template_bytes"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    if not tb or not att:
        st.markdown(bdg("Complete steps 1 and 2 to preview", "info"), unsafe_allow_html=True)
        return
    try:
        fc = FontConfiguration(
            font_path="assets/fonts/Arial.ttf",
            font_size=st.session_state["font_size"],
            font_color=FontConfiguration.parse_color(st.session_state["font_color"]),
        )
        gen = CertificateGenerator(template_bytes=tb, template_format=st.session_state["template_format"], font_config=fc)
        prev = gen.generate(att[0].name, vertical_position=st.session_state["vertical_position"], vertical_as_percentage=True)
        if prev.format in ("png","jpg"):
            st.image(prev.certificate, caption=f"Preview: {att[0].name}")
        elif prev.format == "pdf":
            doc = fitz.open(stream=prev.certificate, filetype="pdf")
            pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2,2))
            st.image(pix.tobytes("png"), caption=f"Preview: {att[0].name}")
            doc.close()
        st.markdown(bdg(f"{svg('check')} Looks good", "ok"), unsafe_allow_html=True)
    except Exception as e:
        st.markdown(bdg(f"{svg('x-circle')} Preview failed: {e}", "err"), unsafe_allow_html=True)


def render_step_send() -> None:
    step_hdr(5, "Generate and Deliver", "send")
    tb = st.session_state["template_bytes"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    subj = st.session_state["email_subject"].strip()
    body = st.session_state["email_body"].strip()
    sip = st.session_state["send_in_progress"]
    ready = all([tb, att, subj, body])
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
        c1, c2 = st.columns([2,1])
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
    elif st.session_state["zip_bytes"] and not st.session_state["send_results"]:
        st.markdown(bdg(f"{svg('check')} Certificates generated", "ok"), unsafe_allow_html=True)
        st.download_button("Download Certificates ZIP", data=st.session_state["zip_bytes"], file_name="certificates.zip", mime="application/zip", use_container_width=True)


def _generate_only() -> None:
    tb = st.session_state["template_bytes"]
    tf = st.session_state["template_format"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    bar = st.progress(0)
    status = st.empty()
    status.text("Generating...")
    try:
        fc = FontConfiguration(font_path="assets/fonts/Arial.ttf", font_size=st.session_state["font_size"], font_color=FontConfiguration.parse_color(st.session_state["font_color"]))
        gen = CertificateGenerator(template_bytes=tb, template_format=tf, font_config=fc)
        batch = gen.generate_batch([a.name for a in att], vertical_position=st.session_state["vertical_position"], vertical_as_percentage=True)
        st.session_state["generated_certs"] = batch.certificates
        bar.progress(0.8)
        st.session_state["zip_bytes"] = _make_zip(batch.certificates)
        bar.progress(1.0)
        status.text(f"Done. {len(batch.certificates)} certificates ready.")
    except Exception as e:
        st.error(f"Generation failed: {e}")


def _execute_send() -> None:
    st.session_state["send_in_progress"] = True
    tb = st.session_state["template_bytes"]
    tf = st.session_state["template_format"]
    att: List[AttendeeRecord] = st.session_state["attendees"]
    bar = st.progress(0)
    status = st.empty()
    status.text(f"Generating {len(att)} certificates...")
    try:
        fc = FontConfiguration(font_path="assets/fonts/Arial.ttf", font_size=st.session_state["font_size"], font_color=FontConfiguration.parse_color(st.session_state["font_color"]))
        gen = CertificateGenerator(template_bytes=tb, template_format=tf, font_config=fc)
        batch = gen.generate_batch([a.name for a in att], vertical_position=st.session_state["vertical_position"], vertical_as_percentage=True)
        st.session_state["generated_certs"] = batch.certificates
        bar.progress(0.3)
        status.text("Sending emails...")
        cert_bytes: List[bytes] = []
        for cert in batch.certificates:
            if cert.format in ("png","jpg"):
                buf = io.BytesIO()
                cert.certificate.save(buf, format="PNG" if cert.format == "png" else "JPEG")
                cert_bytes.append(buf.getvalue())
            else:
                cert_bytes.append(cert.certificate)
        ok_names = {c.attendee_name for c in batch.certificates}
        ok_att = [a for a in att if a.name in ok_names]
        tmpl = EmailTemplate(subject=st.session_state["email_subject"], body=st.session_state["email_body"])
        def prog(cur, tot):
            bar.progress(0.3 + (cur/tot)*0.65)
            status.text(f"Sending {cur}/{tot}...")
        sender = EmailSender()
        result = sender.send_bulk(recipients=ok_att, certificate_data=cert_bytes, certificate_format=tf, template=tmpl, progress_callback=prog)
        st.session_state["send_results"] = result
        st.session_state["zip_bytes"] = _make_zip(batch.certificates)
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
                cert.certificate.save(ib, format="PNG" if cert.format == "png" else "JPEG")
                zf.writestr(fn, ib.getvalue())
            else:
                zf.writestr(fn, cert.certificate)
    return buf.getvalue()


if __name__ == "__main__":
    main()
