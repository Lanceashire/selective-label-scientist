param(
  [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\release\runtime\ecomic-agent")
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory, (Join-Path $OutputDirectory "agent\src"), (Join-Path $OutputDirectory "vendor\pi") | Out-Null
Copy-Item "C:\Program Files\nodejs\node.exe" (Join-Path $OutputDirectory "node.exe") -Force
Copy-Item (Join-Path $root "agent\src\desktop-scientist-runner-v2.mjs") (Join-Path $OutputDirectory "agent\src\desktop-scientist-runner-v2.mjs") -Force
Copy-Item (Join-Path $root "agent\src\pi-connection-probe.mjs") (Join-Path $OutputDirectory "agent\src\pi-connection-probe.mjs") -Force
Copy-Item (Join-Path $root "agent\src\connection-test-contract.mjs") (Join-Path $OutputDirectory "agent\src\connection-test-contract.mjs") -Force
Copy-Item (Join-Path $root "vendor\pi\packages") (Join-Path $OutputDirectory "vendor\pi\packages") -Recurse -Force
Copy-Item (Join-Path $root "vendor\pi\node_modules") (Join-Path $OutputDirectory "vendor\pi\node_modules") -Recurse -Force
Copy-Item (Join-Path $root "release\runtime\ecomic-backend.exe") (Join-Path $OutputDirectory "ecomic-backend.exe") -Force