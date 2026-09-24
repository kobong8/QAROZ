param([string]$Python = "python", [switch]$SkipBrowser)
$ErrorActionPreference = "Stop"
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        & $Python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
        if ($LASTEXITCODE -ne 0) { throw "Python 3.12+ is required. Pass -Python with the path to python.exe." }
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
    }
    & .\.venv\Scripts\python.exe -m pip install -e ".[test]"
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    if (-not $SkipBrowser) {
        & .\.venv\Scripts\python.exe -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Chromium installation failed." }
    }
    Write-Host "QAROZ installed. Stop the old QAROZ server, then run scripts/start.ps1."
} finally { Pop-Location }
