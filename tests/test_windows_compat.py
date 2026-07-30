"""Windows compatibility tests.

Added in the windows-compat sweep. Locks in the .sh/.ps1 parity for the
standardized control-room scripts and parse-checks the PowerShell ports. The
FastAPI server (uvicorn) is cross-platform; the C++ build (scripts/build_cpp.sh)
and Linux env helpers (load_env.sh) are not ported.
"""
import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent

# Standardized control-room scripts that must ship both forms.
SCRIPT_STEMS = [
    "bootstrap",
    "start-mu2edaq-resource-manager",
    "stop-mu2edaq-resource-manager",
]

PWSH = shutil.which("pwsh") or shutil.which("powershell")


def test_standardized_scripts_have_both_forms():
    for stem in SCRIPT_STEMS:
        assert (REPO / f"{stem}.sh").is_file(), f"missing bash script: {stem}.sh"
        assert (REPO / f"{stem}.ps1").is_file(), f"missing PowerShell port: {stem}.ps1"


def test_cpp_and_env_scripts_are_not_ported():
    # C++ build (CMake) and the .env loader are Linux-oriented; no PowerShell.
    for rel in ("scripts/build_cpp.sh", "scripts/load_env.sh"):
        assert (REPO / rel).is_file()
        assert not (REPO / rel).with_suffix(".ps1").exists()


@pytest.mark.skipif(not PWSH, reason="PowerShell not available")
@pytest.mark.parametrize("stem", SCRIPT_STEMS)
def test_powershell_scripts_parse(stem):
    path = (REPO / f"{stem}.ps1").as_posix()
    code = (
        "$e=$null;"
        f"[System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$null,[ref]$e)|Out-Null;"
        "if($e){$e|ForEach-Object{Write-Error $_};exit 1}else{exit 0}"
    )
    result = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
