# 1016 lab · netmon.ps1 — sample TdxW.exe TCP connections (endpoints + timing)
# Usage: pwsh -File netmon.ps1 -OutDir <dir> -DurationSec <n>
param(
  [Parameter(Mandatory=$true)][string]$OutDir,
  [int]$DurationSec = 300,
  [int]$IntervalMs = 300
)
$ErrorActionPreference = 'SilentlyContinue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$csv = Join-Path $OutDir "netmon_$stamp.csv"
"t_unix,pid,proc,remote_ip,remote_port,state" | Out-File $csv -Encoding utf8
$deadline = (Get-Date).AddSeconds($DurationSec)
while ((Get-Date) -lt $deadline) {
  $t = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
  $procs = Get-Process | Where-Object { $_.Name -imatch '^TdxW' }
  if ($procs) {
    $pids = $procs.Id
    $conns = Get-NetTCPConnection | Where-Object {
      $pids -contains $_.OwningProcess -and $_.RemoteAddress -notmatch '^(127\.|::1|0\.0\.0\.0|::$)'
    }
    foreach ($c in $conns) {
      $pn = ($procs | Where-Object Id -eq $c.OwningProcess | Select-Object -First 1).Name
      "$t,$($c.OwningProcess),$pn,$($c.RemoteAddress),$($c.RemotePort),$($c.State)" |
        Out-File $csv -Append -Encoding utf8
    }
  }
  Start-Sleep -Milliseconds $IntervalMs
}
Write-Output "DONE $csv"
