param(
  [string]$Backend = (Join-Path $PSScriptRoot "..\release\runtime\ecomic-backend.exe"),
  [string]$WorkRoot = (Join-Path $PSScriptRoot "..\release\backend-exe-acceptance")
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path $WorkRoot -ErrorAction SilentlyContinue)
if (-not $root) { $root = New-Item -ItemType Directory -Path $WorkRoot }
$csv = Join-Path $root "smoke.csv"
$rows = "feature,decision,label,cost" + [Environment]::NewLine + ((0..79 | ForEach-Object { "$($_),$(if ($_ % 2) {'1'} else {'0'}),$(if ($_ % 3) {'1'} else {'0'}),1" }) -join [Environment]::NewLine)
[System.IO.File]::WriteAllText($csv, $rows, [System.Text.UTF8Encoding]::new($false))
$state = Join-Path $root "state"
$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = (Resolve-Path $Backend)
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$psi.Environment["PATH"] = "C:\Windows\System32;C:\Windows"
$psi.Environment["ECOMIC_STATE_DIR"] = $state
$process = [System.Diagnostics.Process]::new(); $process.StartInfo = $psi
if (-not $process.Start()) { throw "backend executable did not start" }
function Invoke-Backend([string]$Action, [hashtable]$Payload = @{}) {
  $line = @{ action = $Action; payload = $Payload } | ConvertTo-Json -Compress -Depth 8
  $process.StandardInput.WriteLine($line); $process.StandardInput.Flush()
  $response = $process.StandardOutput.ReadLine() | ConvertFrom-Json
  if ($response.status -ne "OK") { throw "backend $Action failed: $($response.message)" }
  if ($Action -eq "health_check") { return $response }
  return $response.result
}
try {
  $health = Invoke-Backend "health_check"
  $loaded = Invoke-Backend "load_dataset" @{ path = $csv }
  $session = $loaded.session_id
  $decision = Invoke-Backend "confirm_decision_mapping" @{ session_id=$session; decision_column="decision"; observed_values=@("1"); non_observed_values=@("0"); target_column="label"; cost_column="cost" }
  $null = Invoke-Backend "confirm_observation_action" @{ session_id=$session; reversible=$true; simulatable=$true; description="bundled offline replay" }
  $hypothesis = Invoke-Backend "create_hypothesis" @{ session_id=$session; content="Bundled backend smoke hypothesis" }
  $plan = Invoke-Backend "plan_experiment" @{ session_id=$session; hypothesis_id=$hypothesis.hypothesis_id; policy="Random"; budget=8; rounds=2 }
  $run = Invoke-Backend "run_experiment" @{ session_id=$session; plan_id=$plan.plan_id; policy="Random"; budget=8; seed=23; rounds=2 }
  [pscustomobject]@{ backend=$health.backend; session_id=$session; run_id=$run.run_id; rounds=$run.observations.Count; state_dir=$state; python_on_path=$false } | ConvertTo-Json -Compress
}
finally {
  try { $process.StandardInput.WriteLine('{"action":"shutdown","payload":{}}'); $process.StandardInput.Flush(); $null=$process.StandardOutput.ReadLine() } catch {}
  if (-not $process.WaitForExit(5000)) { $process.Kill() }
  $process.Dispose()
}