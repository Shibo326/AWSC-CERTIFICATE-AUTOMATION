---
inclusion: fileMatch
fileMatchPattern: "**/email_sender.py"
---

# CertFlow — Email Security & SMTP Guidelines

## Gmail SMTP Security Rules

1. **NEVER** hardcode email addresses or passwords in source code
2. **ALWAYS** load credentials from `.streamlit/secrets.toml` or environment variables
3. **ALWAYS** use TLS (port 587) — never unencrypted SMTP
4. **ALWAYS** use Gmail App Password, never the account password

## Credential Loading Priority

```python
# Priority order:
# 1. .streamlit/secrets.toml (Streamlit Cloud compatible)
# 2. Environment variables (CERTFLOW_EMAIL_SENDER, CERTFLOW_EMAIL_APP_PASSWORD)
# 3. Raise ConfigurationError if neither available
```

## SMTP Connection Pattern

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Always use context manager or explicit quit()
with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(sender_email, app_password)
    # Send emails...
```

## Rate Limiting Awareness

- Gmail free tier: 500 emails/day
- Log a warning when batch size exceeds 450
- Consider adding a small delay (0.5s) between sends to avoid throttling
- Handle `SMTPDataError` for rate limit responses

## Attachment Safety

- Maximum attachment size: 25MB (Gmail limit)
- Validate attachment size BEFORE attempting send
- Use proper MIME types for each format:
  - PNG: `image/png`
  - JPG: `image/jpeg`
  - PDF: `application/pdf`

## Error Recovery

- On connection drop: attempt ONE reconnection
- On auth failure: do NOT retry (credentials are wrong)
- On recipient rejection: log and skip, continue batch
- On rate limit: stop batch, report partial results
