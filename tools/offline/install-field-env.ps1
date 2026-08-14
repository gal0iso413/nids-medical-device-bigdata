#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $PythonExe,
    [string] $KitDirectory = $PSScriptRoot,
    [string] $InstallDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "field-kit-common.ps1")

$kit = Get-FieldKitFullPath $KitDirectory
if ([string]::IsNullOrWhiteSpace($InstallDirectory)) {
    $InstallDirectory = Join-Path (Split-Path -Parent $kit) "nids-field-runtime"
}
$install = Get-FieldKitFullPath $InstallDirectory
if (Test-Path -LiteralPath $install) {
    throw "InstallDirectory must not exist; installation requires a clean target."
}
$manifest = Test-FieldKit -KitDirectory $kit
$runtime = Assert-FieldKitPython -PythonExe $PythonExe
$parent = Split-Path -Parent $install
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "The parent of InstallDirectory must already exist."
}
$staging = Join-Path $parent (".field-env.tmp-" + [guid]::NewGuid().ToString("N"))
try {
    $null = New-Item -ItemType Directory -Path $staging
    $venv = Join-Path $staging ".venv"
    & $PythonExe -I -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
    $venvPython = Join-Path $venv "Scripts\python.exe"
    & $venvPython -I -m pip install --disable-pip-version-check --no-index `
        --find-links (Join-Path $kit "wheels") --only-binary=:all: --no-deps --require-hashes `
        --requirement (Join-Path $kit $manifest.dependency_lock)
    if ($LASTEXITCODE -ne 0) { throw "Offline wheel installation failed." }

    $sourceArchive = @(Get-ChildItem -LiteralPath (Join-Path $kit "source") -Filter "*.zip" -File)
    if ($sourceArchive.Count -ne 1) { throw "Exactly one source snapshot is required." }
    $sourceRoot = Join-Path $staging "source"
    Expand-Archive -LiteralPath $sourceArchive[0].FullName -DestinationPath $sourceRoot
    $versionProbe = "import importlib.metadata as m,json,site,sys; names=['numpy','pandas','pyarrow','openpyxl','et-xmlfile','python-dateutil','six','tzdata']; print(json.dumps({'venv':sys.prefix!=sys.base_prefix,'user_site':site.ENABLE_USER_SITE,'versions':{n:m.version(n) for n in names}},sort_keys=True))"
    $probeRaw = & $venvPython -I -c $versionProbe
    if ($LASTEXITCODE -ne 0) { throw "Installed environment verification failed." }
    $probe = $probeRaw | ConvertFrom-Json
    if (-not $probe.venv -or $probe.user_site) { throw "The installed interpreter is not isolated from global/user site-packages." }
    foreach ($name in $script:FieldKitPackageVersions.Keys) {
        if ([string]$probe.versions.$name -ne [string]$script:FieldKitPackageVersions[$name]) {
            throw "Installed package version does not match the field-kit lock: $name"
        }
    }
    Write-FieldKitUtf8 -Path (Join-Path $staging "source-commit.txt") -Text ($manifest.source_commit + "`n")
    Move-Item -LiteralPath $staging -Destination $install
    [ordered]@{
        status = "installed"
        source_commit = $manifest.source_commit
        python_version = $runtime.version
        isolated_venv = $true
    } | ConvertTo-Json -Compress
}
catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    throw
}
