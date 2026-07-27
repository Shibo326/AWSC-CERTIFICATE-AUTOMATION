"""Application state persistence using Flet's client storage (SharedPreferences).

Provides cross-platform key-value persistence for user settings such as
template path, font configuration, and email template content.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import flet as ft


@dataclass
class PersistedState:
    """All settings restored from SharedPreferences on app launch.

    Represents the complete persisted application state with sensible
    defaults for each field. Used to restore settings on app launch.

    Attributes:
        template_path: Path to the last-used certificate template file.
        template_format: Format of the last-used template (png, jpg, pdf).
        attendee_path: Path to the last-used attendee list file.
        font_family: Name of the selected font family.
        font_size: Font size in points (10-120).
        font_color: Hex color string for the font (e.g., '#000000').
        vertical_position: Vertical position percentage (0-100).
        email_subject: Email subject line template.
        email_body: Email body template with {name} placeholder support.
    """

    template_path: Optional[str] = None
    template_format: Optional[str] = None
    attendee_path: Optional[str] = None
    font_family: str = "Arial"
    font_size: int = 40
    font_color: str = "#000000"
    vertical_position: int = 50
    email_subject: str = "Your Certificate of Achievement"
    email_body: str = (
        "Hi {name},\n\nPlease find your certificate attached."
        "\n\nBest regards,\nThe Team"
    )


class AppStateManager:
    """Persist and restore application state across sessions.

    Uses Flet's page.client_storage (backed by SharedPreferences on mobile,
    localStorage on web, platform key-value stores on desktop) for
    cross-platform persistence.

    Attributes:
        KEYS: List of all persisted setting keys.
    """

    KEYS: List[str] = [
        "template_path",
        "template_format",
        "attendee_path",
        "font_family",
        "font_size",
        "font_color",
        "vertical_position",
        "email_subject",
        "email_body",
    ]

    _PREFIX = "certflow_"

    def __init__(self, page: ft.Page) -> None:
        """Initialize AppStateManager with a Flet page for client_storage access.

        Args:
            page: The Flet page instance providing client_storage API.
        """
        self._page = page

    def _prefixed_key(self, key: str) -> str:
        """Return the storage key with application prefix.

        Args:
            key: The raw setting key name.

        Returns:
            The prefixed key string for storage.
        """
        return f"{self._PREFIX}{key}"

    async def save(self, key: str, value: str) -> None:
        """Save a setting to persistent storage.

        Args:
            key: The setting key (must be one of KEYS).
            value: The string value to persist.

        Raises:
            ValueError: If the key is not in the allowed KEYS list.
        """
        if key not in self.KEYS:
            raise ValueError(
                f"Invalid key '{key}'. Must be one of: {self.KEYS}"
            )
        await self._page.client_storage.set_async(
            self._prefixed_key(key), value
        )

    async def load_all(self) -> Dict[str, Optional[str]]:
        """Load all persisted settings.

        Returns:
            A dictionary mapping each key to its stored value, or None if
            the key has not been persisted.
        """
        result: Dict[str, Optional[str]] = {}
        for key in self.KEYS:
            value = await self._page.client_storage.get_async(
                self._prefixed_key(key)
            )
            result[key] = value
        return result

    async def clear(self, key: str) -> None:
        """Clear a specific persisted key.

        Args:
            key: The setting key to remove from storage.

        Raises:
            ValueError: If the key is not in the allowed KEYS list.
        """
        if key not in self.KEYS:
            raise ValueError(
                f"Invalid key '{key}'. Must be one of: {self.KEYS}"
            )
        await self._page.client_storage.remove_async(
            self._prefixed_key(key)
        )

    async def clear_all(self) -> None:
        """Reset all persisted state by removing every known key."""
        for key in self.KEYS:
            await self._page.client_storage.remove_async(
                self._prefixed_key(key)
            )

    async def restore_session(self) -> Tuple[PersistedState, List[str]]:
        """Restore all saved settings on app launch.

        Loads all persisted settings and validates that file paths still exist.
        If a persisted file path references a file that no longer exists,
        adds a notification message and clears that path from state.

        If persisted state is missing or unreadable, returns defaults silently.

        Returns:
            Tuple of (PersistedState with restored values, list of warning
            messages for unavailable files).
        """
        warnings: List[str] = []

        try:
            stored = await self.load_all()
        except Exception:
            return PersistedState(), warnings

        # Check if all values are None (empty storage)
        if all(v is None for v in stored.values()):
            return PersistedState(), warnings

        # Validate file paths exist
        template_path = stored.get("template_path")
        if template_path and not os.path.isfile(template_path):
            warnings.append(f"Template file not found: {template_path}")
            stored["template_path"] = None
            try:
                await self.clear("template_path")
            except Exception:
                pass

        attendee_path = stored.get("attendee_path")
        if attendee_path and not os.path.isfile(attendee_path):
            warnings.append(f"Attendee file not found: {attendee_path}")
            stored["attendee_path"] = None
            try:
                await self.clear("attendee_path")
            except Exception:
                pass

        # Convert string values to proper types with defaults for None
        try:
            font_size = int(stored["font_size"]) if stored.get("font_size") else 40
        except (ValueError, TypeError):
            font_size = 40

        try:
            vertical_position = (
                int(stored["vertical_position"])
                if stored.get("vertical_position")
                else 50
            )
        except (ValueError, TypeError):
            vertical_position = 50

        state = PersistedState(
            template_path=stored.get("template_path"),
            template_format=stored.get("template_format"),
            attendee_path=stored.get("attendee_path"),
            font_family=stored.get("font_family") or "Arial",
            font_size=font_size,
            font_color=stored.get("font_color") or "#000000",
            vertical_position=vertical_position,
            email_subject=(
                stored.get("email_subject")
                or "Your Certificate of Achievement"
            ),
            email_body=(
                stored.get("email_body")
                or "Hi {name},\n\nPlease find your certificate attached."
                "\n\nBest regards,\nThe Team"
            ),
        )

        return state, warnings
