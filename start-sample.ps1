$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
$backendProcess = $null
try {
  if (-not (Test-Path .venv/Scripts/python.exe)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
  }
  $python = (Resolve-Path .venv/Scripts/python.exe).Path
  & $python -m pip install -r backend/requirements.txt
  if ($LASTEXITCODE -ne 0) { throw "Backend dependency install failed." }
  New-Item -ItemType Directory -Force .local | Out-Null
  $backendProcess = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory (Join-Path $PSScriptRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot '.local/api.out.log') -RedirectStandardError (Join-Path $PSScriptRoot '.local/api.err.log')
  Start-Sleep -Seconds 2
  if ($backendProcess.HasExited) { throw "The API could not start. Check .local/api.err.log and whether port 8000 is already occupied." }
  Push-Location frontend
  try {
    npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency install failed." }
    npm.cmd run dev
  } finally { Pop-Location }
} finally {
  if ($backendProcess -and -not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id }
  Pop-Location
}
