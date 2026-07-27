# CertFlow iOS Build Configuration

## Overview

This directory contains iOS-specific configuration and documentation for building
CertFlow as an iOS application (.ipa) using `flet build ipa`.

**Bundle ID:** `com.certflow.app`
**Minimum iOS:** 16.0
**Permissions:** Network access only (for SMTP email sending)

---

## Prerequisites

1. **macOS** — iOS builds require a Mac with Xcode installed
2. **Xcode 15+** — Download from Mac App Store
3. **Apple Developer Account** — Required for provisioning and code signing
4. **Flutter SDK** — Installed and in PATH
5. **CocoaPods** — `sudo gem install cocoapods`
6. **Python 3.11+** with `flet` installed

---

## Provisioning Profile Requirements

### Development (Testing on Device)

To test on a physical device during development:

1. **Create an App ID** in Apple Developer Portal:
   - Bundle ID: `com.certflow.app`
   - Capabilities: None required (no push notifications, no special entitlements)

2. **Create a Development Provisioning Profile**:
   - Type: iOS App Development
   - App ID: `com.certflow.app`
   - Certificates: Your iOS Development certificate
   - Devices: Register your test device UDIDs

3. **Install via Xcode**:
   - Xcode > Settings > Accounts > Your Team > Download Manual Profiles
   - Or double-click the `.mobileprovision` file

### Distribution (App Store / TestFlight)

For App Store submission:

1. **Create a Distribution Certificate**:
   - Type: Apple Distribution (covers App Store + Ad Hoc)
   - Download and install in Keychain Access

2. **Create a Distribution Provisioning Profile**:
   - Type: App Store
   - App ID: `com.certflow.app`
   - Certificate: Your Apple Distribution certificate

3. **Export for upload**:
   - Archive in Xcode
   - Upload to App Store Connect via Xcode Organizer or Transporter

### Ad Hoc Distribution (Direct Install)

For distributing to specific devices without the App Store:

1. **Create an Ad Hoc Provisioning Profile**:
   - Type: Ad Hoc
   - App ID: `com.certflow.app`
   - Devices: All target device UDIDs registered

---

## Signing Certificate Setup

### Automatic Signing (Recommended for Development)

Set your Team ID and let Xcode manage signing:

```bash
export CERTFLOW_IOS_TEAM_ID="YOUR_TEAM_ID"
./build_ios.sh
```

### Manual Signing

For CI/CD or when you need explicit control:

```bash
export CERTFLOW_IOS_TEAM_ID="YOUR_TEAM_ID"
export CERTFLOW_IOS_SIGNING_IDENTITY="Apple Distribution: Your Name (TEAM_ID)"
export CERTFLOW_IOS_PROVISIONING="/path/to/CertFlow_AppStore.mobileprovision"
./build_ios.sh
```

### Finding Your Team ID

