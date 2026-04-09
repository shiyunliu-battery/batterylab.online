$repoRoot = Split-Path -Parent $PSScriptRoot
$uiRoot = Join-Path $repoRoot "ui"

Set-Location $uiRoot
corepack yarn install --ignore-engines
