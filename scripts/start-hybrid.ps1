param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$uiRoot = Join-Path $repoRoot "ui"
$capture = Join-Path $repoRoot "evidence\opcua\microsoft-opc-plc.jsonl"
$startedBridge = $null

if (-not (Test-Path $python)) {
    throw "Python environment missing. Run: py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e '.[opcua]'"
}

$bridgeReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8765 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $bridgeReady) {
    $startedBridge = Start-Process -FilePath $python `
        -ArgumentList "-m", "linealert_core.opcua_bridge", "--capture-jsonl", $capture `
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
    npm run dev
}
finally {
    Pop-Location
    if ($null -ne $startedBridge -and -not $startedBridge.HasExited) {
        Stop-Process -Id $startedBridge.Id
    }
}
