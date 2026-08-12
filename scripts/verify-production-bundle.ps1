$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$cargo = Join-Path $repository "desktop/src-tauri/Cargo.toml"
$lib = Join-Path $repository "desktop/src-tauri/src/lib.rs"
$main = Join-Path $repository "desktop/src/main.tsx"
$capabilityPath = Join-Path $repository "desktop/src-tauri/capabilities/default.json"
$dist = Join-Path $repository "desktop/dist"
foreach ($target in @($cargo, $lib, $main, $capabilityPath)) { if (-not (Test-Path -LiteralPath $target)) { throw "Required production surface is missing: $target" } }
$cargoText = Get-Content -LiteralPath $cargo -Raw -Encoding UTF8
if ($cargoText -notmatch '(?m)^tauri-plugin-wdio\s*=\s*\{[^}]*optional\s*=\s*true[^}]*\}\s*$') { throw "WDIO must be declared only as an optional test dependency" }
if ($cargoText -notmatch '(?m)^e2e\s*=\s*\["dep:tauri-plugin-wdio"\]\s*$') { throw "WDIO must be gated behind the explicit e2e Cargo feature" }
$libText = Get-Content -LiteralPath $lib -Raw -Encoding UTF8
if ($libText -notmatch '(?s)#\[cfg\(feature\s*=\s*"e2e"\)\]\s*let builder = builder\.plugin\(tauri_plugin_wdio::init\(\)\);') { throw "WDIO Rust plugin registration is not gated by the e2e feature" }
$mainText = Get-Content -LiteralPath $main -Raw -Encoding UTF8
if ($mainText -notmatch 'VITE_E2E_WDIO' -or $mainText -match '@wdio/tauri-plugin') { throw "WDIO frontend bootstrap must be dynamically gated and absent from the production entry module" }
$capability = Get-Content -LiteralPath $capabilityPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($permission in @($capability.permissions)) { if ([string]$permission -match "wdio|webdriver") { throw "Production capability grants automation permission: $permission" } }
if (-not (Test-Path -LiteralPath $dist)) { throw "Production Vite output is missing: $dist" }
$bundleMatches = Get-ChildItem -LiteralPath $dist -Recurse -File | Select-String -Pattern "@wdio/tauri-plugin|wdioTauri|webdriver" -CaseSensitive:$false
if ($bundleMatches) { $locations = ($bundleMatches | Select-Object -First 5 | ForEach-Object { "$($_.Path):$($_.LineNumber)" }) -join ", "; throw "WDIO/WebDriver leaked into production Vite output: $locations" }
Write-Output "PRODUCTION_BUNDLE_WDIO_EXCLUSION_PASS"