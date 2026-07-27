@echo off
REM ============================================================================
REM CertFlow Android APK Build Script
REM ============================================================================
REM
REM This script builds the CertFlow app as an Android APK using flet build apk.
REM
REM Prerequisites:
REM   1. Python 3.11+ installed
REM   2. Flet installed: pip install flet
REM   3. Flutter SDK installed and in PATH
REM      Download: https://docs.flutter.dev/get-started/install/windows
REM   4. Android SDK installed (via Android Studio or command-line tools)
REM      - Minimum SDK: API 24 (Android 7.0 Nougat)
REM      - Target SDK: API 34 (Android 14)
REM   5. Java JDK 17+ installed and JAVA_HOME set
REM
REM Output:
REM   build/apk/certflow.apk
REM
REM Package: com.certflow.app
REM Min SDK: 24 (Android 7.0)
REM Target SDK: 34 (Android 14)
REM
REM Permissions requested:
REM   - INTERNET: For email sending via Gmail SMTP
REM   - READ_EXTERNAL_STORAGE: For template/CSV import (Android 12 and below)
REM   - POST_NOTIFICATIONS: For queue status notifications (Android 13+)
REM
REM Note on Android 13+ (API 33+):
REM   Scoped storage is enforced. The app uses the system photo picker and
REM   Storage Access Framework (SAF) instead of READ_EXTERNAL_STORAGE.
REM   The permission is still declared for backward compatibility with API < 33.
REM
REM Usage:
REM   build_android.bat
REM ============================================================================

setlocal

echo.
echo ============================================
echo   CertFlow - Android APK Build
echo ============================================
echo.

REM Check if flet is available
where flet >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] flet command not found.
    echo         Install with: pip install flet
    exit /b 1
)

REM Check if flutter is available
where flutter >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] flutter command not found.
    echo         Install Flutter SDK: https://docs.flutter.dev/get-started/install/windows
    exit /b 1
)

REM Check JAVA_HOME
if "%JAVA_HOME%"=="" (
    echo [WARNING] JAVA_HOME is not set. Android builds require JDK 17+.
    echo           Set JAVA_HOME to your JDK installation directory.
    echo.
)

REM Check ANDROID_HOME / ANDROID_SDK_ROOT
if "%ANDROID_HOME%"=="" (
    if "%ANDROID_SDK_ROOT%"=="" (
        echo [WARNING] ANDROID_HOME/ANDROID_SDK_ROOT is not set.
        echo           Android SDK is required for APK builds.
        echo           Install via Android Studio or command-line tools.
        echo.
    )
)

echo [INFO] Building CertFlow APK...
echo [INFO] Package: com.certflow.app
echo [INFO] Min SDK: 24 (Android 7.0)
echo [INFO] Target SDK: 34 (Android 14)
echo.

REM Run flet build apk
REM Flet reads configuration from pyproject.toml [tool.flet] section:
REM   - org = "com.certflow" -> package becomes com.certflow.app
REM   - android_min_sdk = 24
REM   - android_target_sdk = 34
REM   - android_permissions = ["INTERNET", "READ_EXTERNAL_STORAGE", "POST_NOTIFICATIONS"]
REM   - assets = "assets" (includes fonts and other bundled resources)
flet build apk --project certflow --product CertFlow --org com.certflow --description "Bulk Certificate Generator and Email Sender" -o build

if %ERRORLEVEL% equ 0 (
    echo.
    echo ============================================
    echo   [SUCCESS] APK build complete!
    echo ============================================
    echo.
    echo   Output: build\apk\
    echo.
    echo   Install on device:
    echo     adb install build\apk\certflow.apk
    echo.
    echo   Or transfer the APK file to your Android device.
    echo.
    exit /b 0
) else (
    echo.
    echo ============================================
    echo   [ERROR] APK build failed!
    echo ============================================
    echo.
    echo   Troubleshooting:
    echo     1. Ensure Flutter SDK is installed and in PATH
    echo     2. Ensure Android SDK is installed (ANDROID_HOME set)
    echo     3. Ensure JDK 17+ is installed (JAVA_HOME set)
    echo     4. Run 'flutter doctor' to check environment
    echo     5. Run 'flet build apk --verbose' for detailed output
    echo.
    exit /b 1
)

endlocal
