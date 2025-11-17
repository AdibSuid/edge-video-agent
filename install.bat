@echo off
REM Edge Agent Installation Script for Windows

echo ==========================================
echo Edge Agent - Installation Script
echo ==========================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo Python found!
echo.

REM Check for pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip is not installed
    echo Please reinstall Python with pip enabled
    pause
    exit /b 1
)

echo pip found!
echo.

REM Create virtual environment
echo Creating Python virtual environment...
python -m venv venv

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install Python dependencies
echo.
echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo ==========================================
echo Installation Complete!
echo ==========================================
echo.
echo IMPORTANT: You need to install GStreamer manually!
echo.
echo 1. Download GStreamer from: https://gstreamer.freedesktop.org/download/
echo    - Download "msvc runtime installer" (both runtime and development)
echo    - Install to default location (C:\gstreamer\1.0\msvc_x86_64\)
echo.
echo 2. Add GStreamer to PATH:
echo    - Add: C:\gstreamer\1.0\msvc_x86_64\bin
echo.
echo After installing GStreamer:
echo   1. Activate virtual environment: venv\Scripts\activate
echo   2. Edit config.yaml with your settings
echo   3. Run: python app.py
echo.
echo Web UI will be available at: http://localhost:5000
echo.
pause