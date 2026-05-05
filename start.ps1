# VisualPedia launcher (PowerShell)
# Run with:  .\start.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " VisualPedia launcher" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[setup] Creating virtual environment..." -ForegroundColor Yellow
    py -3 -m venv .venv
}

if (-not (Test-Path ".venv\Lib\site-packages\flask")) {
    Write-Host "[setup] Installing dependencies..." -ForegroundColor Yellow
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

if (-not (Test-Path ".env")) {
    Write-Host "[setup] Copying .env.example -> .env" -ForegroundColor Yellow
    Copy-Item .env.example .env
}

Write-Host "[run] Starting VisualPedia at http://127.0.0.1:5000" -ForegroundColor Green
Start-Process "http://127.0.0.1:5000"
.\.venv\Scripts\python.exe app.py
