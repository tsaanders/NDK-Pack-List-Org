@echo off
title NDK Pack List Org
cd /d "%~dp0"

if not exist "venv" (
    echo Setting up NDK Pack List Org the first time...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo Starting NDK Pack List Org...
echo Keep this window open while packing.
echo.
start "" "http://127.0.0.1:5000"
python app.py
pause
