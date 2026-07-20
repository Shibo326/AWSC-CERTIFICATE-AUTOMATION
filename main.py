"""CertFlow — Cross-Platform Certificate Generator & Email Sender.

Workflow: Upload Template → Upload CSV → Customize → Generate → Review/Edit → Send
Builds to: Windows (.exe), macOS (.app), Android (.apk), iOS (.ipa)
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
APP_VERSION = "2.2.0"


def main(page: ft.Page) -> None:
    """Entry point for the Flet application."""
    page.title = "CertFlow — Certificate Generator"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1100
    page.window.height = 900
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

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
        "current_preview_idx": 0,
    }

    # --- Helpers ---
    def notify(msg: str, color: str = ft.Colors.GREEN) -> None:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color=ft.Colors.WHITE),
            bgcolor=color, duration=3000,
        )
        page.snack_bar.open = True
        page.update()

    def _build_font_config() -> FontConfiguration:
        return FontConfiguration(
            font_path="assets/fonts/Arial.ttf",
            font_size=state["font_size"],
            font_color=FontConfiguration.parse_color(state["font_color"]),
        )

    def _cert_to_base64(cert: CertificateOutput) -> str:
        """Convert a certificate to base64 PNG for display."""
        if cert.format in ("png", "jpg"):
            buf = io.BytesIO()
            img_fmt = "PNG" if cert.format == "png" else "JPEG"
            cert.certificate.save(buf, format=img_fmt)
            return base64.b64encode(buf.getvalue()).decode()
        elif cert.format == "pdf":
            import fitz
            doc = fitz.open(stream=cert.certificate, filetype="pdf")
            pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            result = base64.b64encode(pix.tobytes("png")).decode()
            doc.close()
            return result
        return ""

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
        icon=ft.Icons.DARK_MODE, tooltip="Toggle theme", on_click=toggle_theme,
    )

    # --- Gmail Status ---
    gmail_ok = EmailSender.check_credentials()
    gmail_chip = ft.Chip(
        label=ft.Text("Gmail OK" if gmail_ok else "Gmail Not Set"),
        leading=ft.Icon(
            ft.Icons.CHECK_CIRCLE if gmail_ok else ft.Icons.WARNING,
            color=ft.Colors.GREEN if gmail_ok else ft.Colors.ORANGE, size=16,
        ),
        bgcolor=ft.Colors.GREEN_50 if gmail_ok else ft.Colors.ORANGE_50,
    )

    # ==================== STEP 1: TEMPLATE ====================
    template_preview = ft.Image(
        src_base64="", width=400, height=280,
        fit=ft.ImageFit.CONTAIN, visible=False,
    )
    template_status = ft.Text("No template uploaded", size=13, color=ft.Colors.GREY)

    def on_template_picked(e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        file = e.files[0]
        file_path = file.path
        if not file_path:
            notify("File picker error", ft.Colors.RED)
            return

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
                template_preview.src_base64 = base64.b64encode(
                    pix.tobytes("png")
                ).decode()
                doc.close()
                template_preview.visible = True
            except Exception:
                template_preview.visible = False

        template_status.value = f"✅ {file.name} ({file_size // 1024}KB)"
        template_status.color = ft.Colors.GREEN
        notify("Template uploaded")
        page.update()

    template_picker = ft.FilePicker(on_result=on_template_picked)
    page.overlay.append(template_picker)

    # ==================== STEP 2: CSV ====================
    csv_status = ft.Text("No attendees loaded", size=13, color=ft.Colors.GREY)
    csv_details = ft.Column(visible=False, spacing=2)

    def on_csv_picked(e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        file = e.files[0]
        file_path = file.path
        if not file_path:
            notify("File picker error", ft.Colors.RED)
            return

        file_size = os.path.getsize(file_path)
        if file_size > MAX_CSV_SIZE_MB * 1024 * 1024:
            notify(f"CSV exceeds {MAX_CSV_SIZE_MB}MB limit", ft.Colors.RED)
            return

        try:
            ext = file.name.rsplit(".", 1)[-1].lower()
            parser = CSVParser()
            if ext in ("xlsx", "xls"):
                with open(file_path, "rb") as f:
                    result = parser.parse_xlsx(f.read())
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    result = parser.parse(f.read())

            state["attendees"] = result.records
            state["csv_errors"] = result.errors
            state["generated_certs"] = []
            state["zip_bytes"] = None

            csv_status.value = f"✅ {len(result.records)} valid attendees"
            csv_status.color = ft.Colors.GREEN

            csv_details.controls.clear()
            if result.errors:
                csv_details.controls.append(ft.Text(
                    f"⚠️ {len(result.errors)} issues",
                    color=ft.Colors.ORANGE, size=12,
                ))
            for i, rec in enumerate(result.records[:5], 1):
                csv_details.controls.append(
                    ft.Text(f"  {i}. {rec.name} — {rec.email}", size=11)
                )
            if len(result.records) > 5:
                csv_details.controls.append(
                    ft.Text(f"  ... +{len(result.records) - 5} more", size=11)
                )
            csv_details.visible = True
            notify(f"Loaded {len(result.records)} attendees")
        except ValueError as ex:
            csv_status.value = f"❌ {ex}"
            csv_status.color = ft.Colors.RED
            notify(str(ex), ft.Colors.RED)
        page.update()

    csv_picker = ft.FilePicker(on_result=on_csv_picked)
    page.overlay.append(csv_picker)

    # ==================== STEP 3: CUSTOMIZE ====================
    font_size_slider = ft.Slider(
        min=10, max=120, value=state["font_size"],
        divisions=110, label="{value}pt", width=280,
    )
    font_color_field = ft.TextField(
        value=state["font_color"], label="Font Color (hex)", width=140,
    )
    vertical_slider = ft.Slider(
        min=0, max=100, value=state["vertical_position"],
        divisions=100, label="{value}%", width=280,
    )
    email_subject_field = ft.TextField(
        value=state["email_subject"], label="Email Subject", width=380,
    )
    email_body_field = ft.TextField(
        value=state["email_body"], label="Email Body",
        multiline=True, min_lines=4, max_lines=8, width=380,
    )

    def sync_settings() -> None:
        state["font_size"] = int(font_size_slider.value)
        color_val = font_color_field.value.strip().lstrip("#")
        state["font_color"] = f"#{color_val}" if color_val else "#000000"
        state["vertical_position"] = int(vertical_slider.value)
        state["email_subject"] = email_subject_field.value
        state["email_body"] = email_body_field.value

    # ==================== STEP 4: GENERATE & REVIEW ====================
    gen_progress = ft.ProgressBar(width=500, visible=False)
    gen_status = ft.Text("", size=13)

    # Certificate gallery
    gallery_container = ft.Container(visible=False)
    gallery_image = ft.Image(src_base64="", width=550, height=400,
                             fit=ft.ImageFit.CONTAIN)
    gallery_name_label = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
    gallery_counter = ft.Text("", size=12, color=ft.Colors.GREY_600)

    def _show_cert(idx: int) -> None:
        certs = state["generated_certs"]
        if not certs or idx < 0 or idx >= len(certs):
            return
        state["current_preview_idx"] = idx
        cert = certs[idx]
        gallery_image.src_base64 = _cert_to_base64(cert)
        gallery_name_label.value = cert.attendee_name
        gallery_counter.value = f"{idx + 1} / {len(certs)}"
        page.update()

    def on_prev(e) -> None:
        idx = state["current_preview_idx"] - 1
        if idx >= 0:
            _show_cert(idx)

    def on_next(e) -> None:
        idx = state["current_preview_idx"] + 1
        if idx < len(state["generated_certs"]):
            _show_cert(idx)

    def on_edit_name(e) -> None:
        idx = state["current_preview_idx"]
        certs = state["generated_certs"]
        if not certs or idx >= len(certs):
            return

        current_name = certs[idx].attendee_name
        name_field = ft.TextField(
            value=current_name, label="Attendee Name",
            width=300, autofocus=True,
        )

        def save_name(ev) -> None:
            new_name = name_field.value.strip()
            if not new_name:
                notify("Name cannot be empty", ft.Colors.ORANGE)
                return
            try:
                generator = CertificateGenerator(
                    template_bytes=state["template_bytes"],
                    template_format=state["template_format"],
                    font_config=_build_font_config(),
                )
                new_cert = generator.generate(
                    attendee_name=new_name,
                    vertical_position=state["vertical_position"],
                    vertical_as_percentage=True,
                )
                generator.cleanup()

                state["generated_certs"][idx] = new_cert
                if idx < len(state["attendees"]):
                    old_rec = state["attendees"][idx]
                    state["attendees"][idx] = AttendeeRecord(
                        name=new_name, email=old_rec.email,
                    )

                _show_cert(idx)
                edit_dlg.open = False
                page.update()
                notify(f"Updated: {current_name} → {new_name}")
            except Exception as ex:
                notify(f"Regenerate failed: {ex}", ft.Colors.RED)

        def cancel_edit(ev) -> None:
            edit_dlg.open = False
            page.update()

        edit_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Name"),
            content=ft.Column([
                ft.Text("Fix the name and regenerate this certificate:", size=13),
                name_field,
            ], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_edit),
                ft.ElevatedButton("Save & Regenerate", on_click=save_name),
            ],
        )
        page.overlay.append(edit_dlg)
        edit_dlg.open = True
        page.update()

    gallery_nav = ft.Row([
        ft.IconButton(ft.Icons.ARROW_BACK, on_click=on_prev, tooltip="Previous"),
        gallery_counter,
        ft.IconButton(ft.Icons.ARROW_FORWARD, on_click=on_next, tooltip="Next"),
        ft.Container(width=20),
        ft.ElevatedButton("✏️ Edit Name", icon=ft.Icons.EDIT,
                          on_click=on_edit_name),
    ], alignment=ft.MainAxisAlignment.CENTER)

    gallery_section = ft.Column([
        ft.Container(height=10),
        ft.Text("📋 Review Certificates", size=15, weight=ft.FontWeight.W_500),
        ft.Text("Use arrows to browse. Click Edit to fix typos.",
                size=12, color=ft.Colors.GREY_600),
        gallery_nav,
        gallery_name_label,
        gallery_image,
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
    gallery_container.content = gallery_section

    def on_generate(e) -> None:
        sync_settings()
        if not state["template_bytes"]:
            notify("Upload a template first", ft.Colors.ORANGE)
            return
        if not state["attendees"]:
            notify("Upload attendees first", ft.Colors.ORANGE)
            return

        gen_progress.visible = True
        gen_progress.value = 0
        gen_status.value = "Generating..."
        gallery_container.visible = False
        page.update()

        def task() -> None:
            try:
                generator = CertificateGenerator(
                    template_bytes=state["template_bytes"],
                    template_format=state["template_format"],
                    font_config=_build_font_config(),
                )
                batch = generator.generate_batch(
                    attendee_names=[a.name for a in state["attendees"]],
                    vertical_position=state["vertical_position"],
                    vertical_as_percentage=True,
                )
                generator.cleanup()
                state["generated_certs"] = batch.certificates

                gen_progress.value = 1.0
                msg = f"✅ {len(batch.certificates)} certificates generated"
                if batch.errors:
                    msg += f" ({len(batch.errors)} failed)"
                gen_status.value = msg

                if batch.certificates:
                    gallery_container.visible = True
                    _show_cert(0)

                notify(f"Done! {len(batch.certificates)} ready to review")
                page.update()
            except Exception as ex:
                gen_status.value = f"❌ {ex}"
                gen_progress.visible = False
                notify(str(ex), ft.Colors.RED)
                page.update()

        threading.Thread(target=task, daemon=True).start()

    # ==================== STEP 5: DOWNLOAD & SEND ====================
    send_progress = ft.ProgressBar(width=500, visible=False)
    send_status = ft.Text("", size=13)
    results_col = ft.Column(visible=False, spacing=4)

    def on_download(e) -> None:
        if not state["generated_certs"]:
            notify("Generate certificates first (Step 4)", ft.Colors.ORANGE)
            return
        state["zip_bytes"] = _generate_zip(state["generated_certs"])
        save_path = str(Path.home() / "Downloads" / "certificates.zip")
        with open(save_path, "wb") as f:
            f.write(state["zip_bytes"])
        notify(f"Saved to {save_path}")

    def on_send(e) -> None:
        sync_settings()
        if not state["generated_certs"]:
            notify("Generate certificates first (Step 4)", ft.Colors.ORANGE)
            return
        if not state["email_subject"].strip() or not state["email_body"].strip():
            notify("Email subject and body required", ft.Colors.ORANGE)
            return

        def confirm_yes(ev) -> None:
            dlg.open = False
            page.update()
            _do_send()

        def confirm_no(ev) -> None:
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm Send"),
            content=ft.Text(
                f"Send {len(state['generated_certs'])} certificates via email?\n"
                "This cannot be undone."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=confirm_no),
                ft.ElevatedButton("Yes, Send All", on_click=confirm_yes),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _do_send() -> None:
        send_progress.visible = True
        send_progress.value = 0
        send_status.value = "Sending..."
        results_col.visible = False
        page.update()

        def task() -> None:
            try:
                certs = state["generated_certs"]
                cert_bytes_list: List[bytes] = []
                for cert in certs:
                    if cert.format in ("png", "jpg"):
                        buf = io.BytesIO()
                        img_fmt = "PNG" if cert.format == "png" else "JPEG"
                        cert.certificate.save(buf, format=img_fmt)
                        cert_bytes_list.append(buf.getvalue())
                    else:
                        cert_bytes_list.append(cert.certificate)

                recipients = []
                for i, cert in enumerate(certs):
                    if i < len(state["attendees"]):
                        recipients.append(AttendeeRecord(
                            name=cert.attendee_name,
                            email=state["attendees"][i].email,
                        ))

                template = EmailTemplate(
                    subject=state["email_subject"],
                    body=state["email_body"],
                )

                def on_progress(current: int, total: int) -> None:
                    send_progress.value = current / total
                    send_status.value = f"Sending {current}/{total}..."
                    page.update()

                sender = EmailSender()
                result = sender.send_bulk(
                    recipients=recipients,
                    certificate_data=cert_bytes_list,
                    certificate_format=state["template_format"],
                    template=template,
                    progress_callback=on_progress,
                )

                state["send_results"] = result
                send_progress.value = 1.0
                send_status.value = "✅ Complete!"

                results_col.controls.clear()
                results_col.controls.append(ft.Text(
                    f"✅ Sent: {result.success_count}  |  "
                    f"❌ Failed: {result.failure_count}",
                    size=14, weight=ft.FontWeight.BOLD,
                ))
                for fail in result.failures[:10]:
                    results_col.controls.append(ft.Text(
                        f"  ❌ {fail.attendee_name}: {fail.error_message}",
                        size=11, color=ft.Colors.RED_700,
                    ))
                results_col.visible = True
                page.update()
            except Exception as ex:
                send_status.value = f"❌ {ex}"
                send_progress.visible = False
                notify(str(ex), ft.Colors.RED)
                page.update()

        threading.Thread(target=task, daemon=True).start()

    # ==================== PAGE LAYOUT ====================
    page.add(
        ft.Row([
            ft.Icon(ft.Icons.WORKSPACE_PREMIUM, size=30, color=ft.Colors.BLUE),
            ft.Text("CertFlow", size=26, weight=ft.FontWeight.BOLD),
            ft.Text(f"v{APP_VERSION}", size=11, color=ft.Colors.GREY),
            ft.Container(expand=True),
            gmail_chip,
            theme_btn,
        ]),
        ft.Divider(height=1),

        # Step 1
        ft.Text("1. Upload Certificate Template",
                size=17, weight=ft.FontWeight.W_600),
        ft.Row([
            ft.ElevatedButton("Choose Template", icon=ft.Icons.UPLOAD_FILE,
                              on_click=lambda _: template_picker.pick_files(
                                  allowed_extensions=["png", "jpg", "jpeg", "pdf"],
                                  dialog_title="Select Template")),
            template_status,
        ]),
        template_preview,
        ft.Divider(height=1),

        # Step 2
        ft.Text("2. Upload Attendees (CSV/XLSX)",
                size=17, weight=ft.FontWeight.W_600),
        ft.Row([
            ft.ElevatedButton("Choose File", icon=ft.Icons.TABLE_CHART,
                              on_click=lambda _: csv_picker.pick_files(
                                  allowed_extensions=["csv", "xlsx", "xls"],
                                  dialog_title="Select Attendee File")),
            csv_status,
        ]),
        csv_details,
        ft.Divider(height=1),

        # Step 3
        ft.Text("3. Customize", size=17, weight=ft.FontWeight.W_600),
        ft.ResponsiveRow([
            ft.Column([
                ft.Text("Font & Position", size=13, weight=ft.FontWeight.W_500),
                ft.Row([ft.Text("Size:", size=12), font_size_slider]),
                font_color_field,
                ft.Row([ft.Text("Y Position:", size=12), vertical_slider]),
            ], col={"sm": 12, "md": 6}),
            ft.Column([
                ft.Text("Email Template", size=13, weight=ft.FontWeight.W_500),
                email_subject_field,
                email_body_field,
                ft.Text("Use {name} as placeholder", size=11, italic=True,
                        color=ft.Colors.GREY_600),
            ], col={"sm": 12, "md": 6}),
        ]),
        ft.Divider(height=1),

        # Step 4
        ft.Text("4. Generate & Review", size=17, weight=ft.FontWeight.W_600),
        ft.Text("Generate all certificates, browse them, and fix names if needed.",
                size=12, color=ft.Colors.GREY_700),
        ft.ElevatedButton("🔨 Generate All Certificates",
                          icon=ft.Icons.AUTO_AWESOME, on_click=on_generate,
                          style=ft.ButtonStyle(bgcolor=ft.Colors.TEAL,
                                              color=ft.Colors.WHITE)),
        gen_progress,
        gen_status,
        gallery_container,
        ft.Divider(height=1),

        # Step 5
        ft.Text("5. Download / Send", size=17, weight=ft.FontWeight.W_600),
        ft.Row([
            ft.ElevatedButton("📥 Download ZIP", icon=ft.Icons.DOWNLOAD,
                              on_click=on_download),
            ft.ElevatedButton("📧 Send via Email", icon=ft.Icons.SEND,
                              color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE,
                              on_click=on_send),
        ]),
        send_progress,
        send_status,
        results_col,

        ft.Container(height=30),
        ft.Text("CertFlow — Windows | macOS | Android | iOS",
                size=11, color=ft.Colors.GREY_400,
                text_align=ft.TextAlign.CENTER),
    )


def _generate_zip(certificates: List[CertificateOutput]) -> bytes:
    """Package all generated certificates into a ZIP archive."""
    if not certificates:
        return b""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for cert in certificates:
            safe_name = re.sub(r"[^\w\s-]", "", cert.attendee_name)
            safe_name = safe_name.replace(" ", "_")
            filename = f"{safe_name}.{cert.format}"
            if cert.format in ("png", "jpg"):
                img_buf = io.BytesIO()
                img_format = "PNG" if cert.format == "png" else "JPEG"
                cert.certificate.save(img_buf, format=img_format)
                zf.writestr(filename, img_buf.getvalue())
            else:
                zf.writestr(filename, cert.certificate)
    return buffer.getvalue()


if __name__ == "__main__":
    ft.app(target=main)
