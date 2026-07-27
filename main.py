"""CertFlow — Flet native app entry point.

Wires the step-based workflow UI with real components from parts/,
connects callbacks to update shared state, and provides settings
access via AppBar gear icon.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

import flet as ft

from parts.attendee_step import AttendeeStep
from parts.credentials_screen import CredentialsScreen
from parts.customize_step import CustomizeStep
from parts.generate_step import GenerateStep
from parts.queue_status import QueueStatusDisplay
from parts.review_step import ReviewStep
from parts.send_step import SendStep
from parts.template_step import TemplateStep
from utils.app_state_manager import AppStateManager
from utils.credential_store import CredentialStore
from utils.email_queue import EmailQueueManager
from utils.font_config import FontConfiguration, get_assets_root
from utils.font_manager import FontManager
from utils.models import AttendeeRecord, BatchResult, CertificateOutput, SendResult
from utils.platform_storage import PlatformStorage

logger = logging.getLogger(__name__)

# Step labels for the stepper navigation
STEP_LABELS = [
    "Template",
    "Attendees",
    "Customize",
    "Generate",
    "Review",
    "Send",
]


def main(page: ft.Page) -> None:
    """Application entry point — configure page and build UI."""
    page.title = "CertFlow — Certificate Generator"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.window.min_width = 800
    page.window.min_height = 600

    # ------------------------------------------------------------------
    # Shared state dict accessible by GenerateStep via page.certflow_state
    # ------------------------------------------------------------------
    certflow_state: Dict = {
        "template_bytes": None,
        "template_format": None,
        "template_filename": None,
        "attendees": [],
        "font_config": None,
        "vertical_position": 50,
        "certificates": [],
    }
    page.certflow_state = certflow_state  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------
    platform_storage = PlatformStorage()
    assets_dir = get_assets_root()
    data_dir = platform_storage.get_app_data_directory()

    font_manager = FontManager(assets_dir=assets_dir, data_dir=data_dir)
    state_manager = AppStateManager(page)
    credential_store = CredentialStore(page)
    queue_manager = EmailQueueManager(data_dir)

    # ------------------------------------------------------------------
    # Navigation state
    # ------------------------------------------------------------------
    current_step_index = 0

    # ------------------------------------------------------------------
    # Callbacks wired to step components
    # ------------------------------------------------------------------
    def on_template_loaded(
        template_data: bytes, template_format: str, template_filename: str
    ) -> None:
        """Store template in shared state and auto-advance to step 2."""
        certflow_state["template_bytes"] = template_data
        certflow_state["template_format"] = template_format
        certflow_state["template_filename"] = template_filename
        _go_to_step(1)

    def on_attendees_loaded(attendees: List[AttendeeRecord]) -> None:
        """Store attendees in shared state and auto-advance to step 3."""
        certflow_state["attendees"] = attendees
        _go_to_step(2)

    def on_settings_changed(settings: Dict) -> None:
        """Update shared state with customization settings and auto-save."""
        font_path = settings.get("font_path", "")
        font_size = settings.get("font_size", 40)
        font_color_hex = settings.get("font_color", "#000000")
        vertical_position = settings.get("vertical_position", 50)

        font_color_rgb = FontConfiguration.parse_color(font_color_hex)
        font_config = FontConfiguration(
            font_path=font_path,
            font_size=font_size,
            font_color=font_color_rgb,
        )
        certflow_state["font_config"] = font_config
        certflow_state["vertical_position"] = vertical_position

        # Auto-save settings via AppStateManager
        page.run_task(_save_settings, settings)

    async def _save_settings(settings: Dict) -> None:
        """Persist customization settings."""
        try:
            await state_manager.save("font_family", settings.get("font_name", "Arial"))
            await state_manager.save("font_size", str(settings.get("font_size", 40)))
            await state_manager.save("font_color", settings.get("font_color", "#000000"))
            await state_manager.save(
                "vertical_position", str(settings.get("vertical_position", 50))
            )
        except Exception as exc:
            logger.warning("Failed to auto-save settings: %s", exc)

    def on_generation_complete(result: BatchResult) -> None:
        """Store generated certificates and auto-advance to step 5."""
        certflow_state["certificates"] = result.certificates
        # Set data on the review and send steps
        review_step.set_certificates(
            certificates=result.certificates,
            template_bytes=certflow_state["template_bytes"],
            template_format=certflow_state["template_format"],
            font_config=certflow_state.get("font_config"),
            vertical_position=certflow_state.get("vertical_position", 50),
        )
        send_step.set_data(
            certificates=result.certificates,
            attendees=certflow_state["attendees"],
        )
        _go_to_step(4)

    def on_send_complete(result: SendResult) -> None:
        """Show summary snackbar after sending completes."""
        sent = result.success_count
        failed = result.failure_count
        msg = f"Sending complete: {sent} sent, {failed} failed."
        color = ft.Colors.GREEN if failed == 0 else ft.Colors.ORANGE
        page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color=ft.Colors.WHITE),
            bgcolor=color,
            duration=5000,
        )
        page.snack_bar.open = True
        # Refresh queue status
        page.run_task(queue_status_display.refresh_status)
        page.update()

    # ------------------------------------------------------------------
    # Step component instances
    # ------------------------------------------------------------------
    template_step = TemplateStep(page=page, on_template_loaded=on_template_loaded)
    attendee_step = AttendeeStep(page=page, on_attendees_loaded=on_attendees_loaded)
    customize_step = CustomizeStep(
        page=page,
        font_manager=font_manager,
        on_settings_changed=on_settings_changed,
    )
    generate_step = GenerateStep(page=page, on_generation_complete=on_generation_complete)
    review_step = ReviewStep(page=page)
    send_step = SendStep(page=page, on_send_complete=on_send_complete)

    # Build control trees from each component
    step_controls = [
        template_step.build(),
        attendee_step.build(),
        customize_step.build(),
        generate_step.build(),
        review_step.build(),
        send_step.build(),
    ]

    # ------------------------------------------------------------------
    # Queue status display (shown in appbar area when pending > 0)
    # ------------------------------------------------------------------
    queue_status_display = QueueStatusDisplay(page=page, queue_manager=queue_manager)

    # ------------------------------------------------------------------
    # Step content container
    # ------------------------------------------------------------------
    step_content = ft.Container(
        content=step_controls[0],
        padding=ft.Padding(left=16, top=16, right=16, bottom=16),
        expand=True,
    )

    # ------------------------------------------------------------------
    # Stepper navigation rail (left sidebar with step labels)
    # ------------------------------------------------------------------
    def _build_step_buttons() -> List[ft.Control]:
        """Build clickable step label buttons for the sidebar."""
        buttons = []
        for i, label in enumerate(STEP_LABELS):
            buttons.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.CircleAvatar(
                                content=ft.Text(str(i + 1), size=12),
                                radius=14,
                                bgcolor=(
                                    ft.Colors.TEAL
                                    if i == current_step_index
                                    else ft.Colors.GREY_400
                                ),
                                foreground_color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                label,
                                size=14,
                                weight=(
                                    ft.FontWeight.W_600
                                    if i == current_step_index
                                    else ft.FontWeight.W_400
                                ),
                                color=(
                                    ft.Colors.TEAL
                                    if i == current_step_index
                                    else ft.Colors.GREY_700
                                ),
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(left=12, top=10, right=12, bottom=10),
                    border_radius=8,
                    bgcolor=(
                        ft.Colors.TEAL_50
                        if i == current_step_index
                        else None
                    ),
                    on_click=lambda e, idx=i: _on_step_click(idx),
                    ink=True,
                )
            )
        return buttons

    step_nav_column = ft.Column(
        controls=_build_step_buttons(),
        spacing=4,
        width=180,
    )

    # ------------------------------------------------------------------
    # Navigation buttons (Previous / Next)
    # ------------------------------------------------------------------
    prev_btn = ft.ElevatedButton(
        "Previous",
        icon=ft.Icons.ARROW_BACK,
        on_click=lambda e: _go_to_step(current_step_index - 1),
        visible=False,
    )

    next_btn = ft.ElevatedButton(
        "Next",
        icon=ft.Icons.ARROW_FORWARD,
        on_click=lambda e: _go_to_step(current_step_index + 1),
        disabled=True,
    )

    nav_row = ft.Row(
        controls=[prev_btn, ft.Container(expand=True), next_btn],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # ------------------------------------------------------------------
    # Step validation — disable Next when prerequisites not met
    # ------------------------------------------------------------------
    def _is_step_complete(step_index: int) -> bool:
        """Check whether a step's prerequisites are satisfied."""
        if step_index == 0:
            return certflow_state["template_bytes"] is not None
        if step_index == 1:
            return len(certflow_state["attendees"]) > 0
        if step_index == 2:
            # Customize is always "complete" (has defaults)
            return True
        if step_index == 3:
            return len(certflow_state.get("certificates", [])) > 0
        if step_index == 4:
            return len(certflow_state.get("certificates", [])) > 0
        # Last step — no next
        return False

    def _update_nav_buttons() -> None:
        """Update Previous/Next button visibility and disabled state."""
        nonlocal current_step_index
        prev_btn.visible = current_step_index > 0
        next_btn.visible = current_step_index < len(STEP_LABELS) - 1
        next_btn.disabled = not _is_step_complete(current_step_index)

    # ------------------------------------------------------------------
    # Navigation logic
    # ------------------------------------------------------------------
    def _go_to_step(index: int) -> None:
        """Navigate to the specified step index."""
        nonlocal current_step_index
        if index < 0 or index >= len(STEP_LABELS):
            return
        current_step_index = index
        step_content.content = step_controls[current_step_index]
        step_nav_column.controls = _build_step_buttons()
        _update_nav_buttons()
        page.update()

    def _on_step_click(index: int) -> None:
        """Handle sidebar step click — allow navigation to completed steps."""
        if index <= current_step_index or _is_step_complete(index - 1):
            _go_to_step(index)

    # ------------------------------------------------------------------
    # Credentials dialog (gear icon in AppBar)
    # ------------------------------------------------------------------
    def _open_credentials_dialog(e: ft.ControlEvent) -> None:
        """Open the credentials screen as a dialog."""
        creds_screen = CredentialsScreen(
            page=page,
            credential_store=credential_store,
            on_credentials_saved=lambda: _close_dialog(),
        )
        creds_control = creds_screen.build()
        creds_screen.initialize()
        dialog = ft.AlertDialog(
            title=ft.Text("Email Credentials"),
            content=ft.Container(
                content=creds_control,
                width=420,
                height=440,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda e: _close_dialog()),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

        def _close_dialog() -> None:
            dialog.open = False
            page.update()

    # ------------------------------------------------------------------
    # AppBar with gear icon and queue status badge
    # ------------------------------------------------------------------
    queue_badge = ft.Badge(
        content=ft.Icon(ft.Icons.OUTBOX, color=ft.Colors.WHITE, size=20),
        text="0",
        small_size=10,
    )

    queue_badge_container = ft.Container(
        content=queue_badge,
        visible=False,
        tooltip="Emails in queue",
        on_click=lambda e: _show_queue_panel(),
    )

    app_bar = ft.AppBar(
        title=ft.Text("CertFlow", weight=ft.FontWeight.W_600),
        center_title=False,
        bgcolor=ft.Colors.TEAL,
        color=ft.Colors.WHITE,
        actions=[
            queue_badge_container,
            ft.IconButton(
                icon=ft.Icons.SETTINGS,
                icon_color=ft.Colors.WHITE,
                tooltip="Email Credentials",
                on_click=_open_credentials_dialog,
            ),
        ],
    )

    page.appbar = app_bar

    # ------------------------------------------------------------------
    # Queue panel (shows full QueueStatusDisplay)
    # ------------------------------------------------------------------
    def _show_queue_panel() -> None:
        """Show queue status as a dialog."""
        queue_control = queue_status_display.build()
        dialog = ft.AlertDialog(
            title=ft.Text("Email Queue"),
            content=ft.Container(
                content=queue_control,
                width=380,
                height=200,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda e: _close_queue()),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

        def _close_queue() -> None:
            dialog.open = False
            page.update()

    # ------------------------------------------------------------------
    # Main layout: sidebar + content area
    # ------------------------------------------------------------------
    main_layout = ft.Row(
        controls=[
            ft.Container(
                content=step_nav_column,
                padding=ft.Padding(left=0, top=8, right=8, bottom=0),
                border=ft.Border(right=ft.BorderSide(1, ft.Colors.GREY_300)),
            ),
            ft.Column(
                controls=[
                    step_content,
                    ft.Divider(height=1),
                    nav_row,
                ],
                expand=True,
                spacing=8,
            ),
        ],
        expand=True,
        spacing=0,
    )

    page.add(main_layout)

    # ------------------------------------------------------------------
    # Initialize: restore persisted state + refresh queue status
    # ------------------------------------------------------------------
    async def _initialize() -> None:
        """Restore persisted state and check queue on launch."""
        # Restore persisted settings
        try:
            persisted, warnings = await state_manager.restore_session()
            if persisted.font_family:
                customize_step.set_settings(
                    font_name=persisted.font_family,
                    font_size=persisted.font_size,
                    font_color=persisted.font_color,
                    vertical_position=persisted.vertical_position,
                )
                # Also populate certflow_state with restored font config
                font_color_rgb = FontConfiguration.parse_color(persisted.font_color)
                try:
                    font_path = font_manager.resolve_font_path(persisted.font_family)
                except ValueError:
                    font_path = ""
                certflow_state["font_config"] = FontConfiguration(
                    font_path=font_path,
                    font_size=persisted.font_size,
                    font_color=font_color_rgb,
                )
                certflow_state["vertical_position"] = persisted.vertical_position

            for warning_msg in warnings:
                logger.warning(warning_msg)
        except Exception as exc:
            logger.warning("Failed to restore session state: %s", exc)

        # Check queue status and show badge if pending > 0
        try:
            status = await queue_manager.get_status()
            if status.pending_count > 0:
                queue_badge.text = str(status.pending_count)
                queue_badge_container.visible = True
                page.update()
        except Exception as exc:
            logger.warning("Failed to check queue status: %s", exc)

    page.run_task(_initialize)

    # Initial nav button state
    _update_nav_buttons()
    page.update()


if __name__ == "__main__":
    ft.app(target=main)  # ft.app delegates to ft.run internally  # Use ft.app for compatibility; ft.run() for Flet 0.80+
