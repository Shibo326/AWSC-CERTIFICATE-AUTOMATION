---
inclusion: fileMatch
fileMatchPattern: "tests/**"
---

# CertFlow — Testing Guide

## Testing Framework

- **Test runner**: pytest
- **Property-based testing**: hypothesis
- **Coverage**: pytest-cov

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=utils --cov-report=term-missing

# Run specific module tests
pytest tests/test_image_processor.py

# Run property-based tests only
pytest -m "hypothesis"
```

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── test_image_processor.py        # Image rendering tests
├── test_pdf_processor.py          # PDF rendering tests
├── test_csv_parser.py             # CSV parsing tests
├── test_email_sender.py           # Email sending tests (mocked SMTP)
└── test_certificate_generator.py  # Orchestrator tests
```

## Correctness Properties (Property-Based Testing)

These are the formal properties that MUST hold. Use hypothesis to verify:

### Certificate Generation Properties
1. **Horizontal centering**: For any template width W and text width T, x = (W - T) / 2
2. **Batch count invariant**: len(successes) + len(failures) == len(input_list)
3. **Format preservation**: input format == output format (PNG→PNG, PDF→PDF)
4. **Template immutability**: template unchanged after any generation
5. **Idempotent generation**: same input → same output (deterministic)
6. **Order preservation**: output order matches input order

### CSV Parser Properties
7. **Round-trip consistency**: parse(format(parse(csv))) == parse(csv)
8. **Validation completeness**: every row is either valid OR has an error (none lost)
9. **Duplicate detection**: duplicate emails always flagged except first occurrence

### Email Sender Properties
10. **Delivery completeness**: sent + failed == total attempted
11. **Progress monotonicity**: progress callback values are strictly increasing

## Fixtures (conftest.py)

Required shared fixtures:
- `sample_png_template` — 800x600 white PNG image
- `sample_jpg_template` — 800x600 white JPG image
- `sample_pdf_template` — A4 blank PDF
- `default_font_config` — Arial, 40pt, black
- `sample_attendees` — list of 5 valid Attendee_Record objects
- `sample_csv_content` — valid CSV string with name,email columns

## Mocking Strategy

- **Email tests**: Always mock smtplib.SMTP — never send real emails in tests
- **File I/O**: Use tmp_path fixture for temporary files
- **Streamlit**: Use streamlit.testing (if available) or mock st.session_state

## Test Naming Convention

```python
def test_{method_name}_{scenario}_{expected_result}():
    """Example: test_render_name_valid_input_returns_image"""
    pass
```

## Coverage Targets

| Module | Target |
|--------|--------|
| utils/image_processor.py | 95% |
| utils/pdf_processor.py | 95% |
| utils/csv_parser.py | 95% |
| utils/email_sender.py | 90% |
| utils/certificate_generator.py | 95% |
