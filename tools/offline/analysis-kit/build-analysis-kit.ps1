#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $PythonExe,
    [Parameter(Mandatory = $true)][string] $PythonInstaller,
    [Parameter(Mandatory = $true)][Alias("Wheelhouse")][string] $WheelhouseDirectory,
    [Parameter(Mandatory = $true)][Alias("Class1Dist")][string] $Class1DistDirectory,
    [Parameter(Mandatory = $true)][Alias("Class2Dist")][string] $Class2DistDirectory,
    [Parameter(Mandatory = $true)][string] $OutputDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "analysis-kit-common.ps1")

function Get-BuilderRelativePath {
    param([string] $BasePath, [string] $Path)
    $base = (Get-AnalysisFullPath $BasePath).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $full = Get-AnalysisFullPath $Path
    if (-not $full.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes its declared input root."
    }
    return $full.Substring($base.Length).Replace('\', '/')
}

function Assert-BuilderTree {
    param([string] $Root, [string] $Label)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "$Label does not exist or is not a directory."
    }
    $rootItem = Get-Item -LiteralPath $Root -Force
    if (($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "$Label must not be a link or reparse point."
    }
    $links = @(Get-ChildItem -LiteralPath $Root -Force -Recurse | Where-Object {
        ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
    })
    if ($links.Count -ne 0) {
        throw "$Label must not contain links or reparse points."
    }
}

function Read-AnalysisLockEntries {
    param([string] $LockPath)
    if (-not (Test-Path -LiteralPath $LockPath -PathType Leaf)) {
        throw "Analysis dependency lock is missing."
    }
    $entries = @()
    foreach ($line in @(Get-Content -LiteralPath $LockPath -Encoding UTF8)) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith('#')) { continue }
        $match = [regex]::Match($line, '^\s*([A-Za-z0-9_.-]+)==([^\s#]+)\s+--hash=sha256:([0-9a-f]{64})(?:\s+#.*)?\s*$')
        if (-not $match.Success) {
            throw "Analysis dependency lock must contain only exact, single-hash requirements."
        }
        $normalized = [regex]::Replace($match.Groups[1].Value.ToLowerInvariant(), '[-_.]+', '-')
        $entries += [pscustomobject]@{
            package = $match.Groups[1].Value
            normalized_package = $normalized
            version = $match.Groups[2].Value
            sha256 = $match.Groups[3].Value
        }
    }
    if ($entries.Count -lt 43) { throw "Analysis dependency lock must retain the 43-wheel baseline." }
    if (@($entries | Group-Object normalized_package | Where-Object Count -ne 1).Count -ne 0) {
        throw "Analysis dependency lock contains duplicate packages."
    }
    if (@($entries | Group-Object sha256 | Where-Object Count -ne 1).Count -ne 0) {
        throw "Analysis dependency lock contains duplicate hashes."
    }
    return @($entries)
}

