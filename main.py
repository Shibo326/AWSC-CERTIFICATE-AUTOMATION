"""CertFlow - Cross-Platform Certificate Generator and Email Sender.

Enhanced UX: tab navigation, theme toggle, snackbar notifications,
data table for attendees, generate-only mode, responsive layout.
"""

import base64
import io
import os
import re
import threading
import zipfile
from pathlib import Path
from typing import List

import flet as ft

from utils.certificate_generator import CertificateGenerator
from utils.csv_parser import CSVParser
from utils.email_sender import EmailSender
from utils.font_config import FontConfiguration
from utils.models import AttendeeRecord, CertificateOutput, EmailTemplate

MAX_TEMPLATE_SIZE_MB = 10
MAX_CSV_SIZE_MB = 5
APP_VERSION = "2.1.0"


def main(page: ft.Page) -> None:
    """Entry point for the Flet application."""
    page.title = "CertFlow"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1100
    page.window.height = 850
    page.padding = 0

    # --- State ---
    state = {
        "template_bytes": None,
        "template_format": None,
        "template_filename": None,
        "attendees": [],
        "csv_errors": [],
        "font_size": 40,
        "font_color": "#000000",
        "vertical_position": 50,
        "email_subject": "Your Certificate of Achievement",
        "email_body": (
            "Hi {name},\n\n"
            "Congratulations! Please find your certificate attached.\n\n"
            "Best regards,\nThe Team"
        ),
        "generated_certs": [],
        "zip_bytes": None,
        "send_results": None,
    }

    # --- Helper: show snackbar ---
    def notify(msg: str, color: str = ft.Colors.GREEN) -> None:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color=ft.Colors.WHITE),
            bgcolor=color,
            duration=3000,
        )
        page.snack_bar.open = True
        page.update()

    # --- Helper: build font config from state ---
    def _build_font_config() -> FontConfiguration:
        return FontConfiguration(
            font_path="assets/fonts/Arial.ttf",
            font_size=state["font_size"],
            font_color=FontConfiguration.parse_color(state["font_color"]),
        )

    # --- Theme Toggle ---
    def toggle_theme(e) -> None:
        page.theme_mode = (
            ft.ThemeMode.DARK
            if page.theme_mode == ft.ThemeMode.LIGHT
            else ft.ThemeMode.LIGHT
        )
        theme_btn.icon = (
            ft.Icons.LIGHT_MODE
            if page.theme_mode == ft.ThemeMode.DARK
            else ft.Icons.DARK_MODE
        )
        page.update()

    theme_btn = ft.IconButton(
        icon=ft.Icons.DARK_MODE,
        tooltip="Toggle Dark/Light Mode",
        on_click=toggle_theme,
    )

    # --- Gmail Status Chip ---
    gmail_connected = EmailSender.check_credentials()
    gmail_chip = ft.Chip(
        label=ft.Text("Gmail Connected" if gmail_connected else "Gmail Not Set"),
        leading=ft.Icon(
            ft.Icons.CHECK_CIRCLE if gmail_connected else ft.Icons.WARNING,
            color=ft.Colors.GREEN if gmail_connected else ft.Colors.ORANGE,
            size=16,
        ),
        bgcolor=ft.Colors.GREEN_50 if gmail_connected else ft.Colors.ORANGE_50,
    )

    # ==================== STEP 1: TEMPLATE ====================
    template_preview = ft.Image(
        src_base64="", width=450, height=320,
        fit=ft.ImageFit.CONTAIN, visible=False,
        border_radius=ft.border_radius.all(8),
    )
    template_info = ft.Text("", size=12, color=ft.Colors.GREY_600)

    def on_template_picked(e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        file = e.files[0]
        file_path = file.path
        file_size = os.path.getsize(file_path)

        if file_size > MAX_TEMPLATE_SIZE_MB * 1024 * 1024:
            notify(f"File exceeds {MAX_TEMPLATE_SIZE_MB}MB limit", ft.Colors.RED)
            return

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        ext = file.name.rsplit(".", 1)[-1].lower()
        fmt = "jpg" if ext in ("jpg", "jpeg") else ext
        if fmt not in ("png", "jpg", "pdf"):
            notify("Unsupported format. Use PNG, JPG, or PDF.", ft.Colors.RED)
            return

        state["template_bytes"] = file_bytes
        state["template_format"] = fmt
        state["template_filename"] = file.name
        state["generated_certs"] = []
        state["zip_bytes"] = None

        if fmt in ("png", "jpg"):
            template_preview.src_base64 = base64.b64encode(file_bytes).decode()
            template_preview.visible = True
        elif fmt == "pdf":
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                png_bytes = pix.tobytes("png")
                doc.close()
                template_preview.src_base64 = base64.b64encode(png_bytes).decode()
                template_preview.visible = True
            except Exception:
                template_preview.visible = False

        size_str = (
            f"{file_size / 1024:.0f}KB"
            if file_size < 1024 * 1024
            else f"{file_size / 1024 / 1024:.1f}MB"
        )
        template_info.value = f"{file.name}  ({size_str}, {fmt.upper()})"
        notify("Template uploaded successfully")
        _update_tab_icons()
        page.update()

    template_picker = ft.FilePicker(on_result=on_template_picked)
    page.overlay.append(template_picker)
