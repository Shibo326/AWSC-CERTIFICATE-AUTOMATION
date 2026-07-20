# 📜 CertFlow

**Cross-platform bulk certificate generator and email sender.**

Generate personalized certificates from templates and send them to attendees via Gmail.
Runs as a native app on Windows, macOS, Android, and iOS.

## Features

- Upload PNG/JPG/PDF certificate templates
- Import attendee lists from CSV or XLSX
- Customize font size, color, and text position
- Live certificate preview
- Bulk email sending via Gmail SMTP
- Download all certificates as ZIP
- Cross-platform: Windows, macOS, Android, iOS

## Quick Start (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app (opens in native window)
python main.py
```

## Building Installable Apps

CertFlow uses [Flet](https://flet.dev) to compile to native apps from a single Python codebase.

### Prerequisites

```bash
pip install flet
```

### Windows (.exe)

```bash
flet build windows
```

Output: `build/windows/CertFlow.exe`

### macOS (.app / .dmg)

```bash
flet build macos
```

Output: `build/macos/CertFlow.app`

### Android (.apk)

```bash
flet build apk
```

Output: `build/apk/CertFlow.apk`

> Requires: Java JDK 17+, Android SDK (auto-downloaded by Flet)

### iOS (.ipa)

```bash
flet build ipa
```

Output: `build/ipa/CertFlow.ipa`

> Requires: macOS with Xcode installed, Apple Developer account for distribution

## Email Configuration

CertFlow loads Gmail credentials from these sources (checked in order):

1. `credentials.toml` (next to the app)
2. `~/.certflow/credentials.toml` (home directory)
3. Environment variables: `CERTFLOW_EMAIL_SENDER`, `CERTFLOW_EMAIL_APP_PASSWORD`

### Setup

```bash
# Copy the example and fill in your credentials
cp credentials.toml.example credentials.toml
```

Edit `credentials.toml`:

```toml
[email]
sender = "your-email@gmail.com"
app_password = "xxxx xxxx xxxx xxxx"
```

> Use a **Gmail App Password** (not your regular password).
> Generate one at: https://myaccount.google.com/apppasswords

## Project Structure

```
certflow/
├── main.py                       # Flet app (cross-platform UI)
├── app.py                        # Legacy Streamlit app (web only)
├── pyproject.toml                # Build & tool configuration
├── requirements.txt              # Python dependencies
├── credentials.toml.example      # Email config template
├── utils/
│   ├── certificate_generator.py  # Orchestrator
│   ├── image_processor.py        # PNG/JPG rendering (Pillow)
│   ├── pdf_processor.py          # PDF rendering (ReportLab + PyMuPDF)
│   ├── csv_parser.py             # CSV/XLSX parsing and validation
│   ├── email_sender.py           # Gmail SMTP bulk sender
│   ├── font_config.py            # Font configuration
│   ├── models.py                 # Data models
│   └── exceptions.py             # Custom exceptions
├── assets/fonts/Arial.ttf        # Default font
├── sample/                       # Example files
│   ├── template_sample.png
│   └── attendees_sample.csv
└── tests/                        # Test suite
```

## CSV Format

Your attendee CSV must have `name` and `email` columns:

```csv
name,email
Juan Dela Cruz,juan@example.com
Maria Santos,maria@example.com
```

XLSX files with the same columns are also supported.

## Tech Stack

- **UI Framework**: [Flet](https://flet.dev) (Python → Flutter, cross-platform)
- **Image Processing**: Pillow
- **PDF Processing**: ReportLab + PyMuPDF
- **Email**: Gmail SMTP (TLS, App Password)
- **Testing**: pytest + hypothesis

## Running Tests

```bash
pytest
```

## License

MIT
