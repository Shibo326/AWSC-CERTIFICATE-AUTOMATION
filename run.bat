@echo off
title Prototype Cert Automation
echo.
echo  ================================
echo   Prototype Cert Automation
echo   by AWS CLOUD CLUB STI GLOBAL
echo  ================================
echo.
echo  Starting app...
echo  (Browser will open automatically)
echo.
echo  Press Ctrl+C to stop the server.
echo.

REM Check if Python is available
py --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
py -c "import streamlit" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing dependencies...
    py -m pip install -r requirements.txt
)

REM Run Streamlit
py -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
pause
