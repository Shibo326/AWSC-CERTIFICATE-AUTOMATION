# Android Build Configuration

## Overview

This directory contains Android-specific configuration notes for the CertFlow APK build.
Flet handles most Android configuration automatically via `pyproject.toml` and its internal
Flutter project generation. This document explains what is configured vs. what is auto-generated.

## What `flet build apk` Handles Automatically

When you run `flet build apk`, Flet:

1. **Creates the Flutter project** with proper Gradle build files
2. **Generates AndroidManifest.xml** with permissions from `pyproject.toml`
3. **Sets min/target SDK versions** from `pyproject.toml` settings
4. **Bundles Python runtime** and all listed dependencies
5. **Includes assets/** directory content (fonts, templates, etc.)
6. **Configures package name** from `org` field (com.certflow) + project name -> `com.certflow.app`
7. **Signs the APK** with a debug key (release signing requires separate keystore config)

## What You Configure in `pyproject.toml`

```toml
[tool.flet]
org = "com.certflow"                    # -> package: com.certflow.app
android_min_sdk = 24                    # Android 7.0 Nougat
android_target_sdk = 34                 # Android 14
android_permissions = [
    "INTERNET",
    "READ_EXTERNAL_STORAGE",
    "POST_NOTIFICATIONS",
]
```

## Android Permissions

### INTERNET
- **Purpose**: Required for sending emails via Gmail SMTP (smtp.gmail.com:587)
- **API Level**: All versions
- **User prompt**: None (normal permission, auto-granted)

### READ_EXTERNAL_STORAGE
- **Purpose**: Allows importing template files (PNG/JPG/PDF) and attendee lists (CSV/XLSX) from device storage
- **API Level**: Required for API < 33 (Android 12 and below)
- **User prompt**: Runtime permission dialog on first use
- **Android 13+ (API 33+)**: NOT used. Scoped storage and the system photo picker replace this permission. The app uses `ACTION_OPEN_DOCUMENT` (Storage Access Framework) which doesn't require any storage permission.

### POST_NOTIFICATIONS (API 33+)
- **Purpose**: Display notifications for email queue status (emails queued, sent, failed)
- **API Level**: Required for API 33+ (Android 13+)
- **User prompt**: Runtime permission dialog
- **Graceful degradation**: If denied, the app still functions — queue status is shown in-app instead of as system notifications

## AndroidManifest.xml Permissions Reference

If you need to customize the generated AndroidManifest.xml, here is the permissions block
that Flet generates based on the `pyproject.toml` configuration:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.certflow.app">

    <!-- Network access for Gmail SMTP email sending -->
    <uses-permission android:name="android.permission.INTERNET" />

    <!-- Storage access for importing templates and attendee files (API < 33) -->
    <uses-permission
        android:name="android.permission.READ_EXTERNAL_STORAGE"
        android:maxSdkVersion="32" />

    <!-- Notification permission for email queue status (API 33+) -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

    <application
        android:label="CertFlow"
        android:usesCleartextTraffic="false">
        <!-- Activities and services are managed by Flutter/Flet -->
    </application>
</manifest>
```

## Scoped Storage (Android 13+ / API 33+)

Starting with Android 13, the storage permission model changed significantly:

- **READ_EXTERNAL_STORAGE** is deprecated and has no effect on API 33+
- Apps must use **scoped storage APIs**:
  - `ACTION_OPEN_DOCUMENT` (Storage Access Framework) for file imports
  - `MediaStore` API for media access
  - System photo picker for image selection

CertFlow handles this by:
1. Using Flet's `FilePicker` control which wraps the platform's native file picker
2. The `FilePicker` automatically uses SAF on Android 13+ without needing broad storage access
3. `READ_EXTERNAL_STORAGE` is declared with `android:maxSdkVersion="32"` for backward compatibility

## File Picker Configuration

The app uses filtered file pickers for imports:

- **Templates**: PNG, JPG, PDF files (via system file picker)
- **Attendee Lists**: CSV, XLSX files (via system file picker)

Flet's `FilePicker` control automatically launches the system file picker filtered to accepted
file types, complying with Android's scoped storage requirements.

## Build Size Target

- **Target**: APK under 80MB
- **Includes**: Python runtime, Flet/Flutter framework, PIL/PyMuPDF/ReportLab, 5 bundled fonts
- **Optimization**: Only 5 core fonts bundled (vs. 43 in development), additional fonts imported by user

## Release Build & Signing

For production release (not debug builds):

1. Generate a keystore:
   ```
   keytool -genkey -v -keystore certflow-release.keystore -alias certflow -keyalg RSA -keysize 2048 -validity 10000
   ```

2. Configure signing in the Flet build (consult Flet docs for `--android-signing` options)

3. The release APK can be distributed via:
   - Direct APK sideloading
   - Google Play Store (requires additional listing metadata)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ANDROID_HOME not set` | Set env var to Android SDK path (e.g., `C:\Users\<user>\AppData\Local\Android\Sdk`) |
| `No Java found` | Install JDK 17+ and set `JAVA_HOME` |
| `License not accepted` | Run `sdkmanager --licenses` to accept Android SDK licenses |
| `APK too large` | Check bundled assets size; ensure only 5 core fonts are in `assets/fonts/` for production |
| `Permission denied at runtime` | App handles denial gracefully; check `AndroidManifest.xml` has correct permissions |