function Copy-VerifiedWheelhouse {
    param([string] $Wheelhouse, [object[]] $LockEntries, [string] $Destination)
    Assert-BuilderTree -Root $Wheelhouse -Label "WheelhouseDirectory"
    $children = @(Get-ChildItem -LiteralPath $Wheelhouse -Force)
    $wheels = @($children | Where-Object { -not $_.PSIsContainer })
    if ($children.Count -ne $LockEntries.Count -or $wheels.Count -ne $LockEntries.Count -or @($wheels | Where-Object Extension -ne '.whl').Count -ne 0) {
        throw "The input wheelhouse must be flat and exactly match the locked wheel count."
    }
    $byHash = @{}
    foreach ($entry in $LockEntries) { $byHash[$entry.sha256] = $entry }
    $seen = @{}
    foreach ($wheel in @($wheels | Sort-Object Name)) {
        $hash = (Get-FileHash -LiteralPath $wheel.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if (-not $byHash.ContainsKey($hash)) { throw "Wheel is not present in the locked hash set: $($wheel.Name)" }
        $entry = $byHash[$hash]
        $wheelPackage = $entry.normalized_package.Replace('-', '_')
        $wheelVersion = ([string]$entry.version).Replace('-', '_')
        $expectedPrefix = "$wheelPackage-$wheelVersion-"
        if (-not $wheel.Name.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Wheel package/version does not match its locked hash: $($wheel.Name)"
        }
        if ($seen.ContainsKey($entry.normalized_package)) { throw "More than one wheel satisfies a locked package." }
        $seen[$entry.normalized_package] = $true
        Copy-Item -LiteralPath $wheel.FullName -Destination (Join-Path $Destination $wheel.Name)
    }
    if ($seen.Count -ne $LockEntries.Count) { throw "Every locked package must have exactly one input wheel." }
}

function Copy-VerifiedStaticSite {
    param([string] $DistRoot, [string] $Destination, [string] $Label)
    Assert-BuilderTree -Root $DistRoot -Label $Label
    if (-not (Test-Path -LiteralPath (Join-Path $DistRoot 'index.html') -PathType Leaf)) {
        throw "$Label must contain index.html at its root."
    }
    $files = @(Get-ChildItem -LiteralPath $DistRoot -File -Force -Recurse | Sort-Object FullName)
    if ($files.Count -eq 0) { throw "$Label is empty." }
    $blockedNames = @('restricted-qa.json', 'run-manifest.json', 'source-snapshot-manifest.json')
    $null = New-Item -ItemType Directory -Path $Destination
    foreach ($file in $files) {
        $relative = Get-BuilderRelativePath -BasePath $DistRoot -Path $file.FullName
        $parts = @($relative.Split('/'))
        $leaf = $parts[-1].ToLowerInvariant()
        if (@($parts | Where-Object { $_.ToLowerInvariant() -eq 'generated' }).Count -ne 0 -or
            $blockedNames -contains $leaf -or $leaf -match '(^|[-_.])raw[-_.]?scores?($|[-_.])') {
            throw "$Label contains a generated, raw-score, QA, or source-manifest artifact: $relative"
        }
        if ($leaf.EndsWith('.json')) {
            throw "$Label contains a raw JSON artifact: $relative"
        }
        Assert-AnalysisRelativePath $relative
        $target = Join-Path $Destination $relative.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
        $targetParent = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $targetParent -PathType Container)) {
            $null = New-Item -ItemType Directory -Path $targetParent -Force
        }
        Copy-Item -LiteralPath $file.FullName -Destination $target
    }
    $null = New-Item -ItemType Directory -Path (Join-Path $Destination 'generated')
}

