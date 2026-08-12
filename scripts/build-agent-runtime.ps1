param(
  [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\release\runtime\ecomic-agent")
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory, (Join-Path $OutputDirectory "agent\src"), (Join-Path $OutputDirectory "vendor\pi") | Out-Null

# Resolve node.exe: prefer ECOMIC_NODE env, then (Get-Command node).Source, then system path
$nodeExe = $env:ECOMIC_NODE
if (-not $nodeExe) {
  $nodeCmd = try { (Get-Command node -ErrorAction Stop).Source } catch { $null }
  if ($nodeCmd) { $nodeExe = $nodeCmd }
}
if (-not $nodeExe) { $nodeExe = "C:\Program Files\nodejs\node.exe" }
if (-not (Test-Path $nodeExe)) {
  Write-Error "FAIL: node.exe not found. Set ECOMIC_NODE or ensure Node.js is on PATH."
  exit 1
}
Copy-Item $nodeExe (Join-Path $OutputDirectory "node.exe") -Force

Copy-Item (Join-Path $root "agent\src\desktop-scientist-runner-v2.mjs") (Join-Path $OutputDirectory "agent\src\desktop-scientist-runner-v2.mjs") -Force
Copy-Item (Join-Path $root "agent\src\pi-connection-probe.mjs") (Join-Path $OutputDirectory "agent\src\pi-connection-probe.mjs") -Force
Copy-Item (Join-Path $root "agent\src\connection-test-contract.mjs") (Join-Path $OutputDirectory "agent\src\connection-test-contract.mjs") -Force
Copy-Item (Join-Path $root "agent\src\check-pi-model.mjs") (Join-Path $OutputDirectory "agent\src\check-pi-model.mjs") -Force
Copy-Item (Join-Path $root "vendor\pi\packages") (Join-Path $OutputDirectory "vendor\pi\packages") -Recurse -Force
Copy-Item (Join-Path $root "vendor\pi\node_modules") (Join-Path $OutputDirectory "vendor\pi\node_modules") -Recurse -Force
$backendSrc = Join-Path $root "release\runtime\ecomic-backend.exe"
if (-not (Test-Path $backendSrc)) {
  Write-Error "FAIL: ecomic-backend.exe not found at $backendSrc. Run build-backend.ps1 first."
  exit 1
}
Copy-Item $backendSrc (Join-Path $OutputDirectory "ecomic-backend.exe") -Force
