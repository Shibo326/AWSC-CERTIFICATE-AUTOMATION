# Design Document

## Overview

The Certificate Generation module is structured as a layered system with a top-level orchestrator (`Certificate_Generator`) that delegates format-specific rendering to specialized processors (`Image_Processor` for PNG/JPG, `PDF_Processor` for PDF). The design prioritizes separation of concerns, testability, and graceful error handling during batch operations.

## Architecture

```
┌─────────────────────────────────────────────────┐
│            Certificate_Generator                 │
│  (Orchestrator: template loading, batching,     │
│   font config, coordinate calculation)          │
├─────────────────────┬───────────────────────────┤
│   Image_Processor   │      PDF_Processor        │
│  (Pillow-based      │  (ReportLab + PyMuPDF     │
│   PNG/JPG render)   │   PDF render)             │
└─────────────────────┴───────────────────────────┘
```

## File Structure

```
utils/
├── certificate_generator.py   # Top-level orchestrator
├── image_processor.py         # PNG/JPG name overlay via Pillow
├── pdf_processor.py           # PDF name overlay via ReportLab/PyMuPDF
├── font_config.py             # Font configuration data class
└── exceptions.py              # Custom exception classes

assets/
└── fonts/
    └── Arial.ttf              # Default font
```

## Data Models

### FontConfiguration

```python
from dataclasses import dataclass, field
from typing import Tuple, Optional

@dataclass
class FontConfiguration:
    font_path: str = "assets/fonts/Arial.ttf"
    font_size: int = 40
    font_color: Tuple[int, int, int] = (0, 0, 0)

    @staticmethod
    def parse_color(color_input) -> Tuple[int, int, int]:
        """Parse RGB tuple or hex string to (R, G, B) tuple."""
        ...
```

### GenerationResult

```python
from dataclasses import dataclass
from typing import List, Union
from PIL import Image

@dataclass
class CertificateOutput:
    attendee_name: str
    certificate: Union[Image.Image, bytes]  # PIL Image or PDF bytes
    format: str  # "png", "jpg", or "pdf"

@dataclass
class GenerationError:
    attendee_name: str
    error_message: str

@dataclass
class BatchResult:
    certificates: List[CertificateOutput]
    errors: List[GenerationError]
```

## Component Design

### Certificate_Generator (utils/certificate_generator.py)

The orchestrator class responsible for:
- Loading and validating templates
- Managing font configuration
- Delegating rendering to format-specific processors
- Coordinating batch generation

```python
class CertificateGenerator:
    def __init__(self, template_path: str, font_config: Optional[FontConfiguration] = None):
        """Load template and configure font settings."""
        ...

    def generate(self, attendee_name: str) -> CertificateOutput:
        """Generate a single certificate for one attendee."""
        ...

    def generate_batch(self, attendee_list: List[str]) -> BatchResult:
        """Generate certificates for all attendees, collecting errors gracefully."""
        ...
```

**Template Loading Logic:**
1. Validate file exists (raise FileNotFoundError if not)
2. Determine format from file extension (.png, .jpg/.jpeg, .pdf)
3. Validate format is supported (raise ValueError if not)
4. Attempt to open/parse the file (raise ValueError if corrupted)
5. Extract template dimensions for coordinate calculation

### Image_Processor (utils/image_processor.py)

Handles PNG and JPG rendering using Pillow:

```python
class ImageProcessor:
    def __init__(self, template: Image.Image, font_config: FontConfiguration):
        """Initialize with a loaded PIL Image template and font settings."""
        ...

    def calculate_text_position(self, text: str, vertical_position=None) -> Tuple[int, int]:
        """Calculate (x, y) coordinates for centered text placement."""
        ...

    def render_name(self, attendee_name: str, vertical_position=None) -> Image.Image:
        """Render attendee name onto a copy of the template, return new image."""
        ...
```

**Rendering Flow:**
1. Create a copy of the template image
2. Load the font using `ImageFont.truetype(font_path, font_size)`
3. Measure text bounding box with `font.getbbox(text)` to get text width/height
4. Calculate horizontal center: `x = (template_width - text_width) / 2`
5. Calculate vertical position (default center or user-specified)
6. Validate text fits within template bounds
7. Draw text using `ImageDraw.Draw(copy).text((x, y), text, font=font, fill=color)`
8. Return the modified copy

