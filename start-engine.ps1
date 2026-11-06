$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
  if (-not (Test-Path backend/.env.local)) { throw "Copy backend/.env.example to backend/.env.local and configure the control plane, key and target allowlist." }
  if (-not (Test-Path .venv/Scripts/python.exe)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python environment creation failed." }
  }
  $python = (Resolve-Path .venv/Scripts/python.exe).Path
  & $python -m pip install -r backend/requirements.txt
  if ($LASTEXITCODE -ne 0) { throw "Dependency install failed." }
  & $python -m uvicorn app.main:app --app-dir backend --env-file backend/.env.local --host 127.0.0.1 --port 8000
} finally { Pop-Location }