function Test-SourceSnapshotResult {
    param([string] $SnapshotRoot)
    Assert-BuilderTree -Root $SnapshotRoot -Label "source_snapshot.py result"
    $manifestPath = Join-Path $SnapshotRoot 'source-snapshot-manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Source snapshot manifest is missing." }
    try { $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { throw "Source snapshot manifest is invalid JSON: $($_.Exception.Message)" }
    if ([string]$manifest.base_commit_sha -notmatch '^[0-9a-f]{40}$' -or
        [string]$manifest.source_tree_fingerprint -notmatch '^[0-9a-f]{64}$' -or
        [string]$manifest.source_mode -ne 'working-tree') {
        throw "Source snapshot identity is invalid."
    }
    $expected = @{}
    foreach ($entry in @($manifest.files)) {
        $relative = [string]$entry.relative_path
        Assert-AnalysisRelativePath $relative
        if ($relative -eq 'source-snapshot-manifest.json' -or $expected.ContainsKey($relative) -or
            [int64]$entry.size -lt 0 -or [string]$entry.sha256 -notmatch '^[0-9a-f]{64}$') {
            throw "Source snapshot file metadata is invalid."
        }
        $expected[$relative] = $entry
    }
    if ([int]$manifest.file_count -ne $expected.Count) { throw "Source snapshot file count is invalid." }
    $actual = @{}
    foreach ($file in @(Get-ChildItem -LiteralPath $SnapshotRoot -File -Force -Recurse)) {
        $relative = Get-BuilderRelativePath -BasePath $SnapshotRoot -Path $file.FullName
        if ($relative -ne 'source-snapshot-manifest.json') { $actual[$relative] = $file }
    }
    if (@($expected.Keys | Where-Object { -not $actual.ContainsKey($_) }).Count -ne 0 -or
        @($actual.Keys | Where-Object { -not $expected.ContainsKey($_) }).Count -ne 0) {
        throw "Source snapshot file set differs from its manifest."
    }
    foreach ($relative in $expected.Keys) {
        $file = $actual[$relative]; $entry = $expected[$relative]
        if ([int64]$file.Length -ne [int64]$entry.size -or
            (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne [string]$entry.sha256) {
            throw "Source snapshot checksum mismatch: $relative"
        }
    }
    return $manifest
}

function New-DeterministicSourceZip {
    param([string] $SnapshotRoot, [string] $ArchivePath)
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::Open($ArchivePath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in @(Get-ChildItem -LiteralPath $SnapshotRoot -File -Force -Recurse | Sort-Object FullName)) {
            $relative = Get-BuilderRelativePath -BasePath $SnapshotRoot -Path $file.FullName
            Assert-AnalysisRelativePath $relative
            $entry = $archive.CreateEntry($relative, [System.IO.Compression.CompressionLevel]::Optimal)
            $entry.LastWriteTime = [DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
            $input = [System.IO.File]::OpenRead($file.FullName)
            $output = $entry.Open()
            try { $input.CopyTo($output) }
            finally { $output.Dispose(); $input.Dispose() }
        }
    }
    finally { $archive.Dispose() }
}

function Get-AnalysisFileRole {
    param([string] $Relative)
    if ($Relative.StartsWith('wheels/')) { return 'wheel' }
    if ($Relative.StartsWith('python/')) { return 'python_installer' }
    if ($Relative -eq 'metadata/requirements-analysis-kit-win-py313.lock') { return 'dependency_lock' }
    if ($Relative -eq 'metadata/source-snapshot-manifest.json') { return 'source_snapshot_manifest' }
    if ($Relative.StartsWith('source/')) { return 'source_snapshot' }
    if ($Relative.StartsWith('sites/class1/')) { return 'class1_static_site' }
    if ($Relative.StartsWith('sites/class2/')) { return 'class2_static_site' }
    if ($Relative.EndsWith('.ps1')) { return 'analysis_tool' }
    return 'support'
}

$repositoryRoot = Get-AnalysisFullPath (Join-Path $PSScriptRoot '..\..\..')
$output = Get-AnalysisFullPath $OutputDirectory
$parent = Split-Path -Parent $output
if ([string]::IsNullOrWhiteSpace($parent) -or -not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "The parent of OutputDirectory must already exist."
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "PythonExe does not exist." }
if (-not (Test-Path -LiteralPath $PythonInstaller -PathType Leaf)) { throw "PythonInstaller does not exist." }
if ((Get-FileHash -LiteralPath $PythonInstaller -Algorithm SHA256).Hash.ToLowerInvariant() -ne $script:AnalysisInstallerSha256) {
    throw "Official CPython installer hash mismatch."
}

$lockSource = Join-Path $PSScriptRoot 'requirements-analysis-kit-win-py313.lock'
$lockEntries = @(Read-AnalysisLockEntries -LockPath $lockSource)
$staging = Join-Path $parent ('.analysis-kit.tmp-' + [guid]::NewGuid().ToString('N'))
try {
    $null = New-Item -ItemType Directory -Path $staging
    foreach ($directory in @('wheels', 'python', 'metadata', 'source', 'sites')) {
        $null = New-Item -ItemType Directory -Path (Join-Path $staging $directory)
    }
    Copy-VerifiedWheelhouse -Wheelhouse (Get-AnalysisFullPath $WheelhouseDirectory) -LockEntries $lockEntries -Destination (Join-Path $staging 'wheels')
    Copy-Item -LiteralPath $lockSource -Destination (Join-Path $staging 'metadata\requirements-analysis-kit-win-py313.lock')
    Copy-Item -LiteralPath $PythonInstaller -Destination (Join-Path $staging 'python\python-3.13.12-amd64.exe')

    Copy-VerifiedStaticSite -DistRoot (Get-AnalysisFullPath $Class1DistDirectory) -Destination (Join-Path $staging 'sites\class1') -Label 'Class1DistDirectory'
    Copy-VerifiedStaticSite -DistRoot (Get-AnalysisFullPath $Class2DistDirectory) -Destination (Join-Path $staging 'sites\class2') -Label 'Class2DistDirectory'

    foreach ($name in @('analysis-kit-common.ps1', 'verify-analysis-kit.ps1', 'install-analysis-env.ps1', 'run-analysis.ps1', 'serve-analysis-sites.ps1', 'build-class2-serving-marts.ps1', 'serve-class2-site.ps1', 'rehearse-class2-site.ps1', 'build-class1-lookup-index.ps1', 'serve-class1-site.ps1', 'rehearse-class1-site.ps1', 'run-class1-graph-scale-gate.ps1', 'smoke-analysis-kit.ps1', 'field-run.example.toml', 'README.md')) {
        $source = Join-Path $PSScriptRoot $name
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Required kit support file is missing: $name" }
        Copy-Item -LiteralPath $source -Destination (Join-Path $staging $name)
    }

    $snapshotRoot = Join-Path $staging '.source-snapshot'
    & $PythonExe -I (Join-Path $PSScriptRoot 'source_snapshot.py') $repositoryRoot $snapshotRoot | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Working-tree source snapshot failed." }
    $snapshot = Test-SourceSnapshotResult -SnapshotRoot $snapshotRoot
    $snapshotManifestTarget = Join-Path $staging 'metadata\source-snapshot-manifest.json'
    Copy-Item -LiteralPath (Join-Path $snapshotRoot 'source-snapshot-manifest.json') -Destination $snapshotManifestTarget
    $archiveRelative = 'source/nids-analysis-source-' + [string]$snapshot.source_tree_fingerprint + '.zip'
    New-DeterministicSourceZip -SnapshotRoot $snapshotRoot -ArchivePath (Join-Path $staging $archiveRelative.Replace('/', '\'))
    Remove-Item -LiteralPath $snapshotRoot -Recurse -Force

    $fileEntries = @()
    foreach ($file in @(Get-AnalysisFiles $staging)) {
        $relative = Get-AnalysisRelativePath -BasePath $staging -Path $file.FullName
        $fileEntries += [ordered]@{
            relative_path = $relative
            role = Get-AnalysisFileRole -Relative $relative
            size = [int64]$file.Length
            sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $manifest = [ordered]@{
        contract_version = $script:AnalysisKitVersion
        source_commit = ([string]$snapshot.base_commit_sha).ToLowerInvariant()
        source_tree_fingerprint = [string]$snapshot.source_tree_fingerprint
        python = [ordered]@{
            implementation = 'CPython'; version = $script:AnalysisPythonVersion; architecture = '64bit'
            platform = 'win_amd64'; installer_sha256 = $script:AnalysisInstallerSha256
        }
        dependency_lock = 'metadata/requirements-analysis-kit-win-py313.lock'
        source_snapshot = [ordered]@{ archive = $archiveRelative; manifest = 'metadata/source-snapshot-manifest.json' }
        static_sites = [ordered]@{ class1 = 'sites/class1'; class2 = 'sites/class2' }
        generated_policy = 'empty_directories_only'
        files = @($fileEntries)
    }
    Write-AnalysisUtf8 -Path (Join-Path $staging 'analysis-kit-manifest.json') -Text (($manifest | ConvertTo-Json -Depth 10 -Compress) + "`n")
    $null = Test-AnalysisKit -KitDirectory $staging

    if (Test-Path -LiteralPath $output) {
        if (-not (Test-Path -LiteralPath $output -PathType Container)) { throw "OutputDirectory conflicts with a non-directory path." }
        try { $null = Test-AnalysisKit -KitDirectory $output }
        catch { throw "OutputDirectory contains a conflicting or invalid analysis kit." }
        $newManifest = [System.IO.File]::ReadAllBytes((Join-Path $staging 'analysis-kit-manifest.json'))
        $oldManifest = [System.IO.File]::ReadAllBytes((Join-Path $output 'analysis-kit-manifest.json'))
        if (-not [System.Linq.Enumerable]::SequenceEqual($newManifest, $oldManifest)) {
            throw "OutputDirectory already contains a different analysis kit."
        }
        Remove-Item -LiteralPath $staging -Recurse -Force
        [ordered]@{ status = 'unchanged'; source_commit = $manifest.source_commit; file_count = $fileEntries.Count } | ConvertTo-Json -Compress
        return
    }

    try { Move-Item -LiteralPath $staging -Destination $output }
    catch {
        if (Test-Path -LiteralPath $output -PathType Container) {
            try { $null = Test-AnalysisKit -KitDirectory $output } catch { throw "A conflicting analysis kit won the publish race." }
            $newManifest = [System.IO.File]::ReadAllBytes((Join-Path $staging 'analysis-kit-manifest.json'))
            $oldManifest = [System.IO.File]::ReadAllBytes((Join-Path $output 'analysis-kit-manifest.json'))
            if ([System.Linq.Enumerable]::SequenceEqual($newManifest, $oldManifest)) {
                Remove-Item -LiteralPath $staging -Recurse -Force
                [ordered]@{ status = 'unchanged'; source_commit = $manifest.source_commit; file_count = $fileEntries.Count } | ConvertTo-Json -Compress
                return
            }
        }
        throw "Unable to atomically publish the analysis kit because the destination conflicts."
    }
    [ordered]@{ status = 'built'; source_commit = $manifest.source_commit; file_count = $fileEntries.Count } | ConvertTo-Json -Compress
}
catch {
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    throw
}
