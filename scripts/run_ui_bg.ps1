$repoRoot = Split-Path -Parent $PSScriptRoot
$uiRoot = Join-Path $repoRoot "ui"
$outLog = Join-Path $repoRoot "ui-start.out.log"
$errLog = Join-Path $repoRoot "ui-start.err.log"

if (Test-Path $outLog) { Remove-Item $outLog -Force }
if (Test-Path $errLog) { Remove-Item $errLog -Force }

$env:LANGGRAPH_API_URL = "http://127.0.0.1:2026"
$env:LANGGRAPH_API_KEY = ""
$env:NEXT_PUBLIC_ASSISTANT_ID = "battery_lab"
$env:PORT = "3000"

Start-Process `
  -FilePath "cmd.exe" `
  -ArgumentList @(
    "/c",
    "cd /d `"$uiRoot`" && npm run dev"
  ) `
  -WorkingDirectory $uiRoot `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog `
  -WindowStyle Hidden
