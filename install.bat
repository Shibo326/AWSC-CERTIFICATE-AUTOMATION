@echo off
title Setup - Prototype Cert Automation
echo.
echo  ================================
echo   Prototype Cert Automation
echo   INSTALLER
echo  ================================
echo.

REM Check Python
py --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found!
    echo         Download from: https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [OK] Python found
py --version

echo.
echo [INFO] Installing dependencies...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt

if %ERRORLEVEL% equ 0 (
    echo.
    echo  ================================
    echo   SETUP COMPLETE!
    echo  ================================
    echo.
    echo  Double-click "run.bat" to start the app.
    echo.
) else (
    echo.
    echo [ERROR] Installation failed. Check the errors above.
)
pause
