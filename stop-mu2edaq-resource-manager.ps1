<#
.SYNOPSIS
    Standardized Mu2e control-room stop script (PowerShell port of
    stop-mu2edaq-resource-manager.sh + scripts/stop_server.sh). Stops the
    daemon-mode Resource Manager via its PID file: graceful close, then a forced
    kill after a timeout, and clean up the PID file.

    Honors RM_RUN_DIR / RM_PIDFILE (defaults to run\resource-manager.pid).
#>
[CmdletBinding()]
param(
    [int]$Timeout = 10
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

$RunDir  = if ($env:RM_RUN_DIR) { $env:RM_RUN_DIR } else { Join-Path $Here 'run' }
$PidFile = if ($env:RM_PIDFILE) { $env:RM_PIDFILE } else { Join-Path $RunDir 'resource-manager.pid' }

function Test-ProcessAlive([int]$ProcId) {
    return [bool](Get-Process -Id $ProcId -ErrorAction SilentlyContinue)
}

if (-not (Test-Path $PidFile)) {
    Write-Host "Resource Manager not running (no pidfile: $PidFile)"
    exit 0
}

$ProcId = [int]((Get-Content $PidFile -Raw).Trim())
if (-not (Test-ProcessAlive $ProcId)) {
    Write-Host "Resource Manager not running (stale pid $ProcId); cleaning up"
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    exit 0
}

Write-Host "Stopping Mu2e DAQ Resource Manager (PID $ProcId)..."
$proc = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
if ($proc) { $proc.CloseMainWindow() | Out-Null }
for ($i = 0; $i -lt $Timeout; $i++) {
    if (-not (Test-ProcessAlive $ProcId)) { break }
    Start-Sleep -Seconds 1
}
if (Test-ProcessAlive $ProcId) {
    Write-Host "did not exit within ${Timeout}s; forcing"
    Stop-Process -Id $ProcId -Force -ErrorAction SilentlyContinue
}
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Write-Host 'Resource Manager stopped'
