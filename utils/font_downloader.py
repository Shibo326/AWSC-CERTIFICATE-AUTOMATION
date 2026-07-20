"""Google Fonts downloader for CertFlow.

Downloads TTF font files from Google Fonts and saves them to assets/fonts/.
Uses the Google Fonts CSS API with a desktop User-Agent to get TTF URLs.
"""

import os
import re
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

FONTS_DIR = Path("assets/fonts")

# User-Agent that makes Google Fonts API return TTF URLs (old Safari)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; de-at) "
    "AppleWebKit/533.21.1 (KHTML, like Gecko) "
    "Version/5.0.5 Safari/533.21.1"
)

# Curated list of popular Google Fonts suitable for certificates
POPULAR_FONTS: List[str] = [
    "Abel",
    "Abril Fatface",
    "Alegreya",
    "Alegreya Sans",
    "Anton",
    "Arimo",
    "Bebas Neue",
    "Bitter",
    "Cabin",
    "Cairo",
    "Cinzel",
    "Comfortaa",
    "Cormorant Garamond",
    "Crimson Text",
    "Dancing Script",
    "DM Sans",
    "DM Serif Display",
    "Dosis",
    "EB Garamond",
    "Exo 2",
    "Fira Sans",
    "Great Vibes",
    "Heebo",
    "IBM Plex Sans",
    "IBM Plex Serif",
    "Inter",
    "Josefin Sans",
    "Kanit",
    "Karla",
    "Lato",
    "League Spartan",
    "Libre Baskerville",
    "Libre Franklin",
    "Lobster",
    "Lora",
    "Merriweather",
    "Montserrat",
    "Mulish",
    "Noto Sans",
    "Noto Serif",
    "Nunito",
    "Nunito Sans",
    "Open Sans",
    "Oswald",
    "Outfit",
    "Pacifico",
    "Playfair Display",
    "Plus Jakarta Sans",
    "Poppins",
    "PT Sans",
    "PT Serif",
    "Quicksand",
    "Raleway",
    "Roboto",
    "Roboto Condensed",
    "Roboto Mono",
    "Roboto Slab",
    "Rubik",
    "Sacramento",
    "Source Code Pro",
    "Source Sans 3",
    "Source Serif 4",
    "Space Grotesk",
    "Spectral",
    "Tangerine",
    "Tinos",
    "Ubuntu",
    "Work Sans",
]


def get_font_filename(font_name: str) -> str:
    """Convert a font name to a safe filename.

    Args:
        font_name: Display name like 'Playfair Display'.

    Returns:
        Filename like 'PlayfairDisplay-Regular.ttf'.
    """
    safe_name = font_name.replace(" ", "")
    return f"{safe_name}-Regular.ttf"


def get_font_path(font_name: str) -> Path:
    """Get the local file path where a font would be stored.

    Args:
        font_name: Display name of the font.

    Returns:
        Path to the font file in assets/fonts/.
    """
    return FONTS_DIR / get_font_filename(font_name)


def is_font_downloaded(font_name: str) -> bool:
    """Check if a font TTF file already exists locally.

    Args:
        font_name: Display name of the font.

    Returns:
        True if the font file exists.
    """
    return get_font_path(font_name).exists()


def get_downloaded_fonts() -> List[str]:
    """Get list of font names that are already downloaded.

    Returns:
        List of font display names that exist in assets/fonts/.
    """
    downloaded = []
    for font_name in POPULAR_FONTS:
        if is_font_downloaded(font_name):
            downloaded.append(font_name)
    return downloaded


def download_font(font_name: str) -> Tuple[bool, str]:
    """Download a Google Font TTF file to assets/fonts/.

    Fetches the CSS from Google Fonts API, extracts the TTF URL,
    and downloads the font file.

    Args:
        font_name: Display name of the font (e.g., 'Playfair Display').

    Returns:
        Tuple of (success: bool, message: str).
    """
    # Ensure fonts directory exists
    FONTS_DIR.mkdir(parents=True, exist_ok=True)

    font_path = get_font_path(font_name)

    # Skip if already exists
    if font_path.exists():
        return True, f"'{font_name}' already downloaded"

    try:
        # Request CSS from Google Fonts with TTF-compatible User-Agent
        family = font_name.replace(" ", "+")
        css_url = f"https://fonts.googleapis.com/css2?family={family}&display=swap"

        req = urllib.request.Request(css_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as response:
            css_content = response.read().decode("utf-8")

        # Extract TTF URL from CSS (look for the regular/400 weight first)
        ttf_urls = re.findall(
            r"url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)", css_content
        )

        if not ttf_urls:
            return False, f"No TTF URL found for '{font_name}'"

        # Use the first TTF URL (usually regular weight)
        ttf_url = ttf_urls[0]

        # Download the TTF file
        req = urllib.request.Request(ttf_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as response:
            font_bytes = response.read()

        # Validate it's actually a TTF/OTF file (check magic bytes)
        if not (
            font_bytes[:4] == b"\x00\x01\x00\x00" or font_bytes[:4] == b"OTTO"
        ):
            return False, f"Downloaded file for '{font_name}' is not a valid font"

        # Save to disk
        font_path.write_bytes(font_bytes)

        return True, f"'{font_name}' downloaded successfully"

    except urllib.error.HTTPError as e:
        return False, f"HTTP error downloading '{font_name}': {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Network error downloading '{font_name}': {e.reason}"
    except OSError as e:
        return False, f"File error saving '{font_name}': {e}"


def search_fonts(query: str) -> List[str]:
    """Search the curated font list by partial name match.

    Args:
        query: Search string (case-insensitive).

    Returns:
        List of matching font names.
    """
    if not query.strip():
        return POPULAR_FONTS

    query_lower = query.lower()
    return [f for f in POPULAR_FONTS if query_lower in f.lower()]


def get_available_fonts() -> List[str]:
    """Get all fonts available for use (downloaded + default Arial).

    Returns:
        List of font display names that can be used right now.
    """
    available = ["Arial (Default)"]
    for font_name in POPULAR_FONTS:
        if is_font_downloaded(font_name):
            available.append(font_name)
    return available


def resolve_font_path(font_name: str) -> Optional[str]:
    """Resolve a font display name to its actual file path.

    Args:
        font_name: Display name from the selector, or 'Arial (Default)'.

    Returns:
        String path to the font file, or None if not found.
    """
    if font_name in ("Arial (Default)", "Arial"):
        return "assets/fonts/Arial.ttf"

    font_path = get_font_path(font_name)
    if font_path.exists():
        return str(font_path)

    return None
