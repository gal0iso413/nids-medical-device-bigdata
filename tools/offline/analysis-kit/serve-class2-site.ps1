#Requires -Version 5.1
param([Parameter(Mandatory=$true)][string]$MartRoot,[ValidateSet('127.0.0.1','localhost','::1')][string]$Host='127.0.0.1',[int]$Port=8012,[string]$InstallDirectory="")
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if(!$InstallDirectory){$InstallDirectory=Join-Path (Split-Path -Parent $PSScriptRoot) 'nids-analysis-runtime'};$runtime=[IO.Path]::GetFullPath($InstallDirectory);$py=Join-Path $runtime '.venv\Scripts\python.exe';$source=Join-Path $runtime 'source';$static=Join-Path $runtime 'sites\class2';if(!(Test-Path $py) -or !(Test-Path $static)){throw 'runtime is incomplete'};Push-Location $source;try{&$py -s -m services.class2_local_api --mart-root $MartRoot --static-root $static --host $Host --port $Port}finally{Pop-Location}
