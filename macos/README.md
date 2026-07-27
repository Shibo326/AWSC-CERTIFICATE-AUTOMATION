# CertFlow macOS Build Guide

## Overview

CertFlow is built as a native macOS application (.app bundle) using `flet build macos`. The build produces a standalone app that runs without Python, pip, or any external runtime.

**Target:** macOS 12 (Monterey) and later  
**Bundle ID:** `com.certflow.app`  
**Max Size:** 120MB

## Quick Start (Development Build)

```bash
# Ensure prerequisites are installed
chmod +x build_macos.sh
./build_macos.sh
```

This produces an unsigned `.app` at `build/macos/CertFlow.app`.

## Prerequisites

1. **macOS** — builds must run on a Mac
2. **Xcode Command Line Tools** — `xcode-select --install`
3. **Python 3.11+** — `python3 --version`
4. **Flet** — `pip install flet`
5. **Flutter SDK** — flet build downloads it automatically, or install manually from https://docs.flutter.dev/get-started/install/macos

## Build Configuration

### pyproject.toml

The `[tool.flet.macos]` section configures:

| Key | Value | Purpose |
|-----|-------|---------|
| `bundle_id` | `com.certflow.app` | macOS bundle identifier |
| `min_os_version` | `12.0` | Minimum macOS 12 Monterey |
| `entitlements` | `macos/CertFlow.entitlements` | App sandbox permissions |

### Entitlements (macos/CertFlow.entitlements)

The entitlements file declares the app's sandboxed capabilities:

| Entitlement | Purpose |
|-------------|---------|
| `com.apple.security.app-sandbox` | Enables App Sandbox (required for notarization) |
| `com.apple.security.network.client` | Allows outbound network connections (SMTP email) |
| `com.apple.security.files.user-selected.read-only` | Allows reading files the user picks via file dialogs |

## Code Signing

Code signing is required to distribute the app without Gatekeeper warnings.

### Setup

1. **Enroll** in the [Apple Developer Program](https://developer.apple.com/programs/) ($99/year)
2. **Create** a "Developer ID Application" certificate at [Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/certificates/list)
3. **Download** and double-click the certificate to install it in Keychain Access
4. **Verify** it appears in Keychain Access under My Certificates

### Signing Command

```bash
export CERTFLOW_DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
./build_macos.sh --sign
```

This signs the app with:
- Hardened runtime (required for notarization)
- Secure timestamp
- The entitlements from `macos/CertFlow.entitlements`

## Notarization

Notarization submits the signed app to Apple for malware scanning. Once notarized and stapled, the app passes Gatekeeper on any Mac without user intervention.

### Setup

1. **Create** an app-specific password at [appleid.apple.com](https://appleid.apple.com) under Security, then App-Specific Passwords
2. **Store** credentials in your Keychain using `notarytool`:

```bash
xcrun notarytool store-credentials "certflow-notary" \
    --apple-id "your-apple-id@example.com" \
    --team-id "YOUR_TEAM_ID" \
    --password "your-app-specific-password"
```

3. **Set** the environment variable:

```bash
export CERTFLOW_NOTARY_PROFILE="certflow-notary"
```

### Notarization Command

```bash
export CERTFLOW_DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
export CERTFLOW_NOTARY_PROFILE="certflow-notary"
./build_macos.sh --notarize
```

This will:
1. Build the app
2. Code sign with Developer ID + hardened runtime
3. ZIP the .app and submit to Apple's notary service
4. Wait for approval (typically 5-15 minutes)
5. Staple the notarization ticket to the .app

### Verifying Notarization

```bash
# Check Gatekeeper approval
spctl --assess --type exec build/macos/CertFlow.app

# Check stapling
xcrun stapler validate build/macos/CertFlow.app
```

## Troubleshooting

### "flet: command not found"
```bash
pip install flet
```

### "Flutter SDK not found"
Flet automatically downloads Flutter on first build. If it fails:
```bash
# Install Flutter manually
brew install flutter
# Or download from https://docs.flutter.dev/get-started/install/macos
```

### Code signing fails with "no identity found"
- Verify certificate in Keychain Access under My Certificates
- Check the CERTFLOW_DEVELOPER_ID matches exactly (including team ID in parentheses)
- Ensure the certificate has not expired

### Notarization fails
Check the detailed log:
```bash
xcrun notarytool log <submission-id> --keychain-profile "certflow-notary"
```

Common issues:
- **Hardened runtime not enabled** — the script uses `--options runtime` automatically
- **Missing timestamp** — the script uses `--timestamp` automatically
- **Unsigned nested binaries** — `--deep` flag handles this

### Build exceeds 120MB
- Check `assets/fonts/` — only 5 core fonts should be bundled
- Verify no unnecessary files in `assets/` directory
- Consider if all Python dependencies are required

## CI/CD Integration

For automated builds (e.g., GitHub Actions on macOS runners):

```yaml
# Example GitHub Actions step
- name: Build macOS App
  run: |
    pip install flet
    chmod +x build_macos.sh
    ./build_macos.sh --notarize
  env:
    CERTFLOW_DEVELOPER_ID: ${{ secrets.MACOS_DEVELOPER_ID }}
    CERTFLOW_NOTARY_PROFILE: certflow-notary
```

Note: You will need to import your Developer ID certificate into the CI runner's Keychain. See Apple's documentation on notarizing macOS software before distribution for details.

## Distribution

After a successful notarized build:

1. **DMG** (recommended): Use `create-dmg` or `hdiutil` to create a drag-and-drop installer
2. **ZIP**: Distribute `CertFlow.app` directly as a ZIP
3. **Mac App Store**: Requires additional App Store provisioning (not covered here)

```bash
# Create a DMG (example using hdiutil)
hdiutil create -volname "CertFlow" -srcfolder build/macos/CertFlow.app \
    -ov -format UDZO build/macos/CertFlow.dmg
```
