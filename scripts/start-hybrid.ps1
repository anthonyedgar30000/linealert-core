param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$uiRoot = Join-Path $repoRoot "ui"
$capture = Join-Path $repoRoot "evidence\opcua\microsoft-opc-plc.jsonl"
$conditionEvents = Join-Path $repoRoot "examples\labeler_condition_drift_events.jsonl"
$conditionConfig = Join-Path $repoRoot "examples\labeler_demo_config.json"
$conditionBindings = Join-Path $repoRoot "examples\condition_signal_bindings.json"
$startedBridge = $null

if (-not (Test-Path $python)) {
    throw "Python environment missing. Run: py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e '.[opcua]'"
}

$bridgeReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8765 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $bridgeReady) {
    $startedBridge = Start-Process -FilePath $python `
        -ArgumentList `
            "-m", "linealert_core.opcua_bridge", `
            "--operating-mode", "demo_emulation", `
            "--capture-jsonl", $capture, `
            "--condition-events-jsonl", $conditionEvents, `
            "--condition-config", $conditionConfig, `
            "--condition-bindings", $conditionBindings, `
            "--condition-replay-seconds", "0.25" `
        -WorkingDirectory $repoRoot `
        -PassThru
    Start-Sleep -Seconds 2
}

Push-Location $uiRoot
try {
    if (-not $SkipInstall) {
        npm install
    }
    Write-Host "LineAlert hybrid interface: http://localhost:8766" -ForegroundColor Cyan
    Write-Host "Evidence bridge: http://localhost:8765/api/telemetry" -ForegroundColor DarkCyan
    Write-Host "Condition evidence: http://localhost:8765/api/condition" -ForegroundColor DarkCyan
    npm run dev
}
finally {
    Pop-Location
    if ($null -ne $startedBridge -and -not $startedBridge.HasExited) {
        Stop-Process -Id $startedBridge.Id
    }
}
