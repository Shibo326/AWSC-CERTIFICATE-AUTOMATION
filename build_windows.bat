@echo off
REM ============================================================================
REM CertFlow Windows Build Script
REM ============================================================================
REM Builds CertFlow as a standalone Windows executable using flet build windows.
REM
REM Prerequisites:
REM   1. Python 3.11+ installed and in PATH
REM   2. Flutter SDK installed and in PATH
REM      Download: https://docs.flutter.dev/get-started/install/windows
REM   3. Flet installed: pip install flet
REM   4. All dependencies installed: pip install -r requirements-native.txt
REM
REM Output:
REM   build\windows\  - Contains the standalone CertFlow.exe and dependencies
REM
REM The flet build windows command reads configuration from pyproject.toml
REM [tool.flet] section and produces a standalone .exe that bundles:
REM   - Python runtime
REM   - All dependencies (Pillow, PyMuPDF, ReportLab, openpyxl, flet, etc.)
REM   - All assets (fonts, icons)
REM ============================================================================

setlocal EnableDelayedExpansion

echo.
echo ============================================================================
echo  CertFlow Windows Build
echo ============================================================================
echo.

REM --- Check prerequisites ---

echo [1/4] Checking prerequisites...

REM Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo         Install Python 3.11+ from https://python.org
    exit /b 1
)

REM Check Flet CLI
where flet >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Flet CLI not found in PATH.
    echo         Install with: pip install flet
    exit /b 1
)

REM Check Flutter SDK
where flutter >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Flutter SDK not found in PATH.
    echo         Download from: https://docs.flutter.dev/get-started/install/windows
    echo         Ensure flutter\bin is added to your PATH environment variable.
    exit /b 1
)

echo         Python:  OK
echo         Flet:    OK
echo         Flutter: OK
echo.

REM --- Verify project configuration ---

echo [2/4] Verifying project configuration...

if not exist "pyproject.toml" (
    echo [ERROR] pyproject.toml not found in current directory.
    echo         Run this script from the project root directory.
    exit /b 1
)

if not exist "main.py" (
    echo [ERROR] main.py (app entry point) not found.
    exit /b 1
)

if not exist "assets\fonts" (
    echo [WARNING] assets\fonts directory not found. Fonts may be missing from build.
)

echo         pyproject.toml: OK
echo         main.py:        OK
echo         assets/fonts:   OK
echo.

REM --- Run the build ---

echo [3/4] Building Windows executable...
echo         This may take several minutes on first build.
echo.

flet build windows -o build

set BUILD_EXIT_CODE=%ERRORLEVEL%

echo.

REM --- Report result ---

echo [4/4] Build result:
echo.

if %BUILD_EXIT_CODE% equ 0 (
    echo ============================================================================
    echo  BUILD SUCCESSFUL
    echo ============================================================================
    echo.
    echo  Output directory: build\windows\
    echo.
    echo  The executable bundles:
    echo    - Python runtime (no Python installation needed on target machine)
    echo    - All dependencies (Pillow, PyMuPDF, ReportLab, etc.)
    echo    - All assets (fonts directory, icons)
    echo.
    echo  To distribute, copy the entire build\windows\ folder to the target machine.
    echo ============================================================================
) else (
    echo ============================================================================
    echo  BUILD FAILED  (exit code: %BUILD_EXIT_CODE%)
    echo ============================================================================
    echo.
    echo  Common causes:
    echo    - Flutter SDK not properly configured (run: flutter doctor)
    echo    - Missing dependencies in pyproject.toml [tool.flet] dependencies
    echo    - Syntax errors in Python source files
    echo    - Missing or invalid assets referenced in code
    echo.
    echo  Troubleshooting steps:
    echo    1. Run "flutter doctor" and resolve any issues
    echo    2. Run "flet run main.py" to verify the app runs in dev mode
    echo    3. Check the error output above for specific failure details
    echo    4. Ensure pyproject.toml [tool.flet] section is correctly configured
    echo ============================================================================
    exit /b %BUILD_EXIT_CODE%
)

endlocal
exit /b 0
