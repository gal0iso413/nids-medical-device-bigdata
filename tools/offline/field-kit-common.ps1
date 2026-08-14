#Requires -Version 5.1
Set-StrictMode -Version Latest

$script:FieldKitContractVersion = "1.0.0"
$script:FieldKitPythonVersion = "3.13.12"
$script:FieldKitPythonMajorMinor = "3.13"
$script:FieldKitPlatform = "win_amd64"
$script:FieldKitInstallerSha256 = "96159fcb523ae404b707186a75b4104ee23851e476a5e838e14584cf1e03f981"
$script:FieldKitPackageVersions = [ordered]@{
    "numpy" = "2.4.6"
    "pandas" = "3.0.3"
    "pyarrow" = "24.0.0"
    "openpyxl" = "3.1.5"
    "et-xmlfile" = "2.0.0"
    "python-dateutil" = "2.9.0.post0"
    "six" = "1.17.0"
    "tzdata" = "2026.2"
}

function Get-FieldKitFullPath {
    param([Parameter(Mandatory = $true)][string] $Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Get-FieldKitRelativePath {
    param(
        [Parameter(Mandatory = $true)][string] $BasePath,
        [Parameter(Mandatory = $true)][string] $Path
    )
    $base = (Get-FieldKitFullPath $BasePath).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $full = Get-FieldKitFullPath $Path
    if (-not $full.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the field kit."
    }
    return $full.Substring($base.Length).Replace('\', '/')
}

function Write-FieldKitUtf8 {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Text
    )
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $utf8)
}

function Get-FieldKitFiles {
    param([Parameter(Mandatory = $true)][string] $KitDirectory)
    $root = Get-FieldKitFullPath $KitDirectory
    if (((Get-Item -LiteralPath $root -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Field-kit root must not be a link or reparse point."
    }
    $reparse = @(Get-ChildItem -LiteralPath $root -Force -Recurse | Where-Object {
        ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
    })
    if ($reparse.Count -ne 0) {
        throw "Field kit must not contain links or reparse points."
    }
    return @(Get-ChildItem -LiteralPath $root -File -Force -Recurse |
        Where-Object { (Get-FieldKitRelativePath $root $_.FullName) -ne "field-kit-manifest.json" } |
        Sort-Object { Get-FieldKitRelativePath $root $_.FullName })
}

function Read-FieldKitManifest {
    param([Parameter(Mandatory = $true)][string] $KitDirectory)
    $path = Join-Path (Get-FieldKitFullPath $KitDirectory) "field-kit-manifest.json"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "field-kit-manifest.json is missing."
    }
    try {
        return Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "field-kit-manifest.json is not valid JSON: $($_.Exception.Message)"
    }
}

function Assert-FieldKitRelativePath {
    param([Parameter(Mandatory = $true)][string] $RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or
        $RelativePath.StartsWith('/') -or
        $RelativePath.StartsWith('\') -or
        $RelativePath.Contains('\') -or
        $RelativePath.Contains(':') -or
        @($RelativePath.Split('/')) -contains '..') {
        throw "Manifest contains an unsafe relative path."
    }
}

function Test-FieldKit {
    param([Parameter(Mandatory = $true)][string] $KitDirectory)
    $root = Get-FieldKitFullPath $KitDirectory
    $manifest = Read-FieldKitManifest $root
    if ($manifest.contract_version -ne $script:FieldKitContractVersion -or
        $manifest.python.version -ne $script:FieldKitPythonVersion -or
        $manifest.python.major_minor -ne $script:FieldKitPythonMajorMinor -or
        $manifest.python.platform -ne $script:FieldKitPlatform -or
        $manifest.python.architecture -ne "64bit" -or
        $manifest.python.implementation -ne "CPython" -or
        $manifest.python.installer_sha256 -ne $script:FieldKitInstallerSha256 -or
        $manifest.dependency_lock -ne "metadata/requirements-field-kit-win-py313.lock" -or
        $manifest.source_commit -notmatch '^[0-9a-f]{40}$') {
        throw "Field-kit contract, Python target, or source commit is invalid."
    }
    $expected = @{}
    foreach ($entry in @($manifest.files)) {
        $relative = [string]$entry.relative_path
        Assert-FieldKitRelativePath $relative
        if ($expected.ContainsKey($relative)) {
            throw "Manifest contains a duplicate file entry."
        }
        if ([int64]$entry.size -lt 0 -or [string]$entry.sha256 -notmatch '^[0-9a-f]{64}$') {
            throw "Manifest contains invalid file metadata."
        }
        $expected[$relative] = $entry
    }
    $lockPath = Join-Path $root ([string]$manifest.dependency_lock).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
        throw "The locked dependency file is missing from the field kit."
    }
    $actual = @{}
    foreach ($file in @(Get-FieldKitFiles $root)) {
        $relative = Get-FieldKitRelativePath $root $file.FullName
        $actual[$relative] = $file
    }
    $missing = @($expected.Keys | Where-Object { -not $actual.ContainsKey($_) } | Sort-Object)
    $extra = @($actual.Keys | Where-Object { -not $expected.ContainsKey($_) } | Sort-Object)
    if ($missing.Count -ne 0 -or $extra.Count -ne 0) {
        throw "Field-kit file set mismatch: missing=$($missing.Count); extra=$($extra.Count)."
    }
    foreach ($relative in @($expected.Keys | Sort-Object)) {
        $file = $actual[$relative]
        $entry = $expected[$relative]
        if ([int64]$file.Length -ne [int64]$entry.size) {
            throw "Field-kit file size mismatch: $relative"
        }
        try {
            $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        catch {
            throw "Unable to hash field-kit file '$relative': $($_.Exception.Message)"
        }
        if ($hash -ne [string]$entry.sha256) {
            throw "Field-kit checksum mismatch: $relative"
        }
    }
    return $manifest
}

function Assert-FieldKitPython {
    param([Parameter(Mandatory = $true)][string] $PythonExe)
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
        throw "Python executable does not exist."
    }
    $probe = "import json,platform,struct,sys; print(json.dumps({'implementation':platform.python_implementation(),'version':platform.python_version(),'bits':struct.calcsize('P')*8,'machine':platform.machine(),'prefix':sys.prefix,'base_prefix':sys.base_prefix}))"
    $raw = & $PythonExe -I -c $probe
    if ($LASTEXITCODE -ne 0) {
        throw "Python runtime probe failed."
    }
    $runtime = $raw | ConvertFrom-Json
    if ($runtime.implementation -ne "CPython" -or
        $runtime.version -ne $script:FieldKitPythonVersion -or
        [int]$runtime.bits -ne 64 -or
        [string]$runtime.machine -notmatch '^(AMD64|x86_64)$') {
        throw "CPython 3.13.12 64-bit for Windows x64 is required."
    }
    return $runtime
}
