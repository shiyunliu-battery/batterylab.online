$repoRoot = Split-Path -Parent $PSScriptRoot
$tempDir = Join-Path $repoRoot ".tmp"

New-Item -ItemType Directory -Force $tempDir | Out-Null

$env:TEMP = $tempDir
$env:TMP = $tempDir

Set-Location $repoRoot
uv sync
