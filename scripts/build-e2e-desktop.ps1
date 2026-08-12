$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$desktop = Join-Path $repository "desktop"
$capabilityPath = Join-Path $desktop "src-tauri/capabilities/default.json"
$indexPath = Join-Path $desktop "index.html"
$configPath = Join-Path $desktop "src-tauri/tauri.conf.json"
$targetDir = Join-Path $desktop "src-tauri/target-e2e"
$originalCapability = [IO.File]::ReadAllBytes($capabilityPath)
$originalIndex = [IO.File]::ReadAllBytes($indexPath)
$originalConfig = [IO.File]::ReadAllBytes($configPath)
$oldE2e = $env:VITE_E2E_WDIO
$oldTarget = $env:CARGO_TARGET_DIR
try {
    $capability = [Text.Encoding]::UTF8.GetString($originalCapability) | ConvertFrom-Json
    if (@($capability.permissions) -notcontains "wdio:default") { $capability.permissions = @($capability.permissions) + "wdio:default" }
    [IO.File]::WriteAllText($capabilityPath, ($capability | ConvertTo-Json -Depth 20 -Compress), [Text.UTF8Encoding]::new($false))
    $index = [Text.Encoding]::UTF8.GetString($originalIndex)
    $marker = '<script type="module">import "@wdio/tauri-plugin";</script>'
    if ($index -notlike "*$marker*") { $index = $index.Replace('</head>', "  $marker`n  </head>") }
    [IO.File]::WriteAllText($indexPath, $index, [Text.UTF8Encoding]::new($false))
    $config = [Text.Encoding]::UTF8.GetString($originalConfig) | ConvertFrom-Json
    $config.build.PSObject.Properties.Remove("devUrl")
    [IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
    $env:VITE_E2E_WDIO = "true"
    $env:CARGO_TARGET_DIR = $targetDir
    Push-Location $desktop
    try { npm run build; & "$env:USERPROFILE\.cargo\bin\cargo.exe" build --release --manifest-path src-tauri/Cargo.toml --features e2e } finally { Pop-Location }
} finally {
    [IO.File]::WriteAllBytes($capabilityPath, $originalCapability)
    [IO.File]::WriteAllBytes($indexPath, $originalIndex)
    [IO.File]::WriteAllBytes($configPath, $originalConfig)
    if ($null -eq $oldE2e) { Remove-Item Env:VITE_E2E_WDIO -ErrorAction SilentlyContinue } else { $env:VITE_E2E_WDIO = $oldE2e }
    if ($null -eq $oldTarget) { Remove-Item Env:CARGO_TARGET_DIR -ErrorAction SilentlyContinue } else { $env:CARGO_TARGET_DIR = $oldTarget }
}
$application = Join-Path $targetDir "release/ecomic-desktop.exe"
if (-not (Test-Path -LiteralPath $application)) { throw "E2E desktop binary was not produced: $application" }
Write-Output "E2E_DESKTOP_READY=$application"