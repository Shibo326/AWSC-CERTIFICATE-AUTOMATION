"""Trim font bundle for production mobile builds.

Copies only the 5 core fonts to build_assets/fonts/ to reduce APK/IPA size.
The full font set (40+ fonts) in assets/fonts/ is ~15 MB; the trimmed set is ~1 MB.

Usage:
    py scripts/trim_fonts.py
"""

import shutil
from pathlib import Path

# Core fonts to include in production builds
CORE_FONTS = [
    "Arial.ttf",
    "Roboto-Regular.ttf",
    "Montserrat-Regular.ttf",
    "PlayfairDisplay-Regular.ttf",
    "GreatVibes-Regular.ttf",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "assets" / "fonts"
OUTPUT_DIR = PROJECT_ROOT / "build_assets" / "fonts"


def trim_fonts() -> None:
    """Copy core fonts to build_assets/fonts/ for production builds."""
    # Clean and recreate output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing = []

    for font_name in CORE_FONTS:
        src = SOURCE_DIR / font_name
        dst = OUTPUT_DIR / font_name
        if src.exists():
            shutil.copy2(src, dst)
            copied += 1
            print(f"  ✓ {font_name}")
        else:
            missing.append(font_name)
            print(f"  ✗ {font_name} (not found in assets/fonts/)")

    print(f"\nCopied {copied}/{len(CORE_FONTS)} core fonts to {OUTPUT_DIR.relative_to(PROJECT_ROOT)}")
    if missing:
        print(f"Missing fonts: {', '.join(missing)}")


if __name__ == "__main__":
    print("Trimming font bundle for production build...\n")
    trim_fonts()
