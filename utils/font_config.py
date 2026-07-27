"""Font configuration dataclass for CertFlow.

Provides FontConfiguration for certificate name rendering and a helper
function to resolve the bundled assets directory at runtime across both
development and packaged Flet app scenarios.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple, Union


def get_assets_root() -> Path:
    """Determine the application's bundled assets root directory at runtime.

    Handles two execution modes:
      1. **Packaged Flet app**: Uses the ``FLET_ASSETS_DIR`` environment variable
         set by the Flet build system at runtime.
      2. **Development mode**: Falls back to ``./assets/`` relative to the project
         root (two levels up from this file: ``utils/font_config.py`` -> project root).

    Returns:
        Absolute path to the assets root directory.
    """
    # Packaged Flet app: environment variable set by flet build runtime
    flet_assets_dir = os.environ.get("FLET_ASSETS_DIR")
    if flet_assets_dir:
        return Path(flet_assets_dir).resolve()

    # Development mode: assets/ is at the project root
    # This file lives at <project_root>/utils/font_config.py
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "assets"


def _default_font_path() -> str:
    """Resolve the default font path relative to the assets root.

    Returns:
        Absolute string path to the bundled Arial.ttf font.
    """
    return str(get_assets_root() / "fonts" / "Arial.ttf")


@dataclass
class FontConfiguration:
    """Configuration for certificate name rendering font.

    Attributes:
        font_path: Absolute path to .ttf font file. Defaults to the bundled
            Arial.ttf resolved via the assets root directory.
        font_size: Font size in points.
        font_color: RGB tuple (0-255 per channel).
    """

    font_path: str = field(default_factory=_default_font_path)
    font_size: int = 40
    font_color: Tuple[int, int, int] = (0, 0, 0)

    @staticmethod
    def parse_color(color_input: Union[str, Tuple[int, int, int]]) -> Tuple[int, int, int]:
        """Parse color input to an RGB tuple.

        Args:
            color_input: Either a hex string (e.g., '#FF5733') or an RGB tuple.

        Returns:
            Tuple of (R, G, B) integers in range 0-255.

        Raises:
            ValueError: If the color format is invalid.
        """
        if isinstance(color_input, tuple):
            if len(color_input) != 3:
                raise ValueError(
                    f"RGB tuple must have exactly 3 values, got {len(color_input)}"
                )
            for i, val in enumerate(color_input):
                if not isinstance(val, int) or val < 0 or val > 255:
                    raise ValueError(
                        f"RGB value at index {i} must be an integer 0-255, got {val}"
                    )
            return color_input

        if isinstance(color_input, str):
            hex_str = color_input.lstrip("#")
            if len(hex_str) != 6:
                raise ValueError(
                    f"Hex color must be 6 characters (e.g., '#FF5733'), got '{color_input}'"
                )
            try:
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                return (r, g, b)
            except ValueError:
                raise ValueError(
                    f"Invalid hex color string: '{color_input}'"
                )

        raise ValueError(
            f"Color must be an RGB tuple or hex string, got {type(color_input)}"
        )
