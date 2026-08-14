#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $PythonExe,
    [Parameter(Mandatory = $true)][string] $PythonInstaller,
    [Parameter(Mandatory = $true)][string] $OutputDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "field-kit-common.ps1")

$repositoryRoot = Get-FieldKitFullPath (Join-Path $PSScriptRoot "..\..")
$output = Get-FieldKitFullPath $OutputDirectory
$repositoryPrefix = $repositoryRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if ($output.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
    $repositoryRoot.StartsWith($output.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must be outside the Git repository."
}
if (Test-Path -LiteralPath $output) {
    throw "OutputDirectory already exists; refusing to overwrite it."
}

$null = Assert-FieldKitPython -PythonExe $PythonExe
if (-not (Test-Path -LiteralPath $PythonInstaller -PathType Leaf)) {
    throw "PythonInstaller does not exist."
}
$installerHash = (Get-FileHash -LiteralPath $PythonInstaller -Algorithm SHA256).Hash.ToLowerInvariant()
if ($installerHash -ne $script:FieldKitInstallerSha256) {
    throw "Python installer SHA-256 does not match the official CPython 3.13.12 x64 installer."
}
$signature = Get-AuthenticodeSignature -LiteralPath $PythonInstaller
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -or
    $null -eq $signature.SignerCertificate -or
    $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
    throw "Python installer does not have a valid Python Software Foundation signature."
}

$status = @(& git -C $repositoryRoot status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect the Git working tree."
}
if ($status.Count -ne 0) {
    throw "The Git working tree must be clean before building a field kit."
}
$sourceCommit = (& git -C $repositoryRoot rev-parse HEAD).Trim().ToLowerInvariant()
if ($LASTEXITCODE -ne 0 -or $sourceCommit -notmatch '^[0-9a-f]{40}$') {
    throw "Unable to resolve the source commit."
}

$parent = Split-Path -Parent $output
if ([string]::IsNullOrWhiteSpace($parent) -or -not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "The parent of OutputDirectory must already exist."
}
$staging = Join-Path $parent (".field-kit.tmp-" + [guid]::NewGuid().ToString("N"))
try {
    $null = New-Item -ItemType Directory -Path $staging
    $wheelDirectory = New-Item -ItemType Directory -Path (Join-Path $staging "wheels")
    $installerDirectory = New-Item -ItemType Directory -Path (Join-Path $staging "python")
    $sourceDirectory = New-Item -ItemType Directory -Path (Join-Path $staging "source")
    $metadataDirectory = New-Item -ItemType Directory -Path (Join-Path $staging "metadata")

    foreach ($name in @("field-kit-common.ps1", "verify-field-kit.ps1", "install-field-env.ps1", "smoke-test.ps1")) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $staging $name)
    }
    $lockSource = Join-Path $PSScriptRoot "requirements-field-kit-win-py313.lock"
    $lockTarget = Join-Path $metadataDirectory.FullName "requirements-field-kit-win-py313.lock"
    Copy-Item -LiteralPath $lockSource -Destination $lockTarget
    Copy-Item -LiteralPath $PythonInstaller -Destination (Join-Path $installerDirectory.FullName "python-3.13.12-amd64.exe")

    & $PythonExe -I -m pip download --disable-pip-version-check --require-hashes --only-binary=:all: --no-deps `
        --platform win_amd64 --python-version 3.13 --implementation cp --abi cp313 `
        --dest $wheelDirectory.FullName --requirement $lockSource
    if ($LASTEXITCODE -ne 0) {
        throw "Binary-only wheel download failed."
    }
    $wheels = @(Get-ChildItem -LiteralPath $wheelDirectory.FullName -File)
    if ($wheels.Count -ne 8 -or @($wheels | Where-Object { $_.Extension -ne ".whl" }).Count -ne 0) {
        throw "The wheelhouse must contain exactly the eight locked wheel files."
    }

    $archivePath = Join-Path $sourceDirectory.FullName ("nids-data-pipeline-" + $sourceCommit + ".zip")
    $archiveArgs = @(
        "archive", "--format=zip", "--output=$archivePath", $sourceCommit, "--",
        "README.md", "data_pipeline", "config/field-run.example.toml",
        "requirements-data-pipeline.txt", "tests", "docs/data"
    )
    & git -C $repositoryRoot @archiveArgs
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
        throw "Source snapshot creation failed."
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        foreach ($entry in $archive.Entries) {
            if ($entry.FullName -match '(?i)(^|/)(\.git|node_modules|dist)(/|$)' -or
                $entry.FullName -match '(?i)\.(xlsx?|xlsm|csv|json|parquet|sqlite(?:-wal|-shm)?|db|whl|zip)$' -or
                $entry.FullName -match '(?i)(^|/)(\.env(?:\..*)?|field-run(?:\.local)?\.toml)$' -or
                $entry.FullName -match '(?i)(^|/)[^/]*(credential|secret)[^/]*($|/)') {
                throw "Source snapshot contains a forbidden path."
            }
        }
    }
    finally {
        $archive.Dispose()
    }

    $fileEntries = @()
    foreach ($file in @(Get-FieldKitFiles $staging)) {
        $relative = Get-FieldKitRelativePath $staging $file.FullName
        $role = "support"
        if ($relative.StartsWith("wheels/")) { $role = "wheel" }
        elseif ($relative.StartsWith("python/")) { $role = "python_installer" }
        elseif ($relative.StartsWith("source/")) { $role = "source_snapshot" }
        elseif ($relative.StartsWith("metadata/")) { $role = "dependency_lock" }
        elseif ($relative.EndsWith(".ps1")) { $role = "field_tool" }
        $fileEntries += [ordered]@{
            relative_path = $relative
            role = $role
            size = [int64]$file.Length
            sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $manifest = [ordered]@{
        contract_version = $script:FieldKitContractVersion
        source_commit = $sourceCommit
        python = [ordered]@{
            implementation = "CPython"
            version = $script:FieldKitPythonVersion
            major_minor = $script:FieldKitPythonMajorMinor
            architecture = "64bit"
            platform = $script:FieldKitPlatform
            installer_sha256 = $script:FieldKitInstallerSha256
        }
        dependency_lock = "metadata/requirements-field-kit-win-py313.lock"
        source_snapshot_policy = "tracked pipeline source and synthetic tests only"
        files = @($fileEntries)
    }
    Write-FieldKitUtf8 -Path (Join-Path $staging "field-kit-manifest.json") -Text (($manifest | ConvertTo-Json -Depth 8 -Compress) + "`n")
    $null = Test-FieldKit -KitDirectory $staging
    Move-Item -LiteralPath $staging -Destination $output
    [ordered]@{
        status = "built"
        source_commit = $sourceCommit
        file_count = $fileEntries.Count
        output_size = (Get-ChildItem -LiteralPath $output -File -Recurse | Measure-Object -Property Length -Sum).Sum
    } | ConvertTo-Json -Compress
}
catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    throw
}