### PDF_Processor (utils/pdf_processor.py)

Handles PDF rendering using ReportLab and PyMuPDF:

```python
class PDFProcessor:
    def __init__(self, template_path: str, font_config: FontConfiguration):
        """Initialize with PDF template path and font settings."""
        ...

    def calculate_text_position(self, text: str, page_width: float, page_height: float, vertical_position=None) -> Tuple[float, float]:
        """Calculate (x, y) coordinates for centered text placement on PDF page."""
        ...

    def render_name(self, attendee_name: str, vertical_position=None) -> bytes:
        """Render attendee name onto a copy of the PDF template, return PDF bytes."""
        ...
```

**PDF Rendering Flow:**
1. Open the PDF template with PyMuPDF (`fitz.open(template_path)`)
2. Get the first page and its dimensions
3. Create a text overlay using ReportLab with the configured font
4. Measure text width using `pdfmetrics.stringWidth(text, font_name, font_size)`
5. Calculate horizontal center: `x = (page_width - text_width) / 2`
6. Calculate vertical position (PDF coordinates have origin at bottom-left)
7. Generate an overlay PDF in memory with ReportLab
8. Merge the overlay onto the template page using PyMuPDF
9. Return the resulting PDF as bytes

### Coordinate Calculation

**Vertical Position Resolution:**
- `None` → default to vertical center: `(template_height - text_height) / 2`
- Integer/float value → treat as pixel/point offset from top
- Percentage (0-100 as a separate parameter or type) → compute as `(percentage / 100) * template_height`

**Overflow Detection:**
- After calculating position, verify: `x + text_width <= template_width` and `y + text_height <= template_height`
- Also verify: `x >= 0` and `y >= 0`
- Raise ValueError if text overflows

### Error Handling Strategy

```python
# utils/exceptions.py
class CertificateGenerationError(Exception):
    """Base exception for certificate generation errors."""
    pass

class TemplateLoadError(ValueError):
    """Raised when a template cannot be loaded."""
    pass

class FontLoadError(ValueError):
    """Raised when a font file is invalid."""
    pass

class TextOverflowError(ValueError):
    """Raised when rendered text exceeds template bounds."""
    pass
```

**Batch Error Handling:**
- Each attendee is processed independently in a try/except block
- On success: append `CertificateOutput` to results
- On failure: log the error, append `GenerationError` to errors list
- Return `BatchResult` containing both successful outputs and errors

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Image library | Pillow (PIL) | Industry standard for Python image manipulation, excellent text rendering |
| PDF read | PyMuPDF (fitz) | Fast PDF parsing, good page manipulation API |
| PDF write | ReportLab | Robust text overlay generation, excellent font support |
| Template preservation | Copy-on-write | Never modify the loaded template; create copies for each render |
| Batch strategy | Sequential with error isolation | Simple, predictable, allows partial success reporting |
| Font default | Arial.ttf, 40pt, black | Universally readable, standard size for certificates |
| Color input | RGB tuple or hex string | Covers common use cases, hex is user-friendly |
| Vertical position | Pixel, percentage, or default center | Flexible positioning without overcomplicating the API |

## Correctness Properties

1. **Round-trip template preservation**: Loading a template and generating a certificate with an empty string must produce output equivalent to the original template (tests that rendering doesn't corrupt the base image).

2. **Horizontal centering invariant**: For any template width W and rendered text width T, the x-coordinate must equal (W - T) / 2, ensuring the text is always horizontally centered regardless of name length or template size.

3. **Batch count invariant**: For any Attendee_List of length N, the sum of `len(batch_result.certificates) + len(batch_result.errors)` must equal N.

4. **Format preservation**: For any input template format F (PNG, JPG, PDF), the output certificate format must equal F.

5. **Template immutability**: After generating any number of certificates, the original template object must remain unmodified (byte-identical to its state after initial load).

6. **Idempotent single generation**: Generating a certificate for the same attendee name with the same configuration twice must produce identical output.

7. **Order preservation in batch**: For an Attendee_List [A₁, A₂, ..., Aₙ], the successfully generated certificates must appear in the same relative order as their corresponding names in the input list.
