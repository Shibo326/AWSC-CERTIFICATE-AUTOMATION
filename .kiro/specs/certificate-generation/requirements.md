# Requirements Document

## Introduction

The Certificate Generation module is the core engine of CertFlow — a web-based automation system that generates personalized certificates and sends them to attendees via email in bulk. This module is responsible for loading certificate templates (PNG, JPG, or PDF), overlaying attendee names with configurable font styling, and outputting generated certificates in a format matching the input template. It supports batch generation for processing entire attendee lists at once.

## Glossary

- **Certificate_Generator**: The top-level orchestrator that coordinates template loading, name rendering, and batch output for certificate generation.
- **Image_Processor**: The component (utils/image_processor.py) that handles name overlay on PNG and JPG templates using the Pillow library.
- **PDF_Processor**: The component (utils/pdf_processor.py) that handles name overlay on PDF templates using ReportLab and PyMuPDF.
- **Template**: A PNG, JPG, or PDF file used as the base certificate design onto which attendee names are rendered.
- **Attendee_List**: A list of attendee name strings parsed from a CSV file, provided as input to the generation engine.
- **Font_Configuration**: A set of parameters specifying font file path (.ttf), font size (in points), font color (as RGB tuple or hex string), and font style.
- **Horizontal_Center**: The calculated x-coordinate that places the rendered name text at the horizontal midpoint of the template.
- **Vertical_Position**: The y-coordinate for name placement, configurable by the user with a default of the vertical center of the template.

## Requirements

### Requirement 1: Load Certificate Template

**User Story:** As a user, I want to load a certificate template from a file, so that I can use it as the base for generating personalized certificates.

#### Acceptance Criteria

1. WHEN a PNG file path is provided, THE Certificate_Generator SHALL load the file as an image template and make it available for name rendering.
2. WHEN a JPG file path is provided, THE Certificate_Generator SHALL load the file as an image template and make it available for name rendering.
3. WHEN a PDF file path is provided, THE Certificate_Generator SHALL load the first page of the PDF as a template and make it available for name rendering.
4. IF the provided file path does not exist, THEN THE Certificate_Generator SHALL raise a FileNotFoundError with a message indicating the missing path.
5. IF the provided file is corrupted or unreadable, THEN THE Certificate_Generator SHALL raise a ValueError with a descriptive error message identifying the file and the nature of the corruption.
6. IF the provided file format is not PNG, JPG, or PDF, THEN THE Certificate_Generator SHALL raise a ValueError indicating the unsupported format and listing the supported formats.

### Requirement 2: Configure Font Settings

**User Story:** As a user, I want to customize the font used for name rendering, so that certificates match my organization's branding.

#### Acceptance Criteria

1. THE Certificate_Generator SHALL accept a Font_Configuration specifying font file path, font size, font color, and font style.
2. WHEN no Font_Configuration is provided, THE Certificate_Generator SHALL use the default font located at assets/fonts/Arial.ttf with a size of 40 points and black color (0, 0, 0).
3. WHEN a custom .ttf font file path is provided, THE Certificate_Generator SHALL load and use that font for name rendering.
4. IF the specified font file does not exist, THEN THE Certificate_Generator SHALL raise a FileNotFoundError with a message indicating the missing font path.
5. IF the specified font file is not a valid TrueType font, THEN THE Certificate_Generator SHALL raise a ValueError indicating the font file is invalid.
6. WHEN a font color is provided as an RGB tuple (three integers each in range 0-255), THE Certificate_Generator SHALL use that color for the rendered name text.
7. WHEN a font color is provided as a hex string (e.g., "#FF5733"), THE Certificate_Generator SHALL convert it to RGB and use that color for the rendered name text.

### Requirement 3: Calculate Name Placement Coordinates

**User Story:** As a user, I want names to be automatically centered on the template, so that certificates look professional without manual positioning.

#### Acceptance Criteria

1. THE Image_Processor SHALL calculate the Horizontal_Center by computing (template_width - text_width) / 2 as the x-coordinate for name placement.
2. THE PDF_Processor SHALL calculate the Horizontal_Center by computing (page_width - text_width) / 2 as the x-coordinate for name placement.
3. WHEN no Vertical_Position is specified, THE Certificate_Generator SHALL place the name at the vertical center of the template (template_height / 2 - text_height / 2).
4. WHEN a Vertical_Position is specified as a pixel value, THE Certificate_Generator SHALL place the name at that y-coordinate.
5. WHEN a Vertical_Position is specified as a percentage (0-100), THE Certificate_Generator SHALL compute the y-coordinate as (percentage / 100) * template_height.
6. IF the calculated text dimensions exceed the template dimensions, THEN THE Certificate_Generator SHALL raise a ValueError indicating the text does not fit within the template bounds.

