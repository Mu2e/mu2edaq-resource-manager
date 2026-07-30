<#
.SYNOPSIS
    Bootstrap the Mu2e DAQ Resource Manager on Windows (PowerShell port of
    bootstrap.sh -> scripts/bootstrap.sh): create the venv and install the
    Python dependencies.

.DESCRIPTION
    The C++ component (scripts/build_cpp.sh) is built separately with CMake and
    is not part of this bootstrap. RM_VENV overrides the venv location.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

$VenvDir = if ($env:RM_VENV) { $env:RM_VENV } else { Join-Path $Here 'venv' }

# Prefer 'python'; fall back to the py launcher ('python3' on Windows is the
# Microsoft Store alias stub, so it is not used here).
$Python = $env:PYTHON
if (-not $Python) {
    if (Get-Command python -ErrorAction SilentlyContinue) { $Python = 'python' }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { $Python = 'py' }
    else { Write-Error 'Python 3.9+ not found on PATH. Install it first.'; exit 1 }
}

& $Python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'
if ($LASTEXITCODE -ne 0) { Write-Error 'Python 3.9 or newer is required.'; exit 1 }

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment in $VenvDir"
    & $Python -m venv $VenvDir
}
$VenvPy = Join-Path $VenvDir 'Scripts\python.exe'
& $VenvPy -m pip install --upgrade pip | Out-Null
& $VenvPy -m pip install -r (Join-Path $Here 'requirements.txt')
# httpx is needed by Starlette's TestClient for the test-suite (see report).
& $VenvPy -m pip install httpx | Out-Null

Write-Host ''
Write-Host 'Bootstrap complete. Start with:  .\start-mu2edaq-resource-manager.ps1'
