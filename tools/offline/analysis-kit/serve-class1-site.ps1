#Requires -Version 5.1
param([Parameter(Mandatory=$true)][string]$IndexRoot,[ValidateSet('127.0.0.1','localhost','::1')][string]$ListenAddress='127.0.0.1',[int]$Port=8011,[string]$InstallDirectory="")
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if(!$InstallDirectory){$InstallDirectory=Join-Path (Split-Path -Parent $PSScriptRoot) 'nids-analysis-runtime'};$runtime=[IO.Path]::GetFullPath($InstallDirectory);$py=Join-Path $runtime '.venv\Scripts\python.exe';$source=Join-Path $runtime 'source';$static=Join-Path $runtime 'sites\class1';if(!(Test-Path $py) -or !(Test-Path $static)){throw 'runtime is incomplete'};Push-Location $source;try{&$py -s -m services.class1_local_api --index-root $IndexRoot --static-root $static --host $ListenAddress --port $Port}finally{Pop-Location}
