param(
  [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\release\runtime")
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
python -m PyInstaller --noconfirm --clean --onefile --name ecomic-backend --paths $root --distpath $OutputDirectory --workpath (Join-Path $root "build\pyinstaller") --specpath (Join-Path $root "build\pyinstaller") --collect-data agent_backend --collect-all duckdb --collect-all numpy --collect-all scipy --collect-all sklearn --collect-all pyarrow (Join-Path $root "scripts\ecomic_backend_entry.py")