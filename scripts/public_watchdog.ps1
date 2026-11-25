function Get-PublicWatchdog([string]$Workspace) {
    $expected=Join-Path $Workspace '.local\public-host-pointer.json'
    return @(Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Where-Object { $_.CommandLine -like '*-m scripts.public_watchdog*' -and $_.CommandLine -like ('*'+$expected+'*') })
}

function Start-PublicWatchdog([string]$Workspace,[string]$InstanceRoot) {
    if (@(Get-PublicWatchdog $Workspace).Count -gt 0) { return }
    $pointerPath=Join-Path $Workspace '.local\public-host-pointer.json'
    $tag=[guid]::NewGuid().ToString('N')
    $watch=Start-Process -FilePath (Join-Path $Workspace '.venv\Scripts\python.exe') -WorkingDirectory $Workspace -ArgumentList @('-m','scripts.public_watchdog','--pointer',('"'+$pointerPath+'"')) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $InstanceRoot ('watchdog-'+$tag+'.out.log')) -RedirectStandardError (Join-Path $InstanceRoot ('watchdog-'+$tag+'.err.log')) -PassThru
    $processPath=Join-Path $InstanceRoot 'processes.json'
    $processes=Get-Content -LiteralPath $processPath | ConvertFrom-Json
    $processes | Add-Member -NotePropertyName watchdog -NotePropertyValue $watch.Id -Force
    $processes | ConvertTo-Json | Set-Content -LiteralPath $processPath -Encoding utf8
    Write-Output 'Automatic public-connection recovery is running while this computer is awake.'
}

function Stop-PublicWatchdog([string]$Workspace) {
    foreach ($process in @(Get-PublicWatchdog $Workspace)) { Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue }
    Write-Output 'Automatic public-connection recovery stopped. Web, worker and database were left running.'
}
