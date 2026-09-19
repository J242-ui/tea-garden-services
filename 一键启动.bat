@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo    Tea Garden Weather Service - Quick Start
echo ============================================
echo.

rem --- detect python with venv support ---
set "PY=python"
python -m venv --help >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 goto :nopython
    py -3 -m venv --help >nul 2>&1
    if errorlevel 1 goto :nopython
    set "PY=py -3"
)

rem --- 1. create venv if missing ---
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
) else (
    echo [1/3] Virtual environment found.
)

rem --- 2. install dependencies if missing ---
".venv\Scripts\python.exe" -c "import streamlit, requests, pandas, plotly, dotenv" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :fail
) else (
    echo [2/3] Dependencies ready.
)

rem --- 3. start app ---
echo [3/3] Starting app... browser opens at http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless false
goto :end

:nopython
echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
pause
exit /b 1

:fail
echo.
echo [ERROR] Startup failed. Please check the messages above.
pause
exit /b 1

:end
pause
exit /b 0
