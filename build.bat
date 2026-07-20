@echo off
REM CertFlow Build Script for Windows
REM This script builds the CertFlow app as a standalone Windows executable.
REM
REM Prerequisites:
REM   1. Python 3.11+ installed
REM   2. Flutter SDK installed and in PATH
REM      Download: https://docs.flutter.dev/get-started/install/windows
REM   3. pip install -r requirements.txt
REM
REM Usage:
REM   build.bat windows    - Build Windows .exe
REM   build.bat apk        - Build Android .apk
REM   build.bat run        - Run app in development mode

setlocal

set FLET_EXE=flet

REM Check if flet is available
where %FLET_EXE% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] flet command not found. Install with: pip install flet
    exit /b 1
)

if "%1"=="" goto usage
if "%1"=="run" goto run
if "%1"=="windows" goto build_windows
if "%1"=="apk" goto build_apk
if "%1"=="macos" goto build_macos
if "%1"=="ios" goto build_ios
goto usage

:run
echo [INFO] Starting CertFlow in development mode...
%FLET_EXE% run main.py
goto end

:build_windows
echo [INFO] Building CertFlow for Windows...
%FLET_EXE% build windows --project certflow --product CertFlow --org com.certflow --description "Bulk Certificate Generator and Email Sender" -o build
if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] Build complete! Output: build\windows\
) else (
    echo.
    echo [ERROR] Build failed. Make sure Flutter SDK is installed and in PATH.
    echo         Download Flutter: https://docs.flutter.dev/get-started/install/windows
)
goto end

:build_apk
echo [INFO] Building CertFlow for Android...
%FLET_EXE% build apk --project certflow --product CertFlow --org com.certflow --description "Bulk Certificate Generator and Email Sender" -o build
if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] Build complete! Output: build\apk\
) else (
    echo.
    echo [ERROR] Build failed. Make sure Flutter SDK and Android SDK are available.
)
goto end

:build_macos
echo [INFO] Building CertFlow for macOS...
%FLET_EXE% build macos --project certflow --product CertFlow --org com.certflow --description "Bulk Certificate Generator and Email Sender" -o build
goto end

:build_ios
echo [INFO] Building CertFlow for iOS...
%FLET_EXE% build ipa --project certflow --product CertFlow --org com.certflow --description "Bulk Certificate Generator and Email Sender" -o build
goto end

:usage
echo.
echo CertFlow Build Tool
echo ====================
echo.
echo Usage: build.bat [command]
echo.
echo Commands:
echo   run       Run app in development mode (no build needed)
echo   windows   Build Windows executable (.exe)
echo   apk       Build Android package (.apk)
echo   macos     Build macOS application (.app)
echo   ios       Build iOS application (.ipa)
echo.
echo Prerequisites:
echo   - Python 3.11+
echo   - pip install -r requirements.txt
echo   - Flutter SDK (for build commands only, not for 'run')
echo     Download: https://docs.flutter.dev/get-started/install/windows
echo.

:end
endlocal
