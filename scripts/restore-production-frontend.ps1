$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$desktop = Join-Path $repository "desktop"
$oldE2e = $env:VITE_E2E_WDIO
try {
    Remove-Item Env:VITE_E2E_WDIO -ErrorAction SilentlyContinue
    Push-Location $desktop
    try { npm run build } finally { Pop-Location }
    & (Join-Path $repository "scripts/verify-production-bundle.ps1")
} finally {
    if ($null -eq $oldE2e) { Remove-Item Env:VITE_E2E_WDIO -ErrorAction SilentlyContinue } else { $env:VITE_E2E_WDIO = $oldE2e }
}