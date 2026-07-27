"""Template upload and preview UI component for CertFlow native app.

Provides a file picker filtered to PNG, JPG, and PDF templates (max 10 MB),
displays a preview within 2 seconds (renders first page for PDFs using PyMuPDF),
and stores the template data and format in component state.
"""

import base64
import os
from typing import Callable, Optional

import flet as ft


# Maximum template file size in bytes (10 MB)
MAX_TEMPLATE_SIZE_BYTES = 10 * 1024 * 1024

# Allowed template extensions
ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg", "pdf"]


class TemplateStep:
    """Flet UI component for template upload and preview.

    Attributes:
        template_data: Raw bytes of the uploaded template file.
        template_format: Normalized format string ("png", "jpg", or "pdf").
        template_filename: Original filename of the uploaded template.
    """

    def __init__(
        self,
        page: ft.Page,
        on_template_loaded: Optional[Callable] = None,
    ) -> None:
        """Initialize the TemplateStep component.

        Args:
            page: The Flet page instance.
            on_template_loaded: Optional callback invoked when a valid template
                is successfully loaded.
        """
        self.page = page
        self.on_template_loaded = on_template_loaded
        self.template_data: Optional[bytes] = None
        self.template_format: Optional[str] = None
        self.template_filename: Optional[str] = None

    def build(self) -> ft.Control:
        """Build the template upload and preview UI controls."""
        self._preview_image = ft.Image(
            src_base64="",
            width=400,
            height=280,
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )

        self._status_text = ft.Text(
            "No template uploaded",
            size=14,
            color=ft.Colors.GREY,
        )

        self._error_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.RED,
            visible=False,
        )

        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)

        self._upload_button = ft.ElevatedButton(
            "Choose Template",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._open_file_picker,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TEAL,
                color=ft.Colors.WHITE,
            ),
        )

        # Register file picker overlay
        if self._file_picker not in self.page.overlay:
            self.page.overlay.append(self._file_picker)

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[self._upload_button, self._status_text],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=12,
                ),
                self._error_text,
                self._preview_image,
            ],
            spacing=12,
        )

    def _open_file_picker(self, e: ft.ControlEvent) -> None:
        """Open the file picker dialog filtered to template file types."""
        self._file_picker.pick_files(
            allowed_extensions=ALLOWED_EXTENSIONS,
            dialog_title="Select Certificate Template",
            allow_multiple=False,
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        """Handle file picker result: validate, generate preview, store state."""
        self._error_text.visible = False
        self._error_text.value = ""

        if not e.files:
            self.page.update()
            return

        file_info = e.files[0]
        file_path = file_info.path

        if not file_path:
            self._show_error(
                asset_type="template",
                filename=file_info.name or "unknown",
                location="file picker",
                message="File path not accessible from file picker.",
            )
            self.page.update()
            return

        if not os.path.isfile(file_path):
            self._show_error(
                asset_type="template",
                filename=file_info.name,
                location=file_path,
                message="File does not exist at the specified location.",
            )
            self.page.update()
            return

        try:
            file_size = os.path.getsize(file_path)
        except OSError as err:
            self._show_error(
                asset_type="template",
                filename=file_info.name,
                location=file_path,
                message=f"Cannot read file size: {err}",
            )
            self.page.update()
            return

        # Validate file size (max 10 MB)
        if file_size > MAX_TEMPLATE_SIZE_BYTES:
            self._show_error(
                asset_type="template",
                filename=file_info.name,
                location=file_path,
                message=(
                    f"File exceeds the 10 MB size limit. "
                    f"Selected file is {file_size / (1024 * 1024):.1f} MB."
                ),
            )
            self.page.update()
            return

        # Determine format from extension
        ext = file_info.name.rsplit(".", 1)[-1].lower() if "." in file_info.name else ""
        if ext == "jpeg":
            ext = "jpg"
        if ext not in ("png", "jpg", "pdf"):
            self._show_error(
                asset_type="template",
                filename=file_info.name,
                location=file_path,
                message=f"Unsupported format '.{ext}'. Use PNG, JPG, or PDF.",
            )
            self.page.update()
            return

        # Read the file bytes
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except OSError as err:
            self._show_error(
                asset_type="template",
                filename=file_info.name,
                location=file_path,
                message=f"Failed to read file: {err}",
            )
            self.page.update()
            return

        # Store template state
        self.template_data = file_bytes
        self.template_format = ext
        self.template_filename = file_info.name

        # Generate preview
        self._generate_preview(file_bytes, ext)

        # Update status
        self._status_text.value = f"✅ {file_info.name} ({file_size / 1024:.0f} KB)"
        self._status_text.color = ft.Colors.GREEN

        self.page.update()

        # Notify parent callback
        if self.on_template_loaded:
            self.on_template_loaded(file_bytes, ext, file_info.name)

    def _generate_preview(self, file_bytes: bytes, fmt: str) -> None:
        """Generate a base64 preview image for display.

        For PNG/JPG: encode directly.
        For PDF: render first page via PyMuPDF if available.

        Args:
            file_bytes: Raw bytes of the template file.
            fmt: Format string ('png', 'jpg', or 'pdf').
        """
        import base64

        try:
            if fmt in ("png", "jpg"):
                encoded = base64.b64encode(file_bytes).decode("ascii")
                self._preview_image.src_base64 = encoded
                self._preview_image.visible = True
            elif fmt == "pdf":
                try:
                    import fitz  # PyMuPDF

                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    if doc.page_count > 0:
                        pdf_page = doc.load_page(0)
                        pix = pdf_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        png_bytes = pix.tobytes("png")
                        encoded = base64.b64encode(png_bytes).decode("ascii")
                        self._preview_image.src_base64 = encoded
                        self._preview_image.visible = True
                    doc.close()
                except ImportError:
                    # PyMuPDF not available — skip preview
                    self._preview_image.visible = False
                except Exception:
                    self._preview_image.visible = False
        except Exception:
            self._preview_image.visible = False

    def _show_error(
        self, asset_type: str, filename: str, location: str, message: str
    ) -> None:
        """Display an error message in the UI.

        Args:
            asset_type: Type of asset (e.g., 'template').
            filename: Name of the file that caused the error.
            location: Path or location description.
            message: Human-readable error description.
        """
        self._error_text.value = f"❌ {message}"
        self._error_text.visible = True
        self._preview_image.visible = False
        self._status_text.value = "No template uploaded"
        self._status_text.color = ft.Colors.GREY

    def reset(self) -> None:
        """Reset the component to its initial state."""
        self.template_data = None
        self.template_format = None
        self.template_filename = None
        self._preview_image.src_base64 = ""
        self._preview_image.visible = False
        self._status_text.value = "No template uploaded"
        self._status_text.color = ft.Colors.GREY
        self._error_text.visible = False
        self._error_text.value = ""
        self.page.update()