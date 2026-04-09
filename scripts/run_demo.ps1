$scriptRoot = $PSScriptRoot
$repoRoot = Split-Path -Parent $scriptRoot

$backendScript = Join-Path $scriptRoot "run_backend.ps1"
$uiScript = Join-Path $scriptRoot "run_ui.ps1"

Start-Process -FilePath "pwsh" -ArgumentList @("-NoExit", "-File", $backendScript) -WorkingDirectory $repoRoot | Out-Null
Start-Process -FilePath "pwsh" -ArgumentList @("-NoExit", "-File", $uiScript) -WorkingDirectory $repoRoot | Out-Null

Write-Host "Backend starting at http://127.0.0.1:2026"
Write-Host "UI starting at http://127.0.0.1:3000"