### Requirement 4: Render Name on Image Template

**User Story:** As a user, I want attendee names rendered onto PNG/JPG templates, so that I can generate image-based certificates.

#### Acceptance Criteria

1. WHEN a PNG template and an attendee name are provided, THE Image_Processor SHALL render the name onto a copy of the template at the calculated coordinates and return a PNG image.
2. WHEN a JPG template and an attendee name are provided, THE Image_Processor SHALL render the name onto a copy of the template at the calculated coordinates and return a JPG image.
3. THE Image_Processor SHALL use the Pillow library (PIL) to draw text onto the template image.
4. THE Image_Processor SHALL preserve the original template file without modification during rendering.
5. THE Image_Processor SHALL render the name using the specified Font_Configuration (font file, size, and color).
6. WHEN the attendee name contains Unicode characters, THE Image_Processor SHALL render those characters correctly provided the font supports them.

### Requirement 5: Render Name on PDF Template

**User Story:** As a user, I want attendee names rendered onto PDF templates, so that I can generate PDF-based certificates.

#### Acceptance Criteria

1. WHEN a PDF template and an attendee name are provided, THE PDF_Processor SHALL render the name onto a copy of the template at the calculated coordinates and return a PDF document.
2. THE PDF_Processor SHALL use ReportLab and PyMuPDF to overlay text onto the PDF template.
3. THE PDF_Processor SHALL preserve the original template file without modification during rendering.
4. THE PDF_Processor SHALL render the name using the specified Font_Configuration (font file, size, and color).
5. WHEN the attendee name contains Unicode characters, THE PDF_Processor SHALL render those characters correctly provided the font supports them.
6. THE PDF_Processor SHALL maintain the original PDF page dimensions and content in the output.

### Requirement 6: Batch Certificate Generation

**User Story:** As a user, I want to generate certificates for all attendees in a list at once, so that I can efficiently produce certificates in bulk.

#### Acceptance Criteria

1. WHEN an Attendee_List and a template are provided, THE Certificate_Generator SHALL generate one certificate per attendee name in the list.
2. THE Certificate_Generator SHALL return a list of generated certificate objects (images or PDF documents) corresponding to each attendee in the input list.
3. THE Certificate_Generator SHALL maintain the order of generated certificates matching the order of names in the Attendee_List.
4. WHEN an Attendee_List contains 0 entries, THE Certificate_Generator SHALL return an empty list without raising an error.
5. IF an error occurs while generating a certificate for a specific attendee, THEN THE Certificate_Generator SHALL log the error with the attendee name and continue processing the remaining attendees.
6. WHEN batch generation completes with errors, THE Certificate_Generator SHALL return both the successfully generated certificates and a list of failed attendee names with their error messages.

### Requirement 7: Output Format Consistency

**User Story:** As a user, I want the output certificate format to match the input template format, so that I receive certificates in the expected file type.

#### Acceptance Criteria

1. WHEN a PNG template is used, THE Certificate_Generator SHALL produce output certificates in PNG format.
2. WHEN a JPG template is used, THE Certificate_Generator SHALL produce output certificates in JPG format.
3. WHEN a PDF template is used, THE Certificate_Generator SHALL produce output certificates in PDF format.
4. THE Certificate_Generator SHALL preserve the original image quality and resolution in output PNG and JPG certificates.
5. THE Certificate_Generator SHALL preserve the original page size and orientation in output PDF certificates.

### Requirement 8: Handle Templates of Various Dimensions

**User Story:** As a user, I want the system to work with any template size, so that I can use certificates of different layouts and orientations.

#### Acceptance Criteria

1. THE Certificate_Generator SHALL process templates of any width and height dimension without imposing minimum or maximum size constraints.
2. WHEN a template with landscape orientation is provided, THE Certificate_Generator SHALL correctly calculate name placement based on the template's actual dimensions.
3. WHEN a template with portrait orientation is provided, THE Certificate_Generator SHALL correctly calculate name placement based on the template's actual dimensions.
4. IF a template has dimensions where width or height is zero or negative, THEN THE Certificate_Generator SHALL raise a ValueError indicating invalid template dimensions.
