#Requires -Version 5.1
Set-StrictMode -Version Latest
$script:AnalysisKitVersion = "1.0.0"
$script:AnalysisPythonVersion = "3.13.12"
$script:AnalysisInstallerSha256 = "96159fcb523ae404b707186a75b4104ee23851e476a5e838e14584cf1e03f981"

function Get-AnalysisFullPath { param([string] $Path) [System.IO.Path]::GetFullPath($Path) }
function Write-AnalysisUtf8 { param([string]$Path,[string]$Text) [System.IO.File]::WriteAllText($Path,$Text,(New-Object System.Text.UTF8Encoding($false))) }
function Get-AnalysisRelativePath {
    param([string] $BasePath, [string] $Path)
    $base=(Get-AnalysisFullPath $BasePath).TrimEnd('\','/')+[System.IO.Path]::DirectorySeparatorChar
    $full=Get-AnalysisFullPath $Path
    if(-not $full.StartsWith($base,[System.StringComparison]::OrdinalIgnoreCase)){throw "Path is outside the analysis kit."}
    $full.Substring($base.Length).Replace('\','/')
}
function Assert-AnalysisRelativePath {
    param([string] $RelativePath)
    if([string]::IsNullOrWhiteSpace($RelativePath) -or $RelativePath.StartsWith('/') -or
       $RelativePath.StartsWith('\') -or $RelativePath.Contains('\') -or $RelativePath.Contains(':') -or
       @($RelativePath.Split('/')) -contains '..' -or @($RelativePath.Split('/')) -contains '') {
        throw "Analysis kit manifest path is unsafe."
    }
}
function Get-AnalysisFiles {
    param([string]$Root)
    $rootPath=Get-AnalysisFullPath $Root
    if(-not (Test-Path -LiteralPath $rootPath -PathType Container)){throw "Analysis kit directory is missing."}
    $rootItem=Get-Item -LiteralPath $rootPath -Force
    if(($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0){throw "Analysis kit root must not be a link or reparse point."}
    $links=@(Get-ChildItem -LiteralPath $rootPath -Force -Recurse|Where-Object{($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0})
    if($links.Count -ne 0){throw "Analysis kit must not contain links or reparse points."}
    $byRelative=@{}
    foreach($file in @(Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force)){
        $relative=Get-AnalysisRelativePath -BasePath $rootPath -Path $file.FullName
        if($relative -ne 'analysis-kit-manifest.json'){$byRelative[$relative]=$file}
    }
    $relativePaths=[string[]]@($byRelative.Keys)
    [System.Array]::Sort($relativePaths,[System.StringComparer]::OrdinalIgnoreCase)
    @($relativePaths|ForEach-Object{$byRelative[$_]})
}
function Test-AnalysisKit {
    param([string]$KitDirectory)
    $root=Get-AnalysisFullPath $KitDirectory; $path=Join-Path $root "analysis-kit-manifest.json"
    if(-not (Test-Path -LiteralPath $path -PathType Leaf)){throw "analysis-kit-manifest.json is missing."}
    try{$raw=Get-Content -LiteralPath $path -Raw -Encoding UTF8;$manifest=$raw|ConvertFrom-Json}
    catch{throw "analysis-kit-manifest.json is invalid JSON: $($_.Exception.Message)"}
    if($raw -ne (($manifest|ConvertTo-Json -Depth 10 -Compress)+"`n")){throw "analysis-kit-manifest.json is not canonical."}
    if($manifest.contract_version -ne $script:AnalysisKitVersion -or
       $manifest.python.implementation -ne 'CPython' -or $manifest.python.version -ne $script:AnalysisPythonVersion -or
       $manifest.python.architecture -ne '64bit' -or $manifest.python.platform -ne 'win_amd64' -or
       $manifest.python.installer_sha256 -ne $script:AnalysisInstallerSha256 -or
       $manifest.dependency_lock -ne "metadata/requirements-analysis-kit-win-py313.lock" -or
       $manifest.source_commit -notmatch '^[0-9a-f]{40}$' -or $manifest.source_tree_fingerprint -notmatch '^[0-9a-f]{64}$' -or
       $manifest.source_snapshot.archive -notmatch '^source/[^/]+\.zip$' -or
       $manifest.source_snapshot.manifest -ne 'metadata/source-snapshot-manifest.json' -or
       $manifest.static_sites.class1 -ne 'sites/class1' -or $manifest.static_sites.class2 -ne 'sites/class2' -or
       $manifest.generated_policy -ne 'empty_directories_only') {throw "Analysis kit contract is invalid."}
    $expected=@{};$previous=''
    foreach($entry in @($manifest.files)){
        $relative=[string]$entry.relative_path;Assert-AnalysisRelativePath $relative
        if($expected.ContainsKey($relative)){throw "Analysis kit manifest contains a duplicate path."}
        if($previous -and [string]::Compare($previous,$relative,[System.StringComparison]::OrdinalIgnoreCase) -ge 0){throw "Analysis kit manifest file entries are not canonical."}
        if([int64]$entry.size -lt 0 -or [string]$entry.sha256 -notmatch '^[0-9a-f]{64}$' -or [string]::IsNullOrWhiteSpace([string]$entry.role)){throw "Analysis kit manifest file metadata is invalid."}
        $expected[$relative]=$entry;$previous=$relative
    }
    $actual=@{};foreach($file in @(Get-AnalysisFiles $root)){$relative=Get-AnalysisRelativePath -BasePath $root -Path $file.FullName;$actual[$relative]=$file}
    if(@($expected.Keys|Where-Object{-not $actual.ContainsKey($_)}).Count -ne 0 -or @($actual.Keys|Where-Object{-not $expected.ContainsKey($_)}).Count -ne 0){throw "Analysis kit file set differs from manifest."}
    foreach($relative in $expected.Keys){$entry=$expected[$relative];$file=$actual[$relative];if([int64]$file.Length -ne [int64]$entry.size -or (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne [string]$entry.sha256){throw "Analysis kit checksum mismatch: $relative"}}
    foreach($relative in @($manifest.dependency_lock,$manifest.source_snapshot.archive,$manifest.source_snapshot.manifest)){
        if(-not $expected.ContainsKey([string]$relative)){throw "Analysis kit required path is absent from its exact file set."}
    }
    foreach($site in @('sites/class1','sites/class2')){
        if(-not $expected.ContainsKey("$site/index.html")){throw "Analysis kit static site is missing index.html."}
        $generated=Join-Path $root ("$site/generated".Replace('/',[System.IO.Path]::DirectorySeparatorChar))
        if(-not (Test-Path -LiteralPath $generated -PathType Container) -or @(Get-ChildItem -LiteralPath $generated -Force).Count -ne 0){throw "Analysis kit generated directories must exist and be empty."}
    }
    try{$sourceManifest=Get-Content -LiteralPath (Join-Path $root 'metadata\source-snapshot-manifest.json') -Raw -Encoding UTF8|ConvertFrom-Json}
    catch{throw "Analysis kit source snapshot manifest is invalid."}
    if([string]$sourceManifest.base_commit_sha -ne [string]$manifest.source_commit -or [string]$sourceManifest.source_tree_fingerprint -ne [string]$manifest.source_tree_fingerprint){throw "Analysis kit source snapshot identity differs from the kit manifest."}
    return $manifest
}
function Get-AnalysisConfigValue { param([string]$Python,[string]$Config,[string]$Section,[string]$Key) & $Python -I -c "import pathlib,tomllib; print(tomllib.loads(pathlib.Path(r'''$Config''').read_text(encoding='utf-8'))[r'''$Section'''][r'''$Key'''])" }
