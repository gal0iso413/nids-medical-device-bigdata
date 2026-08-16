#Requires -Version 5.1
param([Parameter(Mandatory=$true)][ValidateSet('preflight','pipeline','class3-export','class1-run','verify')][string]$Command,[Parameter(Mandatory=$true)][string]$Config,[string]$InstallDirectory="")
$ErrorActionPreference="Stop"; Set-StrictMode -Version Latest
if (!$InstallDirectory) {$InstallDirectory=Join-Path (Split-Path -Parent $PSScriptRoot) 'nids-analysis-runtime'}
$runtime=[IO.Path]::GetFullPath($InstallDirectory); $py=Join-Path $runtime '.venv\Scripts\python.exe'; $source=Join-Path $runtime 'source'; if(!(Test-Path $py) -or !(Test-Path $source)){throw 'installed analysis environment is incomplete'}
$common=Join-Path $source 'tools\offline\analysis-kit\analysis-kit-common.ps1'; . $common
$env:PIP_NO_INDEX='1'; Push-Location $source
try {
  if($Command -eq 'preflight') { & $py -s -m data_pipeline.cli preflight --config $Config }
  elseif($Command -eq 'pipeline') { & $py -s -m data_pipeline.cli run --config $Config }
  elseif($Command -eq 'class3-export') { $cfg=Get-AnalysisConfigValue $py $Config 'class3_export' 'config'; & $py -s -m data_pipeline.offline.class3_analysis_export --config $cfg }
  elseif($Command -eq 'class1-run') { $cfg=Get-AnalysisConfigValue $py $Config 'class1' 'config'; & $py -s -m class_1_anomaly_detection.src.offline_anchor_runner --config $cfg; $class1=Get-Content $cfg -Raw -Encoding UTF8|ConvertFrom-Json; & $py -s -m data_pipeline.offline.local_analysis_tools publish-class1-web --output-root $class1.output_root --web-public-root (Join-Path $runtime 'sites\class1') --anchor-month $class1.anchor_month }
  else { & $py -s -m data_pipeline.cli verify --config $Config; $class3=Join-Path $runtime 'sites\class3'; & $py -s -m data_pipeline.offline.local_analysis_tools verify-class3 --web-public-root $class3; $cfg=Get-AnalysisConfigValue $py $Config 'class1' 'config'; $class1=Get-Content $cfg -Raw -Encoding UTF8|ConvertFrom-Json; & $py -s -m data_pipeline.offline.local_analysis_tools verify-class1-web --web-public-root (Join-Path $runtime 'sites\class1') --anchor-month $class1.anchor_month --selected-entity-id $class1.selected_entity_id }
  if($LASTEXITCODE -ne 0){throw "existing analysis command failed: $Command"}
} finally {Pop-Location}
