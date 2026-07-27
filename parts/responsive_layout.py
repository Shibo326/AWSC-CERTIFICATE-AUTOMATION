"""Responsive layout wrapper for CertFlow native app.

Provides a responsive layout that switches between single-column and
multi-column layouts based on screen width, using Flet's ResponsiveRow
with breakpoint-aware column widths.

Single-column layout: screen width < 600px (portrait/mobile)
Multi-column layout: screen width >= 600px (landscape/tablet/desktop)

Requirements: 11.11, 7.7, 9.6
"""

from typing import Optional

import flet as ft


# Breakpoint threshold in logical pixels (dp).
# Below this value the app renders a single-column layout.
BREAKPOINT_WIDTH = 600


def get_column_count(width: float) -> int:
    """Return the number of columns based on screen width.

    Args:
        width: The current screen/page width in logical pixels.

    Returns:
        1 for narrow screens (width < 600px), 2 for wide screens (width >= 600px).
    """
    return 1 if width < BREAKPOINT_WIDTH else 2


class ResponsiveLayout:
    """Wraps content in a responsive layout that switches between
    single-column and multi-column based on screen width.

    Uses Flet's ResponsiveRow with col breakpoints:
    - sm=12 (full width on small screens, i.e. < 600px)
    - md=6 (half width on medium+ screens, i.e. >= 600px)

    If only left_content is provided, it takes the full width regardless
    of screen size. When both left_content and right_content are provided,
    they stack vertically on small screens and appear side-by-side on
    wider screens.

    Args:
        left_content: Primary content control (always displayed).
        right_content: Secondary content control (displayed alongside
            left_content on wide screens, below it on narrow screens).
            If None, left_content takes full width.
    """

    def __init__(self, page: ft.Page,
        left_content: ft.Control,
        right_content: Optional[ft.Control] = None,
    ) -> None:
        self.page = page
        self.left_content = left_content
        self.right_content = right_content

    def build(self) -> ft.Control:
        """Build the responsive layout using ResponsiveRow.

        Returns:
            A ResponsiveRow that adapts column widths based on breakpoints.
        """
        if self.right_content is None:
            # Single content — always full width
            return ft.ResponsiveRow(
                controls=[
                    ft.Column(
                        col={"sm": 12},
                        controls=[self.left_content],
                    ),
                ],
                expand=True,
            )

        # Two-panel layout with breakpoint-aware columns:
        # - sm (< 600px): each column takes full width (stacked vertically)
        # - md (>= 600px): each column takes half width (side by side)
        left_col = ft.Column(
            col={"sm": 12, "md": 6},
            controls=[self.left_content],
        )

        right_col = ft.Column(
            col={"sm": 12, "md": 6},
            controls=[self.right_content],
        )

        return ft.ResponsiveRow(
            controls=[left_col, right_col],
            expand=True,
        )
