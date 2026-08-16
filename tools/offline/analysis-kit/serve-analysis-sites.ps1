#Requires -Version 5.1
param([string]$InstallDirectory="",[int]$Class1Port=8011,[int]$Class3Port=8013)
$ErrorActionPreference="Stop"; Set-StrictMode -Version Latest
if(!$InstallDirectory){$InstallDirectory=Join-Path (Split-Path -Parent $PSScriptRoot) 'nids-analysis-runtime'}; $runtime=[IO.Path]::GetFullPath($InstallDirectory); $py=Join-Path $runtime '.venv\Scripts\python.exe'
foreach($port in @($Class1Port,$Class3Port)){if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){throw "port $port is already in use"}}
$c1=Join-Path $runtime 'sites\class1'; $c3=Join-Path $runtime 'sites\class3'; if(!(Test-Path $c1) -or !(Test-Path $c3)){throw 'static sites are missing'}
$p1=$null;$p3=$null
try {
  $p1=Start-Process -FilePath $py -ArgumentList @('-I','-m','http.server',$Class1Port,'--bind','127.0.0.1') -WorkingDirectory $c1 -PassThru -WindowStyle Hidden
  $p3=Start-Process -FilePath $py -ArgumentList @('-I','-m','http.server',$Class3Port,'--bind','127.0.0.1') -WorkingDirectory $c3 -PassThru -WindowStyle Hidden
  Start-Sleep -Milliseconds 500
  if($p1.HasExited -or $p3.HasExited){throw 'a static site server exited during startup'}
  @{class1_url="http://127.0.0.1:$Class1Port/";class1_pid=$p1.Id;class3_url="http://127.0.0.1:$Class3Port/";class3_pid=$p3.Id;stop="Stop-Process -Id $($p1.Id),$($p3.Id)";network='localhost_only'}|ConvertTo-Json -Compress
} catch {
  foreach($process in @($p1,$p3)){if($null -ne $process -and -not $process.HasExited){Stop-Process -Id $process.Id -Force}}
  throw
}
