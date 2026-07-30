<#
.SYNOPSIS
    Standardized Mu2e control-room start script (PowerShell port of
    start-mu2edaq-resource-manager.sh + scripts/start_server.sh) for the
    Resource Manager server.

.DESCRIPTION
    Maps CRS_PORT_HTTP -> RM_PORT and starts the FastAPI server. POSIX daemon
    mode uses nohup; on Windows the server is backgrounded via Start-Process
    with a PID file so stop-mu2edaq-resource-manager.ps1 can stop it.

    Honors RM_HOST, RM_PORT, RM_CONFIG, RM_STATE, RM_RUN_DIR, RM_PIDFILE,
    RM_LOG, RM_VENV. Port precedence: CRS_PORT_HTTP > RM_PORT > 8080.

.PARAMETER ServerArgs
    Extra arguments forwarded to the server (override the environment values).
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ServerArgs
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

$Host_    = if ($env:RM_HOST)   { $env:RM_HOST } else { '127.0.0.1' }
$Port     = if ($env:CRS_PORT_HTTP) { $env:CRS_PORT_HTTP } elseif ($env:RM_PORT) { $env:RM_PORT } else { '8080' }
$Config   = if ($env:RM_CONFIG) { $env:RM_CONFIG } else { Join-Path $Here 'config\resources.yaml' }
$State    = if ($env:RM_STATE)  { $env:RM_STATE }  else { Join-Path $Here 'config\state.json' }
$RunDir   = if ($env:RM_RUN_DIR){ $env:RM_RUN_DIR }else { Join-Path $Here 'run' }
$PidFile  = if ($env:RM_PIDFILE){ $env:RM_PIDFILE }else { Join-Path $RunDir 'resource-manager.pid' }
$LogFile  = if ($env:RM_LOG)    { $env:RM_LOG }    else { Join-Path $RunDir 'resource-manager.log' }
$VenvDir  = if ($env:RM_VENV)   { $env:RM_VENV }   else { Join-Path $Here 'venv' }

$VenvPy = Join-Path $VenvDir 'Scripts\python.exe'
if (-not (Test-Path $VenvPy)) {
    Write-Error "virtual environment not found in $VenvDir. Run .\bootstrap.ps1 first."
    exit 1
}

function Test-ProcessAlive([int]$ProcId) {
    return [bool](Get-Process -Id $ProcId -ErrorAction SilentlyContinue)
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
if (Test-Path $PidFile) {
    $old = (Get-Content $PidFile -Raw).Trim()
    if ($old -match '^\d+$' -and (Test-ProcessAlive ([int]$old))) {
        Write-Error "server already running (PID $old, pidfile $PidFile)."
        exit 1
    }
    Write-Host "  Removing stale pidfile $PidFile."
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

$server = Join-Path $Here 'server\mu2e-resource-manager.py'
$argList = @($server, '--host', $Host_, '--port', "$Port", '--config', $Config, '--state', $State)
if ($ServerArgs) { $argList += $ServerArgs }

Write-Host 'Starting Mu2e DAQ Resource Manager'
Write-Host "  Listen: http://${Host_}:${Port}"
Write-Host "  PID:    $PidFile"
Write-Host "  Log:    $LogFile"
$proc = Start-Process -FilePath $VenvPy -ArgumentList $argList -WorkingDirectory $Here `
    -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err" `
    -WindowStyle Hidden -PassThru
Set-Content -Path $PidFile -Value $proc.Id -Encoding ascii
Write-Host "Started in background (PID $($proc.Id)). Stop with .\stop-mu2edaq-resource-manager.ps1"
