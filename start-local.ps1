param([string]$SupabaseCli = "", [switch]$SetupOnly)
$ErrorActionPreference = "Stop"
$engineProcess = $null
Push-Location $PSScriptRoot
try {
  if ($SupabaseCli) { $SupabaseCli = (Resolve-Path -LiteralPath $SupabaseCli).Path }
  function Invoke-LocalCli {
    if ($SupabaseCli) { & $SupabaseCli @args } else { & npx.cmd --yes supabase@2.76.16 @args }
    if ($LASTEXITCODE -ne 0) { throw "Supabase failed. Check that Docker Desktop's Linux engine is running." }
  }
  New-Item -ItemType Directory -Path supabase/migrations -Force | Out-Null
  Copy-Item migrations/001_supabase_control_plane.sql supabase/migrations/00000000000001_control_plane.sql -Force
  Copy-Item migrations/002_live_engine.sql supabase/migrations/00000000000002_live_engine.sql -Force
  Copy-Item migrations/003_saved_queries.sql supabase/migrations/00000000000003_saved_queries.sql -Force
  Copy-Item migrations/004_dashboards.sql supabase/migrations/00000000000004_dashboards.sql -Force
  Copy-Item migrations/005_account_lifecycle.sql supabase/migrations/00000000000005_account_lifecycle.sql -Force
  Invoke-LocalCli start -x studio,realtime,edge-runtime,logflare,vector,supavisor,imgproxy,postgres-meta | Out-Null
  Invoke-LocalCli migration up --local
  # Forward only browser-safe values. Supabase status also contains admin secrets.
  $local = Invoke-LocalCli status --output json | Out-String | ConvertFrom-Json
  if (-not $local.API_URL -or -not $local.ANON_KEY) { throw "Could not read the local API URL and publishable key." }
  $env:VITE_SUPABASE_URL=$local.API_URL
  $env:VITE_SUPABASE_ANON_KEY=$local.ANON_KEY
  if (-not $local.DB_URL) { throw "Supabase did not return its local control-plane database URL." }
  New-Item -ItemType Directory -Force .local | Out-Null
  $keyPath = Join-Path $PSScriptRoot '.local/engine.key'
  if (-not (Test-Path -LiteralPath $keyPath)) {
    $keyBytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($keyBytes) } finally { $rng.Dispose() }
    $encoded = [Convert]::ToBase64String($keyBytes).Replace('+','-').Replace('/','_')
    $stream = [IO.File]::Open($keyPath,[IO.FileMode]::CreateNew)
    try {
      $bytes = [Text.Encoding]::ASCII.GetBytes($encoded)
      $stream.Write($bytes,0,$bytes.Length)
    } finally { $stream.Dispose() }
  }
  $targetList = if ($env:MORPHY_TARGET_HOSTS) { $env:MORPHY_TARGET_HOSTS } else { '127.0.0.1:5432' }
  $settingsFile = Join-Path $PSScriptRoot '.local/engine.env'
  @("MORPHY_SUPABASE_URL=$($local.API_URL)", "MORPHY_SUPABASE_PUBLIC_KEY=$($local.ANON_KEY)",
    "MORPHY_CONTROL_DSN=$($local.DB_URL)", "MORPHY_TARGET_HOSTS=$targetList",
    "MORPHY_ENCRYPTION_KEY=$([IO.File]::ReadAllText($keyPath).Trim())") | Set-Content -Encoding ascii $settingsFile
  if (-not $SetupOnly) {
    if (-not (Test-Path .venv/Scripts/python.exe)) {
      python -m venv .venv
      if ($LASTEXITCODE) { throw "Python setup failed." }
    }
    $python = (Resolve-Path .venv/Scripts/python.exe).Path
    & $python -m pip install -r backend/requirements.txt -e ./cli
    if ($LASTEXITCODE) { throw "Engine or CLI installation failed." }
    $engineProcess = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--app-dir','backend','--env-file','.local/engine.env','--host','127.0.0.1','--port','8000' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $PSScriptRoot '.local/engine.log')
    Start-Sleep -Seconds 2
    if ($engineProcess.HasExited) { throw "Engine startup failed. See .local/engine.log and check port 8000." }
  }
  Push-Location frontend
  try {
    & npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency install failed." }
    if ($SetupOnly) { Write-Output "Local Supabase is ready." }
    else { & npm.cmd run dev }
  } finally { Pop-Location }
} finally {
  if ($engineProcess -and -not $engineProcess.HasExited) { Stop-Process -Id $engineProcess.Id }
  Pop-Location
}

