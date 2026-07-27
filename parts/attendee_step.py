"""Attendee list upload and validation display component for CertFlow.

Provides a file picker (CSV/XLSX, max 5 MB) that parses the uploaded file,
displays valid attendee count on success, and shows row-specific validation
errors with row number, field name, and error message.

Requirements: 11.2, 1.7
"""

import os
from typing import Callable, List, Optional

import flet as ft

from utils.csv_parser import CSVParser
from utils.models import AttendeeRecord, ValidationError

MAX_CSV_SIZE_MB = 5
MAX_CSV_SIZE_BYTES = MAX_CSV_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = ["csv", "xlsx"]


class AttendeeStep:
    """Attendee list upload and validation UI component.

    Handles file picking, parsing via CSVParser, and displays results
    including valid attendee count and any row-level validation errors.

    Args:
        on_attendees_loaded: Optional callback invoked with the list of valid
            AttendeeRecord objects after a successful parse.
    """

    def __init__(self, page: ft.Page, on_attendees_loaded: Optional[Callable[[List[AttendeeRecord]], None]] = None):
        self.page = page
        self.on_attendees_loaded = on_attendees_loaded
        self.attendees: List[AttendeeRecord] = []
        self.errors: List[ValidationError] = []
        self._parser = CSVParser()

        # UI controls
        self._status_text = ft.Text(
            "No attendees loaded", size=14, color=ft.Colors.GREY
        )
        self._error_container = ft.Column(visible=False, spacing=4)
        self._attendee_count_text = ft.Text("", size=14, visible=False)
        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)

    def build(self) -> ft.Control:
        """Build the attendee upload UI component."""
        if self._file_picker not in self.page.overlay:
            self.page.overlay.append(self._file_picker)

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            "Choose File",
                            icon=ft.Icons.TABLE_CHART,
                            on_click=self._pick_file,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.TEAL,
                                color=ft.Colors.WHITE,
                            ),
                        ),
                        self._status_text,
                    ],
                    spacing=12,
                ),
                self._attendee_count_text,
                self._error_container,
            ],
            spacing=12,
        )

    def _pick_file(self, e: ft.ControlEvent) -> None:
        """Launch the file picker dialog filtered to CSV/XLSX."""
        self._file_picker.pick_files(
            allowed_extensions=ALLOWED_EXTENSIONS,
            dialog_title="Select Attendee File (CSV or XLSX)",
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        """Handle the file picker result: validate, parse, and display results."""
        if not e.files:
            return

        file = e.files[0]
        file_path = file.path
        if not file_path:
            self._show_error("File picker error: could not access the selected file.")
            return

        # Validate file size (max 5 MB per iOS requirement 9.5)
        try:
            file_size = os.path.getsize(file_path)
        except OSError as ex:
            self._show_error(f"Cannot read file: {ex}")
            return

        if file_size > MAX_CSV_SIZE_BYTES:
            self._show_error(
                f"File exceeds the {MAX_CSV_SIZE_MB} MB size limit. "
                f"Selected file is {file_size / (1024 * 1024):.1f} MB."
            )
            return

        # Determine format from extension
        ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
        if ext not in ("csv", "xlsx"):
            self._show_error(
                f"Unsupported file format '.{ext}'. Please use CSV or XLSX."
            )
            return

        # Parse the file
        try:
            if ext == "xlsx":
                with open(file_path, "rb") as f:
                    result = self._parser.parse_xlsx(f.read())
            else:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    self._show_error(
                        "Unsupported file encoding. The CSV file must be "
                        "UTF-8 encoded. Please re-save the file with UTF-8 "
                        "encoding and try again."
                    )
                    return
                result = self._parser.parse(content)

        except ValueError as ex:
            # CSVParser raises ValueError for:
            # - Empty file (corruption)
            # - Missing required columns (name, email)
            # - Unreadable XLSX (corruption)
            self._show_parse_failure(str(ex))
            return
        except Exception as ex:
            # Catch-all for unexpected parsing errors (corrupted files, etc.)
            self._show_parse_failure(f"Failed to parse file: {ex}")
            return

        # Store results
        self.attendees = result.records
        self.errors = result.errors

        # Display success: valid attendee count
        self._status_text.value = f"\u2705 {len(result.records)} valid attendees loaded"
        self._status_text.color = ft.Colors.GREEN
        self._attendee_count_text.visible = False

        # Display validation errors if present
        self._error_container.controls.clear()
        if result.errors:
            self._error_container.visible = True
            self._error_container.controls.append(
                ft.Text(
                    f"\u26a0\ufe0f {len(result.errors)} validation issue(s) found:",
                    color=ft.Colors.ORANGE,
                    size=13,
                    weight=ft.FontWeight.W_500,
                )
            )
            for error in result.errors:
                self._error_container.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text(
                                    f"Row {error.row_number}",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.RED_700,
                                ),
                                ft.Text("\u2022", size=12, color=ft.Colors.GREY),
                                ft.Text(
                                    error.field,
                                    size=12,
                                    italic=True,
                                    color=ft.Colors.GREY_700,
                                ),
                                ft.Text("\u2022", size=12, color=ft.Colors.GREY),
                                ft.Text(
                                    error.message,
                                    size=12,
                                    color=ft.Colors.RED_700,
                                ),
                            ],
                            spacing=6,
                            wrap=True,
                        ),
                        padding=ft.Padding(left=12, top=0, right=0, bottom=0),
                    )
                )
        else:
            self._error_container.visible = False

        self.page.update()

        # Invoke callback with valid attendees
        if self.on_attendees_loaded:
            self.on_attendees_loaded(self.attendees)

    def _show_error(self, message: str) -> None:
        """Display a general error message (file access, size limit, etc.)."""
        self.attendees = []
        self.errors = []
        self._status_text.value = f"\u274c {message}"
        self._status_text.color = ft.Colors.RED
        self._attendee_count_text.visible = False
        self._error_container.visible = False
        self._error_container.controls.clear()
        self.page.update()

    def _show_parse_failure(self, reason: str) -> None:
        """Display a parsing failure with the specific reason.

        Shows failures like corruption, unsupported encoding, or missing
        required columns without making any network request.
        """
        self.attendees = []
        self.errors = []
        self._status_text.value = "\u274c Failed to parse attendee file"
        self._status_text.color = ft.Colors.RED
        self._attendee_count_text.visible = False

        self._error_container.controls.clear()
        self._error_container.visible = True
        self._error_container.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Parsing failure:",
                            size=13,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.RED_700,
                        ),
                        ft.Text(
                            reason,
                            size=12,
                            color=ft.Colors.RED_700,
                        ),
                    ],
                    spacing=4,
                ),
                bgcolor=ft.Colors.RED_50,
                padding=10,
                border_radius=6,
            )
        )
        self.page.update()

    def reset(self) -> None:
        """Reset the component to its initial state."""
        self.attendees = []
        self.errors = []
        self._status_text.value = "No attendees loaded"
        self._status_text.color = ft.Colors.GREY
        self._attendee_count_text.visible = False
        self._error_container.visible = False
        self._error_container.controls.clear()
        self.page.update()
