# Tasks

## Task 1: Set Up Module Structure and Dependencies

- [ ] 1.1 Create the `utils/` directory with `__init__.py`
- [ ] 1.2 Create `utils/exceptions.py` with custom exception classes: `CertificateGenerationError`, `TemplateLoadError`, `FontLoadError`, `TextOverflowError`
- [ ] 1.3 Create `utils/font_config.py` with the `FontConfiguration` dataclass including `font_path`, `font_size`, `font_color` fields, default values (Arial.ttf, 40pt, black), and `parse_color()` static method for hex-to-RGB conversion
- [ ] 1.4 Create `assets/fonts/` directory and add `Arial.ttf` default font file
- [ ] 1.5 Create `requirements.txt` with dependencies: Pillow, PyMuPDF, reportlab

## Task 2: Implement Image Processor (PNG/JPG)

- [ ] 2.1 Create `utils/image_processor.py` with the `ImageProcessor` class
- [ ] 2.2 Implement `__init__` method that accepts a PIL Image template and FontConfiguration, loads the font with `ImageFont.truetype()`
- [ ] 2.3 Implement `calculate_text_position()` method that computes horizontal center as `(template_width - text_width) / 2` and resolves vertical position (default center, pixel value, or percentage)
- [ ] 2.4 Implement `render_name()` method that creates a copy of the template, draws the attendee name at calculated coordinates using `ImageDraw.Draw().text()`, and returns the new image
- [ ] 2.5 Add overflow validation in `calculate_text_position()` that raises `TextOverflowError` when text dimensions exceed template bounds

## Task 3: Implement PDF Processor

- [ ] 3.1 Create `utils/pdf_processor.py` with the `PDFProcessor` class
- [ ] 3.2 Implement `__init__` method that accepts a template path and FontConfiguration, validates the PDF can be opened with PyMuPDF, and registers the font with ReportLab's `pdfmetrics`
- [ ] 3.3 Implement `calculate_text_position()` method that computes horizontal center using `pdfmetrics.stringWidth()` and resolves vertical position (accounting for PDF bottom-left coordinate origin)
- [ ] 3.4 Implement `render_name()` method that opens the template with PyMuPDF, creates a text overlay with ReportLab, merges the overlay onto the first page, and returns the PDF as bytes
- [ ] 3.5 Add overflow validation that raises `TextOverflowError` when text dimensions exceed page bounds

## Task 4: Implement Certificate Generator Orchestrator

- [ ] 4.1 Create `utils/certificate_generator.py` with the `CertificateGenerator` class
- [ ] 4.2 Implement `__init__` method with template loading logic: validate file exists, determine format from extension, validate format is supported, open/parse the file, extract dimensions, and instantiate the appropriate processor
- [ ] 4.3 Implement `generate()` method that accepts an attendee name and optional vertical position, delegates to the appropriate processor, and returns a `CertificateOutput`
- [ ] 4.4 Implement `generate_batch()` method that iterates over an Attendee_List, calls `generate()` for each name in a try/except block, collects successes into `certificates` and failures into `errors`, and returns a `BatchResult`
- [ ] 4.5 Create `utils/models.py` with `CertificateOutput`, `GenerationError`, and `BatchResult` dataclasses

## Task 5: Add Validation and Error Handling

- [ ] 5.1 Add template file existence validation in `CertificateGenerator.__init__()` raising `FileNotFoundError`
- [ ] 5.2 Add template corruption detection (catch Pillow/PyMuPDF parse errors) raising `TemplateLoadError` with descriptive message
- [ ] 5.3 Add unsupported format detection raising `TemplateLoadError` listing supported formats
- [ ] 5.4 Add font file existence validation raising `FileNotFoundError`
- [ ] 5.5 Add invalid font file detection (catch Pillow font load errors) raising `FontLoadError`
- [ ] 5.6 Add invalid template dimensions check (zero or negative width/height) raising `TemplateLoadError`

## Task 6: Write Unit Tests

- [ ] 6.1 Create `tests/` directory with `__init__.py` and `conftest.py` with shared fixtures (sample templates, font config, attendee lists)
- [ ] 6.2 Write tests for `FontConfiguration`: default values, hex color parsing, RGB tuple validation, invalid inputs
- [ ] 6.3 Write tests for `ImageProcessor`: horizontal centering calculation, vertical position resolution (default, pixel, percentage), render produces valid image, overflow detection
- [ ] 6.4 Write tests for `PDFProcessor`: horizontal centering calculation, vertical position resolution, render produces valid PDF, overflow detection
- [ ] 6.5 Write tests for `CertificateGenerator`: template loading (PNG, JPG, PDF), format detection, error cases (missing file, corrupted, unsupported format)
- [ ] 6.6 Write tests for batch generation: correct count (successes + errors = input count), order preservation, empty list handling, partial failure handling
- [ ] 6.7 Write tests for template immutability: original template unchanged after single and batch generation
