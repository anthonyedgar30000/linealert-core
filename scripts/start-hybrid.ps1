param(
    [switch]$SkipInstall,
    [switch]$SkipHistorian
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$uiRoot = Join-Path $repoRoot "ui"
$capture = Join-Path $repoRoot "evidence\opcua\microsoft-opc-plc.jsonl"
$conditionEvents = Join-Path $repoRoot "examples\labeler_condition_drift_events.jsonl"
$conditionConfig = Join-Path $repoRoot "examples\labeler_demo_config.json"
$conditionBindings = Join-Path $repoRoot "examples\condition_signal_bindings.json"
$historianCompose = Join-Path $repoRoot "docker-compose.historian.yml"
$historianDsn = "postgresql://linealert:linealert_dev@127.0.0.1:5433/linealert"
$startedBridge = $null
$startedHistorian = $null

if (-not (Test-Path $python)) {
    throw "Python environment missing. Run: py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e '.[opcua,historian]'"
}

$uiReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8766 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($uiReady) {
    throw "Port 8766 is already in use. Stop the existing LineAlert UI before starting another hybrid session."
}

if (-not $SkipHistorian) {
    & $python -c "import psycopg" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Historian extra missing. Run: .\.venv\Scripts\python.exe -m pip install -e '.[opcua,historian]'"
    }
    docker compose -f $historianCompose up -d
    $databaseReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $databaseReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($databaseReady) { break }
        Start-Sleep -Seconds 1
    }
    if (-not $databaseReady) {
        throw "TimescaleDB historian did not become ready on localhost:5433."
    }
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

if (-not $SkipHistorian) {
    $historianReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8767 -InformationLevel Quiet -WarningAction SilentlyContinue
    if (-not $historianReady) {
        $startedHistorian = Start-Process -FilePath $python `
            -ArgumentList `
                "-m", "linealert_core.historian_service", `
                "--dsn", $historianDsn, `
                "--source-base-url", "http://127.0.0.1:8765", `
                "--episode-id", "condition-runtime-replay" `
            -WorkingDirectory $repoRoot `
            -PassThru
        Start-Sleep -Seconds 2
    }
}

Push-Location $uiRoot
try {
    if (-not $SkipInstall) {
        npm install
    }
    Write-Host "LineAlert hybrid interface: http://localhost:8766" -ForegroundColor Cyan
    Write-Host "Evidence bridge: http://localhost:8765/api/telemetry" -ForegroundColor DarkCyan
    Write-Host "Condition evidence: http://localhost:8765/api/condition" -ForegroundColor DarkCyan
    if (-not $SkipHistorian) {
        Write-Host "Shared historian: http://localhost:8767/api/status" -ForegroundColor DarkGreen
        Write-Host "Condition history: http://localhost:8767/api/history/conditions" -ForegroundColor DarkGreen
    }
    npm run dev
}
finally {
    Pop-Location
    if ($null -ne $startedHistorian -and -not $startedHistorian.HasExited) {
        Stop-Process -Id $startedHistorian.Id
    }
    if ($null -ne $startedBridge -and -not $startedBridge.HasExited) {
        Stop-Process -Id $startedBridge.Id
    }
}
