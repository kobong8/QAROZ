$ErrorActionPreference = "Stop"
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        throw "Run scripts/install.ps1 first."
    }
    & .\.venv\Scripts\python.exe app.py
    if ($LASTEXITCODE -ne 0) { throw "QAROZ failed to start. Check whether another QAROZ server is using port 8787." }
} finally { Pop-Location }
