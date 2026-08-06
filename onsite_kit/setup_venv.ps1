# NIDS Class 1 onsite — create/activate venv (no conda)
# Usage (from kit root):
#   powershell -ExecutionPolicy Bypass -File onsite_kit\setup_venv.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "class_1_anomaly_detection"))) {
    $Root = (Get-Location).Path
}
Set-Location $Root
Write-Host "Kit root: $Root"

$py = $null
foreach ($cand in @("py -3.11", "py -3.12", "py -3.10", "python")) {
    try {
        if ($cand -like "py *") {
            $parts = $cand.Split(" ")
            & $parts[0] $parts[1] --version | Out-Null
            if ($LASTEXITCODE -eq 0) { $py = $cand; break }
        } else {
            & python --version | Out-Null
            if ($LASTEXITCODE -eq 0) { $py = "python"; break }
        }
    } catch { }
}

if (-not $py) {
    Write-Error "Python not found. Install Python 3.10–3.12 and ensure 'py' or 'python' is on PATH."
}

Write-Host "Using: $py"
$venvPath = Join-Path $Root ".venv"
if (-not (Test-Path $venvPath)) {
    if ($py -like "py *") {
        $parts = $py.Split(" ")
        & $parts[0] $parts[1] -m venv $venvPath
    } else {
        & python -m venv $venvPath
    }
    Write-Host "Created .venv"
} else {
    Write-Host ".venv already exists"
}

$activate = Join-Path $venvPath "Scripts\Activate.ps1"
Write-Host ""
Write-Host "Next, run:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  python -m pip install --upgrade pip"
Write-Host "  python -m pip install -r requirements.txt"
