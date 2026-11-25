$ErrorActionPreference='Stop'
. (Join-Path $PWD 'scripts/public_watchdog.ps1')
$workspacePath=$PWD.Path
$expectedPointer=Join-Path $workspacePath '.local\public-host-pointer.json'
$script:fakeProcesses=@(
    [pscustomobject]@{ProcessId=7;CommandLine=('python -m scripts.public_watchdog --pointer "'+$expectedPointer+'"')},
    [pscustomobject]@{ProcessId=8;CommandLine='python -m scripts.public_process web'},
    [pscustomobject]@{ProcessId=9;CommandLine='python -m scripts.public_watchdog --pointer C:\other\pointer.json'}
)
function Get-CimInstance { param($Filter) return $script:fakeProcesses }
$script:stopped=@()
function Stop-Process { param($Id,$ErrorAction) $script:stopped+= $Id }
function Start-Process { throw 'A duplicate monitor must not be started' }
$found=@(Get-PublicWatchdog $workspacePath)
if ($found.Count -ne 1 -or $found[0].ProcessId -ne 7) { throw 'Workspace isolation failed' }
Start-PublicWatchdog $workspacePath '.tmp'
Stop-PublicWatchdog $workspacePath | Out-Null
if ($script:stopped.Count -ne 1 -or $script:stopped[0] -ne 7) { throw 'Stop targeted unrelated processes' }
foreach ($file in @('repair-public.ps1','start-public.ps1','scripts/public_watchdog.ps1')) {
    $tokens=$null;$errors=$null
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD $file),[ref]$tokens,[ref]$errors) | Out-Null
    if ($errors.Count) { throw ('Invalid syntax: '+$file) }
}
Write-Output 'PowerShell checks passed: workspace isolation, duplicate prevention, safe stop and parser validation.'
