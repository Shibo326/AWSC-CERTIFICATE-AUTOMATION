"""Font configuration dataclass for CertFlow."""

from dataclasses import dataclass
from typing import Tuple, Union


@dataclass
class FontConfiguration:
    """Configuration for certificate name rendering font.

    Attributes:
        font_path: Path to .ttf font file.
        font_size: Font size in points.
        font_color: RGB tuple (0-255 per channel).
    """

    font_path: str = "assets/fonts/Arial.ttf"
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
