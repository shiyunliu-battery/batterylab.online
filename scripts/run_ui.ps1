$repoRoot = Split-Path -Parent $PSScriptRoot
$uiRoot = Join-Path $repoRoot "ui"

if (-not $env:LANGGRAPH_API_URL) {
    $env:LANGGRAPH_API_URL = "http://127.0.0.1:2026"
}

if (-not $env:LANGGRAPH_API_KEY) {
    $env:LANGGRAPH_API_KEY = ""
}

if (-not $env:NEXT_PUBLIC_ASSISTANT_ID) {
    $env:NEXT_PUBLIC_ASSISTANT_ID = "battery_lab"
}

if (-not $env:PORT) {
    $env:PORT = "3000"
}

Set-Location $uiRoot
$nextBin = Join-Path $uiRoot "node_modules\.bin\next.cmd"

if (-not (Test-Path $nextBin)) {
    throw "Next.js CLI not found at $nextBin"
}

& $nextBin dev --webpack --port $env:PORT
