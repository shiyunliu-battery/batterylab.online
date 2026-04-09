$repoRoot = Split-Path -Parent $PSScriptRoot
$tempDir = Join-Path $repoRoot ".tmp"

New-Item -ItemType Directory -Force $tempDir | Out-Null

$env:TEMP = $tempDir
$env:TMP = $tempDir
$env:PYTHONUTF8 = "1"

Set-Location $repoRoot
uv run langgraph dev --host 127.0.0.1 --port 2026 --no-browser --no-reload
