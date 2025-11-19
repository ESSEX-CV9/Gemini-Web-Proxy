@echo off
chcp 65001 >nul
REM Windows Intelligent Startup Script - Auto-detect and install dependencies

echo ==============================
echo Gemini Web Proxy
echo ==============================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.8+
    echo [TIP] Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python installed
python --version
echo.

REM Check dependencies
echo [CHECK] Checking dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [TIP] Dependencies not installed, starting auto-install...
    echo.
    
    REM Install Python dependencies
    echo [INSTALLING] Installing Python dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    
    REM Install Playwright browser
    echo.
    echo [INSTALLING] Installing Playwright browser...
    playwright install chromium
    if errorlevel 1 (
        echo [ERROR] Failed to install Playwright browser
        pause
        exit /b 1
    )
    
    echo.
    echo [OK] Dependencies installed successfully!
    echo.
) else (
    echo [OK] Dependencies already installed
    echo.
)

REM Start service
echo ==============================
echo [STARTING] Starting Gemini Proxy service...
echo ==============================
echo.
echo [TIP] Press Ctrl+C to stop service
echo.
echo [CONFIG]
echo    API Base URL: http://127.0.0.1:5000/v1
echo    Model: gemini-pro
echo.
echo ==============================
echo.

REM Start main program
python main.py

echo.
echo [INFO] Service stopped
pause