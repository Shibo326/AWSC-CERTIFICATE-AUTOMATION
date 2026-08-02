"""Credentials setup screen UI component for CertFlow native app.

Provides a credentials management interface with:
- Gmail address text field (max 254 chars)
- Masked App Password text field (accepts 16 alpha chars, spaces ignored)
- Field-specific validation error messages on submit
- Display of stored/not-configured status
- "Clear Credentials" action button
- Pre-fill email on auth failure (when called with a pre-fill email)

Requirements: 3.5, 3.6, 3.8, 3.9
"""

from typing import Callable, Optional

import flet as ft

from utils.credential_store import CredentialStore


class CredentialsScreen:
    """Flet UI component for Gmail credential management.

    Displays the credential setup form with validation, status indicator,
    and clear/save actions. Supports pre-filling the email field when
    navigated to after an SMTP authentication failure.

    Args:
        credential_store: CredentialStore instance for secure persistence.
        prefill_email: Optional email address to pre-fill (e.g., after auth
            failure per Requirement 3.8).
        on_credentials_saved: Optional callback invoked after successful save.
        on_credentials_cleared: Optional callback invoked after clear action.
    """

    def __init__(self, page: ft.Page,
        credential_store: CredentialStore,
        prefill_email: str = "",
        on_credentials_saved: Optional[Callable] = None,
        on_credentials_cleared: Optional[Callable] = None,
    ) -> None:
        """Initialize the CredentialsScreen component.

        Args:
            credential_store: CredentialStore instance for storage operations.
            prefill_email: Email to pre-fill in the email field.
            on_credentials_saved: Callback after successful credential save.
            on_credentials_cleared: Callback after credentials are cleared.
        """
        self.page = page
        self.credential_store = credential_store
        self.prefill_email = prefill_email
        self.on_credentials_saved = on_credentials_saved
        self.on_credentials_cleared = on_credentials_cleared

    def initialize(self) -> None:
        """Initialize the component after it's been added to the page.
        Call this after build() to trigger the initial credential status check.
        """
        self.page.run_task(self._check_status)

    def build(self) -> ft.Control:
        """Build the credentials setup screen UI controls.

        Returns:
            A Column containing the status indicator, email field,
            password field, save/clear buttons, and error messages.
        """
        # Status indicator: stored or not configured
        self._status_icon = ft.Icon(
            ft.Icons.LOCK_OUTLINE,
            color=ft.Colors.GREY,
            size=20,
        )
        self._status_text = ft.Text(
            "Checking status...",
            size=13,
            color=ft.Colors.GREY,
        )

        # Auth failure banner (shown when pre-fill email is provided)
        self._auth_error_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.ORANGE, size=18),
                    ft.Text(
                        "Authentication failed. Please re-enter your App Password.",
                        size=12,
                        color=ft.Colors.ORANGE_700,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=6,
            bgcolor=ft.Colors.ORANGE_50,
            visible=bool(self.prefill_email),
        )

        # Email text field (max 254 characters)
        self._email_field = ft.TextField(
            label="Gmail Address",
            value=self.prefill_email,
            max_length=254,
            hint_text="your-email@gmail.com",
            prefix_icon=ft.Icons.EMAIL_OUTLINED,
            width=360,
            on_submit=self._on_save,
        )

        # Email field-specific error text
        self._email_error = ft.Text(
            "",
            size=11,
            color=ft.Colors.RED,
            visible=False,
        )

        # App Password text field (masked, accepts 16 alpha chars + spaces)
        self._password_field = ft.TextField(
            label="App Password",
            password=True,
            can_reveal_password=True,
            hint_text="xxxx xxxx xxxx xxxx",
            prefix_icon=ft.Icons.KEY_OUTLINED,
            width=360,
            on_submit=self._on_save,
        )

        # Password field-specific error text
        self._password_error = ft.Text(
            "",
            size=11,
            color=ft.Colors.RED,
            visible=False,
        )

        # Save button
        self._save_button = ft.ElevatedButton(
            "Save Credentials",
            icon=ft.Icons.SAVE,
            on_click=self._on_save,
        )

        # Clear button
        self._clear_button = ft.OutlinedButton(
            "Clear Credentials",
            icon=ft.Icons.DELETE_OUTLINE,
            on_click=self._on_clear,
        )

        # Success message
        self._success_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.GREEN,
            visible=False,
        )

        # Help expander with detailed step-by-step for non-tech users
        self._help_section = ft.ExpansionTile(
            title=ft.Text(
                "📖 How do I get an App Password?",
                size=13,
                weight=ft.FontWeight.W_500,
                color=ft.Colors.BLUE_700,
            ),
            expanded=False,
            controls=[
                ft.Container(
                    padding=ft.Padding(left=16, top=8, right=16, bottom=12),
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "An App Password is a special 16-character "
                                "password that Google generates so apps like "
                                "CertFlow can send emails from your Gmail. "
                                "It's NOT your regular Gmail password.",
                                size=12,
                                color=ft.Colors.GREY_800,
                            ),
                            ft.Divider(height=12),
                            ft.Text(
                                "Step 1: Turn on 2-Step Verification",
                                size=13,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                "① Open your browser and go to:\n"
                                "    myaccount.google.com/security\n"
                                "② Scroll down to \"How you sign in to Google\"\n"
                                "③ Click \"2-Step Verification\"\n"
                                "④ Follow the prompts (phone number, etc.)\n"
                                "⑤ Done when it says \"2-Step Verification is ON\"",
                                size=12,
                                color=ft.Colors.GREY_700,
                            ),
                            ft.Divider(height=12),
                            ft.Text(
                                "Step 2: Create an App Password",
                                size=13,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                "① Go to: myaccount.google.com/apppasswords\n"
                                "② In the \"App name\" box, type: CertFlow\n"
                                "③ Click \"Create\"\n"
                                "④ Google shows a password like: abcd efgh ijkl mnop\n"
                                "⑤ Copy it right away — you won't see it again!",
                                size=12,
                                color=ft.Colors.GREY_700,
                            ),
                            ft.Divider(height=12),
                            ft.Text(
                                "Step 3: Paste it here",
                                size=13,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                "① In the \"Gmail Address\" field above, type "
                                "your full Gmail (e.g. john@gmail.com)\n"
                                "② In the \"App Password\" field, paste the "
                                "16-character code from Step 2\n"
                                "③ Click \"Save Credentials\" — that's it!",
                                size=12,
                                color=ft.Colors.GREY_700,
                            ),
                            ft.Divider(height=12),
                            ft.Container(
                                padding=ft.Padding(left=8, top=6, right=8, bottom=6),
                                border_radius=6,
                                bgcolor=ft.Colors.BLUE_50,
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            "💡 Good to know:",
                                            size=12,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.BLUE_800,
                                        ),
                                        ft.Text(
                                            "• Your regular Gmail password will NOT work\n"
                                            "• You must turn on 2-Step Verification first\n"
                                            "• Spaces in the App Password are optional\n"
                                            "• Free Gmail can send up to 500 emails/day\n"
                                            "• To revoke access later, just delete the app "
                                            "password from your Google account",
                                            size=11,
                                            color=ft.Colors.BLUE_700,
                                        ),
                                    ],
                                    spacing=4,
                                ),
                            ),
                        ],
                        spacing=6,
                    ),
                ),
            ],
        )

        return ft.Column(
            controls=[
                ft.Text(
                    "Email Credentials",
                    size=17,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(
                    "Connect your Gmail so CertFlow can send certificates "
                    "to your attendees.",
                    size=12,
                    color=ft.Colors.GREY_600,
                ),
                ft.Container(height=4),
                # Status row
                ft.Row(
                    controls=[self._status_icon, self._status_text],
                    spacing=6,
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Container(height=8),
                # Auth failure banner (only visible after auth failure)
                self._auth_error_banner,
                ft.Container(height=8),
                # Email field with error
                self._email_field,
                self._email_error,
                ft.Container(height=4),
                # Password field with error and contextual hint
                self._password_field,
                self._password_error,
                ft.Text(
                    "This is the 16-character code from Google, not your "
                    "regular password.",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_500,
                ),
                ft.Container(height=12),
                # Action buttons
                ft.Row(
                    controls=[self._save_button, self._clear_button],
                    spacing=12,
                ),
                self._success_text,
                ft.Container(height=12),
                # Expandable help guide
                self._help_section,
            ],
            spacing=4,
        )

    def set_prefill_email(self, email: str) -> None:
        """Set a pre-fill email and show the auth failure banner.

        Used when navigating to this screen after an SMTP auth failure
        (Requirement 3.8).

        Args:
            email: The Gmail address to pre-fill.
        """
        self.prefill_email = email
        self._email_field.value = email
        self._password_field.value = ""
        self._auth_error_banner.visible = True
        self.page.update()

    def reset(self) -> None:
        """Reset the screen to its initial state."""
        self._email_field.value = ""
        self._password_field.value = ""
        self._email_error.visible = False
        self._email_error.value = ""
        self._password_error.visible = False
        self._password_error.value = ""
        self._success_text.visible = False
        self._auth_error_banner.visible = False
        self.page.run_task(self._check_status)

    async def _check_status(self) -> None:
        """Check current credential storage status and update the UI."""
        try:
            has_creds = await self.credential_store.has_credentials()
            if has_creds:
                self._status_icon.name = ft.Icons.LOCK
                self._status_icon.color = ft.Colors.GREEN
                self._status_text.value = "Credentials stored"
                self._status_text.color = ft.Colors.GREEN
            else:
                self._status_icon.name = ft.Icons.LOCK_OUTLINE
                self._status_icon.color = ft.Colors.GREY
                self._status_text.value = "Not configured"
                self._status_text.color = ft.Colors.GREY
        except Exception:
            self._status_text.value = "Status check failed"
            self._status_text.color = ft.Colors.RED
        self.page.update()

    def _on_save(self, e: ft.ControlEvent = None) -> None:
        """Validate and save credentials."""
        email = self._email_field.value.strip() if self._email_field.value else ""
        password = self._password_field.value.strip() if self._password_field.value else ""

        # Reset errors
        self._email_error.visible = False
        self._password_error.visible = False
        self._success_text.visible = False

        has_error = False

        # Validate email
        if not email:
            self._email_error.value = "Email address is required."
            self._email_error.visible = True
            has_error = True
        elif "@" not in email or not email.endswith("gmail.com"):
            self._email_error.value = "Please enter a valid Gmail address."
            self._email_error.visible = True
            has_error = True

        # Validate password (16 alpha chars, spaces ignored)
        clean_password = password.replace(" ", "")
        if not clean_password:
            self._password_error.value = "App Password is required."
            self._password_error.visible = True
            has_error = True
        elif len(clean_password) != 16 or not clean_password.isalpha():
            self._password_error.value = (
                "App Password must be 16 alphabetic characters."
            )
            self._password_error.visible = True
            has_error = True

        if has_error:
            self.page.update()
            return

        # Save credentials
        self.page.run_task(self._save_credentials, email, clean_password)

    async def _save_credentials(self, email: str, password: str) -> None:
        """Persist credentials via the credential store.

        Args:
            email: Validated Gmail address.
            password: Validated App Password (16 alpha chars, no spaces).
        """
        try:
            await self.credential_store.store(email=email, app_password=password)
            self._success_text.value = "✅ Credentials saved successfully."
            self._success_text.visible = True
            self._auth_error_banner.visible = False
            await self._check_status()
            if self.on_credentials_saved:
                self.on_credentials_saved()
        except Exception as exc:
            self._password_error.value = f"Failed to save: {exc}"
            self._password_error.visible = True
        self.page.update()

    def _on_clear(self, e: ft.ControlEvent = None) -> None:
        """Clear stored credentials."""
        self.page.run_task(self._clear_credentials)

    async def _clear_credentials(self) -> None:
        """Remove credentials from the credential store."""
        try:
            await self.credential_store.clear()
            self._email_field.value = ""
            self._password_field.value = ""
            self._success_text.value = "Credentials cleared."
            self._success_text.color = ft.Colors.ORANGE
            self._success_text.visible = True
            await self._check_status()
            if self.on_credentials_cleared:
                self.on_credentials_cleared()
        except Exception as exc:
            self._password_error.value = f"Failed to clear: {exc}"
            self._password_error.visible = True
        self.page.update()
