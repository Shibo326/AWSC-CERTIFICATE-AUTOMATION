# CertFlow — Project Standards & Conventions

## Project Overview

CertFlow is a web-based bulk certificate generator and email sender built with Python + Streamlit. It automates generating personalized certificates from templates and sending them to attendees via Gmail SMTP.

## Tech Stack

- **Runtime**: Python 3.11+
- **Framework**: Streamlit (latest stable)
- **Image Processing**: Pillow (PIL)
- **PDF Processing**: ReportLab + PyMuPDF (fitz)
- **Email**: smtplib + email.mime (Gmail SMTP with App Password)
- **CSV**: Python csv module
- **Testing**: pytest + hypothesis (property-based testing)
- **Hosting**: Streamlit Cloud (free tier)

## Project Structure

```
certflow/
├── app.py                    # Main Streamlit application (UI + orchestration)
├── requirements.txt          # Python dependencies (pinned versions)
├── .streamlit/
│   └── secrets.toml          # Gmail credentials (NEVER commit)
├── utils/
│   ├── __init__.py
│   ├── certificate_generator.py  # Orchestrator
│   ├── image_processor.py        # PNG/JPG rendering (Pillow)
│   ├── pdf_processor.py          # PDF rendering (ReportLab + PyMuPDF)
│   ├── csv_parser.py             # CSV parsing and validation
│   ├── email_sender.py           # Gmail SMTP bulk sender
│   ├── font_config.py            # Font configuration dataclass
│   ├── models.py                 # Shared data models
│   └── exceptions.py            # Custom exception classes
├── assets/
│   └── fonts/
│       └── Arial.ttf            # Default font
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── test_image_processor.py
│   ├── test_pdf_processor.py
│   ├── test_csv_parser.py
│   ├── test_email_sender.py
│   └── test_certificate_generator.py
├── sample/
│   ├── template_sample.png
│   └── attendees_sample.csv
├── .gitignore
└── README.md
```

## Coding Standards

### Python Style
- Follow PEP 8 strictly
- Use type hints on all function signatures
- Use dataclasses for data models
- Docstrings on all public methods (Google style)
- Max line length: 100 characters

### Naming Conventions
- Files: snake_case (e.g., `image_processor.py`)
- Classes: PascalCase (e.g., `CertificateGenerator`)
- Functions/methods: snake_case (e.g., `render_name()`)
- Constants: UPPER_SNAKE_CASE (e.g., `MAX_FILE_SIZE_MB`)
- Private methods: prefix with underscore (e.g., `_validate_template()`)

### Error Handling
- Use custom exception classes from `utils/exceptions.py`
- Never catch bare `Exception` — be specific
- Always include descriptive error messages
- Batch operations: log errors and continue, don't halt

### Testing
- Use pytest as the test runner
- Use hypothesis for property-based testing (correctness properties)
- Test files mirror source structure: `utils/foo.py` → `tests/test_foo.py`
- Fixtures in `conftest.py` for shared test data
- Aim for 90%+ coverage on utils/ modules

### Security
- NEVER hardcode credentials
- Gmail credentials only from `.streamlit/secrets.toml` or environment variables
- Always validate user input (file types, sizes, CSV content)
- Sanitize attendee names before rendering (prevent injection)

### Dependencies
- Pin exact versions in `requirements.txt`
- Use only well-known, maintained packages
- Minimal dependency footprint

## Gmail SMTP Configuration

- Server: smtp.gmail.com
- Port: 587 (TLS)
- Auth: App Password (NOT regular password)
- Daily limit: 500 emails (free tier)
- Credentials stored in `.streamlit/secrets.toml`:
  ```toml
  [email]
  sender = "youremail@gmail.com"
  app_password = "xxxx xxxx xxxx xxxx"
  ```

## Streamlit Conventions

- Use `st.session_state` for all persistent data
- Organize UI in logical sections with `st.header()` / `st.subheader()`
- Use `st.sidebar` for configuration/status
- Progress bars: `st.progress()` with real-time updates
- File uploads: always validate type and size
- Use `st.columns()` for responsive layouts
- Provide feedback via `st.success()`, `st.warning()`, `st.error()`

## Git Workflow

- Main branch: `main`
- Feature branches: `feature/{feature-name}`
- Commit messages: conventional format (`feat:`, `fix:`, `test:`, `docs:`)
- Never commit `.streamlit/secrets.toml`
- Always update `requirements.txt` when adding dependencies
