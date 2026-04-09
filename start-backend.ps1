$repoRoot = $PSScriptRoot
$tempDir = Join-Path $repoRoot ".tmp"
$runnerScript = Join-Path $repoRoot "scripts\run_backend.ps1"
$outLog = Join-Path $tempDir "backend-start.out.log"
$errLog = Join-Path $tempDir "backend-start.err.log"

New-Item -ItemType Directory -Force $tempDir | Out-Null

if (-not (Test-Path $runnerScript)) {
  throw "Backend runner script not found at $runnerScript"
}

if (Test-Path $outLog) { Remove-Item $outLog -Force }
if (Test-Path $errLog) { Remove-Item $errLog -Force }

$powerShellExe = $null

try {
  $powerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
} catch {
  try {
    $powerShellExe = (Get-Command pwsh.exe -ErrorAction Stop).Source
  } catch {
    throw "Unable to find powershell.exe or pwsh.exe on PATH."
  }
}

Start-Process `
  -FilePath $powerShellExe `
  -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $runnerScript
  ) `
  -WorkingDirectory $repoRoot `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog `
  -WindowStyle Hidden
