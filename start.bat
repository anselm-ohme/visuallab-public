@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  VisualLab launcher
echo ============================================================

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo [error] Could not create venv. Is Python 3 installed? ^(try: py -3 --version^)
        pause
        exit /b 1
    )
)

if not exist ".venv\Lib\site-packages\flask" (
    echo [setup] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [error] pip install failed. See output above.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    echo [setup] Copying .env.example -> .env
    copy /Y .env.example .env >nul
)

echo [run] Starting VisualLab at http://127.0.0.1:5000
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py

endlocal
