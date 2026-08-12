<#
.SYNOPSIS
  Post-build release runtime verification.
  Verifies that the bundled runtime contains all required files and the manifest is valid.

.DESCRIPTION
  This script runs after the runtime is built but before the NSIS installer is created.
  It verifies:
    1. runtime-manifest.json exists and has required fields
    2. All critical runtime files are present
    3. Pi commit in manifest matches .pi-version
    4. Node.exe is functional
    5. Backend executable is present

.PARAMETER RuntimeDir
  The runtime directory to verify. Defaults to <repo>/release/runtime/ecomic-agent.

.EXAMPLE
  ./scripts/verify-release-runtime.ps1
#>
param(
  [string]$RuntimeDir
)
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $repoRoot "release\runtime\ecomic-agent" }

Write-Host "=== Release Runtime Verification ===" -ForegroundColor Cyan
Write-Host "  Runtime dir: $RuntimeDir"
Write-Host ""

if (-not (Test-Path $RuntimeDir)) {
  Write-Error "FAIL: Runtime directory does not exist: $RuntimeDir"
  exit 1
}

# --- 1. Verify runtime-manifest.json ---
Write-Host "[1/4] Verifying runtime-manifest.json..." -ForegroundColor Yellow
$manifestPath = Join-Path $RuntimeDir "runtime-manifest.json"
if (-not (Test-Path $manifestPath)) {
  Write-Error "FAIL: runtime-manifest.json not found"
  exit 1
}
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$requiredFields = @("app_version", "pi_commit", "node_version", "backend_version", "platform", "build_time")
foreach ($field in $requiredFields) {
  if (-not $manifest.$field) {
    Write-Error "FAIL: runtime-manifest.json missing field: $field"
    exit 1
  }
}
Write-Host "  Manifest fields: OK" -ForegroundColor Green

# --- 2. Verify Pi commit matches .pi-version ---
Write-Host "[2/4] Verifying Pi commit matches .pi-version..." -ForegroundColor Yellow
$piVersionFile = Join-Path $repoRoot ".pi-version"
if (Test-Path $piVersionFile) {
  $expectedCommit = (Get-Content $piVersionFile -Raw).Trim()
  $actualCommit = $manifest.pi_commit
  if ($expectedCommit -ne $actualCommit) {
    Write-Error "FAIL: Pi commit mismatch. Expected: $expectedCommit, Got: $actualCommit"
    exit 1
  }
  Write-Host "  Pi commit matches: $actualCommit" -ForegroundColor Green
} else {
  Write-Host "  .pi-version not found, skipping commit verification" -ForegroundColor DarkYellow
}

# --- 3. Verify all critical runtime files ---
Write-Host "[3/4] Verifying critical runtime files..." -ForegroundColor Yellow
$criticalFiles = @(
  "node.exe",
  "ecomic-backend.exe",
  "runtime-manifest.json",
  "agent\src\desktop-scientist-runner-v2.mjs",
  "agent\src\pi-connection-probe.mjs",
  "agent\src\connection-test-contract.mjs",
  "agent\src\check-pi-model.mjs",
  "vendor\pi\packages\agent\dist\index.js",
  "vendor\pi\packages\ai\dist\index.js",
  "vendor\pi\packages\ai\dist\compat.js",
  "vendor\pi\packages\ai\dist\models.js"
)
$missing = @()
foreach ($rel in $criticalFiles) {
  $full = Join-Path $RuntimeDir $rel
  if (-not (Test-Path $full)) { $missing += $rel }
}
if ($missing.Count -gt 0) {
  Write-Error "FAIL: Missing runtime files:`n  $($missing -join "`n  ")"
  exit 1
}
Write-Host "  All $($criticalFiles.Count) critical files present" -ForegroundColor Green

# --- 4. Verify node.exe is functional ---
Write-Host "[4/4] Verifying node.exe is functional..." -ForegroundColor Yellow
$nodeExe = Join-Path $RuntimeDir "node.exe"
$nodeVersion = try { & $nodeExe --version 2>$null } catch { $null }
if (-not $nodeVersion) {
  Write-Error "FAIL: node.exe is not functional"
  exit 1
}
Write-Host "  Node version: $nodeVersion" -ForegroundColor Green

Write-Host ""
Write-Host "=== PASS: Release Runtime is ready ===" -ForegroundColor Cyan
Write-Host "  App version:  $($manifest.app_version)"
Write-Host "  Pi commit:    $($manifest.pi_commit)"
Write-Host "  Node version: $($manifest.node_version)"
Write-Host "  Platform:     $($manifest.platform)"
Write-Host "  Build time:   $($manifest.build_time)"
Write-Host ""
