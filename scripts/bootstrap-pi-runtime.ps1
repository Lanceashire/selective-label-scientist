<#
.SYNOPSIS
  Official Pi Runtime bootstrap script.
  Clones, pins, installs and builds the Pi monorepo at the exact commit
  declared in .pi-version.

.DESCRIPTION
  This is the ONLY supported way to prepare vendor/pi for ECOMIC.
  CI, Release, local development and Agent Runtime build must all call
  this script.  It is idempotent and safe to re-run.

  Steps:
    1. Read PI_COMMIT from .pi-version (single source of truth)
    2. If vendor/pi does not exist -> git clone
    3. Fetch the exact commit
    4. checkout --detach <commit>
    5. npm install --ignore-scripts
    6. npm run hydrate:model-data
    7. npm run build:offline
    8. Verify critical dist files exist
    9. Print PASS / FAIL

.PARAMETER PiRoot
  Override the vendor/pi directory. Defaults to <repo>/vendor/pi.

.EXAMPLE
  ./scripts/bootstrap-pi-runtime.ps1
#>
param(
  [string]$PiRoot
)
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $PiRoot) { $PiRoot = Join-Path $repoRoot "vendor\pi" }
$versionFile = Join-Path $repoRoot ".pi-version"

if (-not (Test-Path $versionFile)) {
  Write-Error "FAIL: .pi-version file not found at $versionFile"
  exit 1
}

$piCommit = (Get-Content $versionFile -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($piCommit)) {
  Write-Error "FAIL: .pi-version is empty."
  exit 1
}

Write-Host "=== Pi Runtime Bootstrap ===" -ForegroundColor Cyan
Write-Host "  Pi commit : $piCommit"
Write-Host "  Target    : $PiRoot"
Write-Host ""

# Step 1: Clone if needed
if (-not (Test-Path (Join-Path $PiRoot ".git"))) {
  Write-Host "[1/8] Cloning Pi repository..." -ForegroundColor Yellow
  $parentDir = Split-Path $PiRoot -Parent
  New-Item -ItemType Directory -Force -Path $parentDir | Out-Null
  git clone https://github.com/earendil-works/pi $PiRoot
  if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: git clone failed"; exit 1 }
} else {
  Write-Host "[1/8] vendor/pi already exists." -ForegroundColor Green
}

# Step 2: Fetch exact commit
Write-Host "[2/8] Fetching commit $piCommit ..." -ForegroundColor Yellow
git -C $PiRoot fetch --depth 1 origin $piCommit
if ($LASTEXITCODE -ne 0) {
  # Fallback: full fetch
  Write-Host "  Shallow fetch failed, trying full fetch..." -ForegroundColor DarkYellow
  git -C $PiRoot fetch origin
  if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: git fetch failed"; exit 1 }
}

# Step 3: Checkout exact commit
Write-Host "[3/8] Checking out $piCommit (detached)..." -ForegroundColor Yellow
git -C $PiRoot checkout --detach $piCommit
if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: git checkout failed"; exit 1 }

# Verify we're at the right commit
$currentHead = (git -C $PiRoot rev-parse HEAD).Trim()
if ($currentHead -ne $piCommit) {
  Write-Error "FAIL: HEAD ($currentHead) does not match .pi-version ($piCommit)"
  exit 1
}
Write-Host "  Verified: HEAD = $currentHead" -ForegroundColor Green

# Step 4: npm install
Write-Host "[4/8] npm install --ignore-scripts ..." -ForegroundColor Yellow
Push-Location $PiRoot
try {
  npm install --ignore-scripts
  if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: npm install failed"; exit 1 }
} finally { Pop-Location }

# Step 5: hydrate model data
Write-Host "[5/8] npm run hydrate:model-data ..." -ForegroundColor Yellow
Push-Location $PiRoot
try {
  npm run hydrate:model-data
  if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: hydrate:model-data failed"; exit 1 }
} finally { Pop-Location }

# Step 6: build offline
Write-Host "[6/8] npm run build:offline ..." -ForegroundColor Yellow
Push-Location $PiRoot
try {
  npm run build:offline
  if ($LASTEXITCODE -ne 0) { Write-Error "FAIL: build:offline failed"; exit 1 }
} finally { Pop-Location }

# Step 7: Verify critical dist files
Write-Host "[7/8] Verifying critical dist files..." -ForegroundColor Yellow
$criticalFiles = @(
  "packages\agent\dist\index.js",
  "packages\ai\dist\index.js",
  "packages\ai\dist\compat.js",
  "packages\ai\dist\models.js",
  "packages\coding-agent\dist\cli.js"
)
$missing = @()
foreach ($rel in $criticalFiles) {
  $full = Join-Path $PiRoot $rel
  if (-not (Test-Path $full)) {
    $missing += $rel
  }
}
if ($missing.Count -gt 0) {
  Write-Error "FAIL: Missing critical dist files:`n  $($missing -join "`n  ")"
  exit 1
}
Write-Host "  All $($criticalFiles.Count) critical files present." -ForegroundColor Green

# Step 8: Done
Write-Host "[8/8] Bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "=== PASS: Pi Runtime is ready at $PiRoot ===" -ForegroundColor Cyan
Write-Host "  Commit: $piCommit"
$nodeVersion = (node --version 2>$null)
if ($nodeVersion) { Write-Host "  Node  : $nodeVersion" }
Write-Host ""