1. Log in to [Apple Developer Portal](https://developer.apple.com/account)
2. Go to Membership Details
3. Your Team ID is a 10-character alphanumeric string

### Finding Your Signing Identity

```bash
security find-identity -v -p codesigning
```

Look for entries like:
- `iPhone Developer: ...` (development)
- `Apple Distribution: ...` (distribution)
- `iPhone Distribution: ...` (legacy distribution)

---

## Permissions

CertFlow requires **minimal iOS permissions**:

| Permission | Purpose | Required? |
|-----------|---------|-----------|
| Network Access | SMTP email sending to smtp.gmail.com:587 | Yes |
| File Access (Document Picker) | Import templates and attendee files | Yes (via system picker) |

**Not required:**
- Camera
- Photo Library
- Location
- Push Notifications
- Contacts
- Microphone
- Bluetooth

The app uses only the iOS document picker (UIDocumentPickerViewController via
Flutter's file_picker) which grants scoped file access without requiring broad
storage permissions.

---

## iOS Document Picker Configuration

CertFlow uses the iOS document picker for importing files. The picker is
configured with the following filters:

### Template Files (Certificate Background)

| Property | Value |
|----------|-------|
| Allowed types | PNG, JPG/JPEG, PDF |
| UTIs | `public.png`, `public.jpeg`, `com.adobe.pdf` |
| Maximum size | 10 MB |
| Picker mode | Single file selection |

### Attendee Files (Name/Email Lists)

| Property | Value |
|----------|-------|
| Allowed types | CSV, XLSX |
| UTIs | `public.comma-separated-values-text`, `org.openxmlformats.spreadsheetml.sheet` |
| Maximum size | 5 MB |
| Picker mode | Single file selection |

### Implementation Notes

The document picker is invoked via Flet's `FilePicker` control:

```python
# Template file picker
template_picker = ft.FilePicker(
    on_result=handle_template_picked,
)
template_picker.allowed_extensions = ["png", "jpg", "jpeg", "pdf"]

# Attendee file picker
attendee_picker = ft.FilePicker(
    on_result=handle_attendee_picked,
)
attendee_picker.allowed_extensions = ["csv", "xlsx"]
```

**File size validation** is performed after the picker returns:
- Templates: reject files > 10 MB with user-friendly error
- Attendee lists: reject files > 5 MB with user-friendly error

**Scoped access:** On iOS, the document picker grants temporary security-scoped
access to the selected file. The app reads the file data immediately upon
selection and stores it in memory / app sandbox. The original file reference
does not persist across sessions.

---

## Build Commands

### Quick Build (Development)

```bash
# Without code signing (verify build compiles)
./build_ios.sh --no-codesign
```

### Full Build (Signed)

```bash
# Set signing environment variables
export CERTFLOW_IOS_TEAM_ID="YOUR_TEAM_ID"

# Build signed .ipa
./build_ios.sh
```

### Using build.bat (Windows — Cross-Reference Only)

The `build.bat ios` command calls `flet build ipa` but will fail on Windows.
iOS builds must be performed on macOS.

---

## Info.plist Configuration

See `Info.plist.additions` for the additional plist keys CertFlow requires:

- **NSAppTransportSecurity** — Allows SMTP connection to smtp.gmail.com (TLS 1.2+)
- **CFBundleDocumentTypes** — Declares supported import file types
- **UTImportedTypeDeclarations** — Registers XLSX UTI if not already known
- **UIFileSharingEnabled** — Allows generated certificates to appear in Files app
- **LSSupportsOpeningDocumentsInPlace** — Enables opening documents from Files app
- **UISupportedInterfaceOrientations** — Portrait + landscape on iPhone and iPad

---

## Troubleshooting

### "No provisioning profile found"

1. Ensure you have a valid profile for `com.certflow.app`
2. Check it's not expired: Xcode > Settings > Accounts > Manage Certificates
3. Re-download profiles from Apple Developer Portal

### "Code signing identity not found"

1. Check your certificate is in Keychain: `security find-identity -v -p codesigning`
2. If missing, download from Apple Developer Portal and double-click to install
3. Ensure the certificate matches your provisioning profile's team

### "Bundle ID mismatch"

The provisioning profile must be created for exactly `com.certflow.app`.
Wildcard profiles (`com.certflow.*`) will also work for development.

### Build fails with CocoaPods errors

```bash
cd build/ipa
pod install --repo-update
```

### Build fails with Flutter errors

```bash
flutter doctor
flutter upgrade
flutter clean
```

---

## CI/CD Integration

For automated builds (e.g., GitHub Actions on macOS runners):

```yaml
# Example GitHub Actions step
- name: Build iOS
  env:
    CERTFLOW_IOS_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
    CERTFLOW_IOS_SIGNING_IDENTITY: ${{ secrets.IOS_SIGNING_IDENTITY }}
    CERTFLOW_IOS_PROVISIONING: ${{ runner.temp }}/profile.mobileprovision
  run: |
    # Decode and install provisioning profile
    echo "${{ secrets.IOS_PROVISIONING_BASE64 }}" | base64 -d > "$CERTFLOW_IOS_PROVISIONING"
    mkdir -p ~/Library/MobileDevice/Provisioning\ Profiles
    cp "$CERTFLOW_IOS_PROVISIONING" ~/Library/MobileDevice/Provisioning\ Profiles/

    # Build
    ./build_ios.sh
```

**Required CI secrets:**
- `APPLE_TEAM_ID` — Your Apple Developer Team ID
- `IOS_SIGNING_IDENTITY` — Full signing identity string
- `IOS_PROVISIONING_BASE64` — Base64-encoded .mobileprovision file
- `IOS_CERTIFICATE_P12_BASE64` — Base64-encoded signing certificate
- `IOS_CERTIFICATE_PASSWORD` — Password for the .p12 certificate
