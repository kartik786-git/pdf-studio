@echo off
:: PDF Studio Launcher
:: Double‑click this file to start the PDF Studio API locally.

cd /d "%~dp0"

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Start the FastAPI application
echo Starting PDF Studio...
python app.py