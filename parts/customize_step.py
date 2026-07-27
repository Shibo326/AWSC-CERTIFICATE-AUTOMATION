"""Customization step UI component for CertFlow native app.

Provides font selection, font size, font color, vertical position controls,
and a font import button. Calls on_settings_changed callback whenever any
setting is modified, enabling live preview updates within 2 seconds.

Requirements: 11.3, 11.4, 5.4
"""

import re
from typing import Callable, Dict, Optional

import flet as ft

from utils.font_manager import FontManager


# Hex color validation pattern: # followed by exactly 6 hex digits.
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class CustomizeStep:
    """Customization controls for certificate text rendering.

    Provides:
    - Font selection dropdown listing all available fonts (bundled + imported)
    - Font size slider (10-120 points, default 40)
    - Font color text field accepting hex values (default #000000)
    - Vertical position slider (0-100%, default 50)
    - Font import button for adding .ttf files via file picker

    Args:
        page: The Flet page instance.
        font_manager: FontManager instance for font discovery and import.
        on_settings_changed: Optional callback invoked with the current
            settings dict whenever any setting changes.
    """

    def __init__(
        self,
        page: ft.Page,
        font_manager: FontManager,
        on_settings_changed: Optional[Callable[[Dict], None]] = None,
    ) -> None:
        self.page = page
        self.font_manager = font_manager
        self.on_settings_changed = on_settings_changed

        # Settings state with defaults
        self.selected_font: str = "Arial"
        self.font_size: int = 40
        self.font_color: str = "#000000"
        self.vertical_position: int = 50

    def _get_settings(self) -> Dict:
        """Return the current settings as a dictionary.

        Returns:
            Dict with keys: font_name, font_size, font_color,
            vertical_position, font_path.
        """
        try:
            font_path = self.font_manager.resolve_font_path(self.selected_font)
        except ValueError:
            font_path = ""

        return {
            "font_name": self.selected_font,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "vertical_position": self.vertical_position,
            "font_path": font_path,
        }

    def _notify_change(self) -> None:
        """Invoke the on_settings_changed callback with current settings."""
        if self.on_settings_changed:
            self.on_settings_changed(self._get_settings())

    def _build_font_options(self) -> list:
        """Build dropdown options from all available fonts.

        Returns:
            List of ft.dropdown.Option for each available font.
        """
        fonts = self.font_manager.get_available_fonts()
        options = []
        for font_info in fonts:
            options.append(
                ft.dropdown.Option(
                    key=font_info.name,
                    text=font_info.name,
                )
            )
        return options

    def _on_font_changed(self, e: ft.ControlEvent) -> None:
        """Handle font selection dropdown change."""
        self.selected_font = e.control.value
        self._notify_change()

    def _on_font_size_changed(self, e: ft.ControlEvent) -> None:
        """Handle font size slider change."""
        self.font_size = int(e.control.value)
        self._size_label.value = f"{self.font_size} pt"
        self._size_label.update()
        self._notify_change()

    def _on_color_changed(self, e: ft.ControlEvent) -> None:
        """Handle font color text field change (on blur or submit)."""
        raw_value = e.control.value.strip()

        # Ensure the value starts with #
        if not raw_value.startswith("#"):
            raw_value = f"#{raw_value}"

        # Validate hex color format
        if _HEX_COLOR_PATTERN.match(raw_value):
            self.font_color = raw_value
            self._color_field.error_text = None
            self._color_preview.bgcolor = raw_value
            self._color_preview.update()
            self._notify_change()
        else:
            self._color_field.error_text = "Invalid hex (e.g. #FF5733)"

        self._color_field.update()

    def _on_position_changed(self, e: ft.ControlEvent) -> None:
        """Handle vertical position slider change."""
        self.vertical_position = int(e.control.value)
        self._position_label.value = f"{self.vertical_position}%"
        self._position_label.update()
        self._notify_change()

    def _on_import_font_result(self, e: ft.FilePickerResultEvent) -> None:
        """Handle font import file picker result."""
        if not e.files:
            return

        file = e.files[0]
        file_path = file.path
        if not file_path:
            self._show_import_error("Could not read the selected file.")
            return

        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except OSError as ex:
            self._show_import_error(f"Failed to read file: {ex}")
            return

        result = self.font_manager.import_font(file_path, file_bytes)

        if result.success:
            # Refresh dropdown options
            self._font_dropdown.options = self._build_font_options()
            self._font_dropdown.value = result.font_name
            self.selected_font = result.font_name
            self._font_dropdown.update()
            self._show_import_success(f"Imported: {result.font_name}")
            self._notify_change()
        else:
            self._show_import_error(result.error_message)

    def _show_import_error(self, message: str) -> None:
        """Display an error message for font import failures."""
        self._import_status.value = f"❌ {message}"
        self._import_status.color = ft.Colors.RED
        self._import_status.visible = True
        self._import_status.update()

    def _show_import_success(self, message: str) -> None:
        """Display a success message for font import."""
        self._import_status.value = f"✅ {message}"
        self._import_status.color = ft.Colors.GREEN
        self._import_status.visible = True
        self._import_status.update()

    def refresh_fonts(self) -> None:
        """Refresh the font dropdown options from FontManager.

        Call this after external font changes (e.g., font removal).
        """
        self._font_dropdown.options = self._build_font_options()
        # Verify selected font still exists
        available_names = [
            f.name for f in self.font_manager.get_available_fonts()
        ]
        if self.selected_font not in available_names:
            self.selected_font = "Arial"
            self._font_dropdown.value = "Arial"
        self._font_dropdown.update()

    def set_settings(
        self,
        font_name: Optional[str] = None,
        font_size: Optional[int] = None,
        font_color: Optional[str] = None,
        vertical_position: Optional[int] = None,
    ) -> None:
        """Programmatically update settings (e.g., from persisted state).

        Args:
            font_name: Font family name to select.
            font_size: Font size in points (10-120).
            font_color: Hex color string (e.g., '#FF5733').
            vertical_position: Vertical position percentage (0-100).
        """
        if font_name is not None:
            self.selected_font = font_name
            self._font_dropdown.value = font_name

        if font_size is not None:
            self.font_size = max(10, min(120, font_size))
            self._size_slider.value = self.font_size
            self._size_label.value = f"{self.font_size} pt"

        if font_color is not None:
            if _HEX_COLOR_PATTERN.match(font_color):
                self.font_color = font_color
                self._color_field.value = font_color.lstrip("#")
                self._color_preview.bgcolor = font_color

        if vertical_position is not None:
            self.vertical_position = max(0, min(100, vertical_position))
            self._position_slider.value = self.vertical_position
            self._position_label.value = f"{self.vertical_position}%"

    def build(self) -> ft.Control:
        """Build the customization step UI controls.

        Returns:
            A Column containing all customization controls.
        """
        # Font selection dropdown
        self._font_dropdown = ft.Dropdown(
            label="Font Family",
            value=self.selected_font,
            options=self._build_font_options(),
            on_change=self._on_font_changed,
            width=280,
        )

        # Font size slider with label
        self._size_label = ft.Text(f"{self.font_size} pt", size=12)
        self._size_slider = ft.Slider(
            min=10,
            max=120,
            value=self.font_size,
            divisions=110,
            label="{value}",
            on_change=self._on_font_size_changed,
            width=250,
        )

        # Color field with preview swatch
        self._color_field = ft.TextField(
            value=self.font_color.lstrip("#"),
            label="Font Color (hex)",
            width=140,
            on_blur=self._on_color_changed,
            on_submit=self._on_color_changed,
            prefix_text="#",
        )

        self._color_preview = ft.Container(
            width=28,
            height=28,
            bgcolor=self.font_color,
            border_radius=4,
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.GREY_400),
                right=ft.BorderSide(1, ft.Colors.GREY_400),
                bottom=ft.BorderSide(1, ft.Colors.GREY_400),
                left=ft.BorderSide(1, ft.Colors.GREY_400),
            ),
        )

        # Vertical position slider with label
        self._position_label = ft.Text(f"{self.vertical_position}%", size=12)
        self._position_slider = ft.Slider(
            min=0,
            max=100,
            value=self.vertical_position,
            divisions=100,
            label="{value}%",
            on_change=self._on_position_changed,
            width=250,
        )

        # Font import file picker
        self._font_picker = ft.FilePicker()
        self._font_picker.on_result = self._on_import_font_result

        # Import status message
        self._import_status = ft.Text("", size=11, visible=False)

        import_btn = ft.OutlinedButton(
            "Import Font (.ttf)",
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            on_click=lambda _: self._font_picker.pick_files(
                allowed_extensions=["ttf"],
                dialog_title="Select TTF Font File",
            ),
        )

        # Assemble the layout
        if self._font_picker not in self.page.overlay:
            self.page.overlay.append(self._font_picker)

        return ft.Column(
            [
                ft.Text(
                    "Font & Position",
                    size=16,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Container(height=4),
                # Font selection row
                ft.Row(
                    [self._font_dropdown, import_btn],
                    spacing=12,
                    wrap=True,
                ),
                self._import_status,
                ft.Container(height=8),
                # Font size
                ft.Row(
                    [
                        ft.Text("Size:", size=14, width=60),
                        self._size_slider,
                        self._size_label,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                # Font color
                ft.Row(
                    [
                        ft.Text("Color:", size=14, width=60),
                        self._color_field,
                        self._color_preview,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                ft.Container(height=4),
                # Vertical position
                ft.Row(
                    [
                        ft.Text("Y Position:", size=14, width=70),
                        self._position_slider,
                        self._position_label,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    "0% = top, 100% = bottom",
                    size=12,
                    italic=True,
                    color=ft.Colors.GREY_600,
                ),
            ],
            spacing=12,
        )
