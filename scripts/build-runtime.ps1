<#
.SYNOPSIS
  Unified Runtime build script.
  This is the ONLY script that CI, Release and local development should call
  to build the complete ECOMIC desktop runtime.

.DESCRIPTION
  Executes the full runtime build pipeline in strict order:
    1. Bootstrap Pi Runtime (clone + pin + build)
    2. Build Python Backend (PyInstaller -> ecomic-backend.exe)
    3. Build Agent Runtime (assemble release/runtime/ecomic-agent/)
    4. Generate runtime-manifest.json
    5. Verify Runtime (check all critical files exist)

  No step may run before its prerequisites are satisfied.

.PARAMETER OutputDirectory
  Override the runtime output directory. Defaults to <repo>/release/runtime/ecomic-agent.

.PARAMETER SkipPiBootstrap
  Skip Pi bootstrap (use when vendor/pi is already built).

.EXAMPLE
  ./scripts/build-runtime.ps1
#>
param(
  [string]$OutputDirectory,
  [switch]$SkipPiBootstrap
)
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repoRoot "release\runtime\ecomic-agent" }

Write-Host "=== ECOMIC Runtime Build ===" -ForegroundColor Cyan
Write-Host "  Output: $OutputDirectory"
Write-Host ""

# --- Step 1: Bootstrap Pi ---
if ($SkipPiBootstrap) {
  Write-Host "[1/5] Skipping Pi bootstrap (--SkipPiBootstrap)" -ForegroundColor DarkYellow
} else {
  Write-Host "[1/5] Bootstrapping Pi Runtime..." -ForegroundColor Yellow
  & (Join-Path $PSScriptRoot "bootstrap-pi-runtime.ps1")
  if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: Pi bootstrap failed"; exit 1 }
}

# --- Step 2: Build Python Backend ---
Write-Host "[2/5] Building Python Backend..." -ForegroundColor Yellow
& (Join-Path $PSScriptRoot "build-backend.ps1")
if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: Backend build failed"; exit 1 }

# --- Step 3: Build Agent Runtime ---
Write-Host "[3/5] Building Agent Runtime..." -ForegroundColor Yellow
& (Join-Path $PSScriptRoot "build-agent-runtime.ps1") -OutputDirectory $OutputDirectory
if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: Agent runtime build failed"; exit 1 }

# --- Step 4: Generate runtime-manifest.json ---
Write-Host "[4/5] Generating runtime-manifest.json..." -ForegroundColor Yellow
$piVersionFile = Join-Path $repoRoot ".pi-version"
$piCommit = (Get-Content $piVersionFile -Raw).Trim()

# Read app version from tauri.conf.json
$tauriConf = Get-Content (Join-Path $repoRoot "desktop\src-tauri\tauri.conf.json") -Raw | ConvertFrom-Json
$appVersion = $tauriConf.version

# Detect Node version
$nodeVersion = try { (node --version 2>$null).Trim() } catch { "unknown" }

# Detect backend version
$backendExe = Join-Path $OutputDirectory "ecomic-backend.exe"
$backendVersion = "unknown"
if (Test-Path $backendExe) {
  $fileInfo = Get-Item $backendExe
  $backendVersion = $fileInfo.LastWriteTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$platform = "windows-$([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture)"

$manifest = @{
  app_version      = $appVersion
  pi_commit        = $piCommit
  node_version     = $nodeVersion
  backend_version  = $backendVersion
  platform         = $platform.ToLower()
  build_time       = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$manifestPath = Join-Path $OutputDirectory "runtime-manifest.json"
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding UTF8
Write-Host "  Manifest written to $manifestPath" -ForegroundColor Green

# --- Step 5: Verify Runtime ---
Write-Host "[5/5] Verifying runtime..." -ForegroundColor Yellow
$requiredFiles = @(
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
foreach ($rel in $requiredFiles) {
  $full = Join-Path $OutputDirectory $rel
  if (-not (Test-Path $full)) { $missing += $rel }
}
if ($missing.Count -gt 0) {
  Write-Error "FAIL: Missing runtime files:`n  $($missing -join "`n  ")"
  exit 1
}

Write-Host ""
Write-Host "=== PASS: ECOMIC Runtime is ready ===" -ForegroundColor Cyan
Write-Host "  Output:     $OutputDirectory"
Write-Host "  App:        v$appVersion"
Write-Host "  Pi commit:  $piCommit"
Write-Host "  Node:       $nodeVersion"
Write-Host "  Platform:   $($platform.ToLower())"
Write-Host ""
