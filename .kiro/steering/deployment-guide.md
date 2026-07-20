---
inclusion: manual
---

# CertFlow — Deployment Guide (Streamlit Cloud)

## Prerequisites

- GitHub account with the certflow repo pushed
- Gmail account with 2-Step Verification enabled
- Gmail App Password generated

## Deployment Steps

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "feat: initial CertFlow implementation"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/certflow.git
git push -u origin main
```

### 2. Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io
2. Click "New app"
3. Select your GitHub repo: `YOUR_USERNAME/certflow`
4. Set main file: `app.py`
5. Click "Deploy"

### 3. Configure Secrets on Streamlit Cloud

In the app settings → Secrets, add:

```toml
[email]
sender = "youremail@gmail.com"
app_password = "xxxx xxxx xxxx xxxx"
```

### 4. Verify Deployment

- Visit your app URL: `https://your-app.streamlit.app`
- Upload a sample template and CSV
- Send a test certificate to yourself

## .gitignore (CRITICAL)

Ensure these are NEVER pushed:

```
.streamlit/secrets.toml
*.env
__pycache__/
.pytest_cache/
generated_certs/
```

## requirements.txt Format

Pin exact versions for reproducible deploys:

```
streamlit==1.38.0
Pillow==10.4.0
PyMuPDF==1.24.9
reportlab==4.2.2
hypothesis==6.108.0
pytest==8.3.2
ruff==0.5.7
mypy==1.11.1
```

## Common Issues

| Issue | Fix |
|-------|-----|
| App crashes on deploy | Check requirements.txt has all deps |
| Email not sending | Verify secrets are set in Streamlit Cloud settings |
| Font not found | Ensure Arial.ttf is committed to assets/fonts/ |
| PDF rendering broken | Make sure PyMuPDF version is compatible |

## Environment Variables (Alternative to secrets.toml)

For local development without secrets.toml:

```bash
set CERTFLOW_EMAIL_SENDER=youremail@gmail.com
set CERTFLOW_EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```
