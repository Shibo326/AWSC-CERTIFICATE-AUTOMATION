"""Image processor for PNG/JPG certificate name overlay using Pillow."""

from typing import Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from utils.exceptions import FontLoadError, TextOverflowError
from utils.font_config import FontConfiguration


class ImageProcessor:
    """Handles rendering attendee names onto PNG/JPG certificate templates.

    Uses Pillow (PIL) for text rendering and image manipulation.
    The original template is never modified — copies are created for each render.
    """

    def __init__(self, template: Image.Image, font_config: FontConfiguration) -> None:
        """Initialize with a loaded PIL Image template and font settings.

        Args:
            template: PIL Image to use as certificate base.
            font_config: Font configuration (path, size, color).

        Raises:
            FontLoadError: If the font file cannot be loaded.
        """
        self._template = template
        self._font_config = font_config
        self._width, self._height = template.size

        try:
            self._font = ImageFont.truetype(
                font_config.font_path, font_config.font_size
            )
        except OSError as e:
            raise FontLoadError(
                f"Cannot load font at '{font_config.font_path}': {e}"
            )

    def calculate_text_position(
        self,
        text: str,
        vertical_position: Optional[Union[int, float]] = None,
        vertical_as_percentage: bool = False,
    ) -> Tuple[int, int]:
        """Calculate (x, y) coordinates for centered text placement.

        Args:
            text: The text to render (attendee name).
            vertical_position: Y position override. If None, uses vertical center.
            vertical_as_percentage: If True, vertical_position is 0-100 percentage.

        Returns:
            Tuple of (x, y) pixel coordinates.

        Raises:
            TextOverflowError: If text dimensions exceed template bounds.
        """
        bbox = self._font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Horizontal: always center
        x = (self._width - text_width) // 2

        # Vertical: configurable
        if vertical_position is None:
            y = (self._height - text_height) // 2
        elif vertical_as_percentage:
            y = int((vertical_position / 100) * self._height) - text_height // 2
        else:
            y = int(vertical_position)

        # Overflow check
        if x < 0 or x + text_width > self._width:
            raise TextOverflowError(
                f"Text width ({text_width}px) exceeds template width ({self._width}px)"
            )
        if y < 0 or y + text_height > self._height:
            raise TextOverflowError(
                f"Text at y={y} with height {text_height}px exceeds template "
                f"height ({self._height}px)"
            )

        return (x, y)

    def render_name(
        self,
        attendee_name: str,
        vertical_position: Optional[Union[int, float]] = None,
        vertical_as_percentage: bool = False,
    ) -> Image.Image:
        """Render attendee name onto a copy of the template.

        Args:
            attendee_name: Name to render on the certificate.
            vertical_position: Y position override. If None, uses vertical center.
            vertical_as_percentage: If True, vertical_position is 0-100 percentage.

        Returns:
            New PIL Image with the name rendered on it.

        Raises:
            TextOverflowError: If the name doesn't fit within template bounds.
        """
        x, y = self.calculate_text_position(
            attendee_name, vertical_position, vertical_as_percentage
        )

        # Create a copy — never modify the original
        output = self._template.copy()
        draw = ImageDraw.Draw(output)
        draw.text(
            (x, y),
            attendee_name,
            font=self._font,
            fill=self._font_config.font_color,
        )

        return output
