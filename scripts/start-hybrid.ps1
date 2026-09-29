param(
    [switch]$SkipInstall,
    [switch]$SkipHistorian,
    [switch]$UseEmulatedHistorian
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$uiRoot = Join-Path $repoRoot "ui"
$capture = Join-Path $repoRoot "evidence\opcua\microsoft-opc-plc.jsonl"
$conditionEvents = Join-Path $repoRoot "examples\labeler_condition_drift_events.jsonl"
$conditionConfig = Join-Path $repoRoot "examples\labeler_demo_config.json"
$conditionBindings = Join-Path $repoRoot "examples\condition_signal_bindings.json"
$serviceCaseSeed = Join-Path $repoRoot "examples\speedway_service_case_workspace_seed_v1.json"
if ($env:LOCALAPPDATA) {
    $serviceCaseDataDir = Join-Path $env:LOCALAPPDATA "LineAlert\service-cases-v1"
    $emulatedHistorianDb = Join-Path $env:LOCALAPPDATA "LineAlert\historian-emulator-v1\historian.sqlite3"
}
else {
    $serviceCaseDataDir = Join-Path $repoRoot ".runtime\service-cases-v1"
    $emulatedHistorianDb = Join-Path $repoRoot ".runtime\historian-emulator-v1\historian.sqlite3"
}
$historianCompose = Join-Path $repoRoot "docker-compose.historian.yml"
$historianDsn = "postgresql://linealert:linealert_dev@127.0.0.1:5433/linealert"
$startedBridge = $null
$startedHistorian = $null
$startedServiceCase = $null

if (-not (Test-Path $python)) {
    throw "Python environment missing. Run: py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e '.[opcua,historian]'"
}

if ($SkipHistorian -and $UseEmulatedHistorian) {
    throw "Choose either -SkipHistorian or -UseEmulatedHistorian, not both."
}

$uiReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8766 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($uiReady) {
    throw "Port 8766 is already in use. Stop the existing LineAlert UI before starting another hybrid session."
}

if (-not $SkipHistorian -and -not $UseEmulatedHistorian) {
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

$serviceCaseReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8768 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $serviceCaseReady) {
    $startedServiceCase = Start-Process -FilePath $python `
        -ArgumentList `
            "-m", "linealert_core.service_case_service", `
            "--data-dir", $serviceCaseDataDir, `
            "--seed-service-case", $serviceCaseSeed `
        -WorkingDirectory $repoRoot `
        -PassThru
    Start-Sleep -Seconds 1
    $serviceCaseReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8768 -InformationLevel Quiet -WarningAction SilentlyContinue
    if (-not $serviceCaseReady) {
        throw "Service-case persistence did not become ready on localhost:8768."
    }
}

if ($UseEmulatedHistorian) {
    $historianReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8767 -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($historianReady) {
        try {
            $historianStatus = Invoke-RestMethod -Uri "http://127.0.0.1:8767/api/status" -TimeoutSec 2
            if (-not $historianStatus.emulated) {
                throw "Port 8767 is occupied by a non-emulated historian."
            }
        }
        catch {
            throw "Port 8767 is occupied but the emulated historian identity could not be verified."
        }
    }
    else {
        $startedHistorian = Start-Process -FilePath $python `
            -ArgumentList `
                "-m", "linealert_core.historian_emulator_service", `
                "--database", $emulatedHistorianDb, `
                "--config", $conditionConfig, `
                "--interval-seconds", "2", `
                "--seed-cycles", "36" `
            -WorkingDirectory $repoRoot `
            -PassThru
        Start-Sleep -Seconds 1
        $historianReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8767 -InformationLevel Quiet -WarningAction SilentlyContinue
        if (-not $historianReady) {
            throw "Emulated historian did not become ready on localhost:8767."
        }
    }
}
elseif (-not $SkipHistorian) {
    $historianReady = Test-NetConnection -ComputerName 127.0.0.1 -Port 8767 -InformationLevel Quiet -WarningAction SilentlyContinue
    if (-not $historianReady) {
        $startedHistorian = Start-Process -FilePath $python `
            -ArgumentList `
                "-m", "linealert_core.historian_service", `
                "--dsn", $historianDsn, `
                "--source-base-url", "http://127.0.0.1:8765", `
                "--episode-id", "condition-runtime-replay", `
                "--condition-config", $conditionConfig `
            -WorkingDirectory $repoRoot `
            -PassThru
        Start-Sleep -Seconds 2
    }
}

$lanDevOrigin = $env:LINEALERT_UI_ALLOWED_DEV_ORIGIN
if (-not $lanDevOrigin) {
    $defaultRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric, InterfaceMetric |
        Select-Object -First 1
    if ($null -ne $defaultRoute) {
        $lanDevOrigin = Get-NetIPAddress -InterfaceIndex $defaultRoute.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.IPAddress -ne "127.0.0.1" -and
                $_.IPAddress -notlike "169.254.*"
            } |
            Select-Object -ExpandProperty IPAddress -First 1
    }
}
if ($lanDevOrigin) {
    $env:LINEALERT_UI_ALLOWED_DEV_ORIGIN = $lanDevOrigin
}

Push-Location $uiRoot
try {
    if (-not $SkipInstall) {
        npm install
    }
    Write-Host "LineAlert hybrid interface: http://localhost:8766" -ForegroundColor Cyan
    if ($lanDevOrigin) {
        Write-Host "Allowed Next.js LAN dev origin: $lanDevOrigin" -ForegroundColor DarkCyan
    }
    Write-Host "Evidence bridge: http://localhost:8765/api/telemetry" -ForegroundColor DarkCyan
    Write-Host "Condition evidence: http://localhost:8765/api/condition" -ForegroundColor DarkCyan
    Write-Host "Service-case persistence: http://localhost:8768/api/status" -ForegroundColor DarkMagenta
    Write-Host "Service-case data: $serviceCaseDataDir" -ForegroundColor DarkMagenta
    if ($UseEmulatedHistorian) {
        Write-Host "Emulated historian: http://localhost:8767/api/status" -ForegroundColor DarkGreen
        Write-Host "Emulated historian data: $emulatedHistorianDb" -ForegroundColor DarkGreen
        Write-Host "Functional/temporal history: http://localhost:8767/api/history/functional-temporal" -ForegroundColor DarkGreen
        Write-Host "Boundary: emulated historian != TimescaleDB != verified physical history" -ForegroundColor DarkYellow
    }
    elseif (-not $SkipHistorian) {
        Write-Host "Shared historian: http://localhost:8767/api/status" -ForegroundColor DarkGreen
        Write-Host "Condition history: http://localhost:8767/api/history/conditions" -ForegroundColor DarkGreen
        Write-Host "Persistent localization: http://localhost:8767/api/history/conditions/localize" -ForegroundColor DarkGreen
    }
    npm run dev
}
finally {
    Pop-Location
    if ($null -ne $startedHistorian -and -not $startedHistorian.HasExited) {
        Stop-Process -Id $startedHistorian.Id
    }
    if ($null -ne $startedServiceCase -and -not $startedServiceCase.HasExited) {
        Stop-Process -Id $startedServiceCase.Id
    }
    if ($null -ne $startedBridge -and -not $startedBridge.HasExited) {
        Stop-Process -Id $startedBridge.Id
    }
}
