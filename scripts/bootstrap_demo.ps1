$scriptRoot = $PSScriptRoot

& (Join-Path $scriptRoot "bootstrap_backend.ps1")
& (Join-Path $scriptRoot "bootstrap_ui.ps1")
