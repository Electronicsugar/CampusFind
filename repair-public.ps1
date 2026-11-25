param([switch]$Force)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$pointerPath=Join-Path $PSScriptRoot '.local/public-host-pointer.json'
$pointer=Get-Content -LiteralPath $pointerPath | ConvertFrom-Json
$instanceRoot=[IO.Path]::GetFullPath($pointer.directory)
$allowedRoot=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'CampusFind\public'))+[IO.Path]::DirectorySeparatorChar
if (-not $instanceRoot.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase) -or (Split-Path $instanceRoot -Leaf) -notmatch '^[a-f0-9]{32}$') { throw 'Unexpected private instance directory.' }
if ([uri]$pointer.origin -and $pointer.origin -ne 'https://campusfind-alpha-nine.vercel.app') { throw 'Unexpected public origin.' }
function Test-Ready([string]$url,[hashtable]$headers=@{}) {
    try { return (Invoke-RestMethod ($url+'/health/ready') -Headers $headers -TimeoutSec 10).status -eq 'ready' } catch { return $false }
}
$mutexName='Local\CampusFindRepair'+(Split-Path $instanceRoot -Leaf)
$mutex=New-Object System.Threading.Mutex($false,$mutexName)
$acquired=$false
try {
    try { $acquired=$mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired=$true }
    if (-not $acquired) { throw 'Another public repair is already running.' }
    if (-not $Force -and (Test-Ready $pointer.origin)) { Write-Output 'Public connection is already healthy.'; return }
    if (-not (Test-Ready 'http://127.0.0.1:8020' @{Host='localhost'})) { throw 'Local backend is not ready. Connection repair leaves database and worker untouched.' }
    $configPath=Join-Path $instanceRoot 'runtime.json'
    $listener=Get-NetTCPConnection -LocalPort 8020 -State Listen | Select-Object -First 1
    $publicWeb=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$listener.OwningProcess)
    if ($publicWeb.CommandLine -notlike '*scripts.public_process*' -or $publicWeb.CommandLine -notlike ('*'+$configPath+'*') -or $publicWeb.CommandLine -notmatch '\bweb\s*$') { throw 'Unexpected listener; nothing stopped.' }
    $tunnelExe=Join-Path $PSScriptRoot '.local\cloudflared\cloudflared-windows-amd64.exe'
    $tunnelId=$null
    $backendUrl=$pointer.tunnel
    if (-not $Force -and -not (Test-Ready $backendUrl)) {
        $currentConfig=Get-Content -LiteralPath $configPath | ConvertFrom-Json
        $currentHost=($currentConfig.CAMPUSFIND_TRUSTED_HOSTS -split ',')[0]
        if ($currentHost -match '^[a-z0-9-]+\.trycloudflare\.com$' -and (Test-Ready ('https://'+$currentHost))) {
            $backendUrl='https://'+$currentHost
            $tunnelId=(Get-Content -LiteralPath (Join-Path $instanceRoot 'processes.json') | ConvertFrom-Json).tunnel
        }
    }
    # Reuse an already healthy replacement if a prior Vercel update failed.
    if ($Force -or -not (Test-Ready $backendUrl)) {
        $tag=[guid]::NewGuid().ToString('N')
        $tunnelLog=Join-Path $instanceRoot ('tunnel-'+$tag+'.log')
        $tunnel=Start-Process -FilePath $tunnelExe -ArgumentList @('tunnel','--url','http://127.0.0.1:8020','--no-autoupdate','--protocol','http2') -WindowStyle Hidden -RedirectStandardError $tunnelLog -PassThru
        $tunnelId=$tunnel.Id;$backendUrl=$null
        for ($attempt=0;$attempt -lt 50;$attempt++) {
            if (Test-Path -LiteralPath $tunnelLog) {
                $logText=Get-Content -LiteralPath $tunnelLog -Raw
                if (-not [string]::IsNullOrEmpty($logText)) {
                    $match=[regex]::Match($logText,'https://[a-z0-9-]+\.trycloudflare\.com')
                    if ($match.Success) { $backendUrl=$match.Value; break }
                }
            }
            Start-Sleep -Milliseconds 500
        }
        if (-not $backendUrl) { throw 'Replacement tunnel did not receive an address.' }
        $config=Get-Content -LiteralPath $configPath | ConvertFrom-Json
        $config.CAMPUSFIND_TRUSTED_HOSTS=([uri]$backendUrl).Host+',localhost'
        $config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
        Stop-Process -Id $publicWeb.ProcessId
        $web=Start-Process -FilePath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -WorkingDirectory $PSScriptRoot -ArgumentList @('-m','scripts.public_process','--config',('"'+$configPath+'"'),'web') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $instanceRoot ('web-'+$tag+'.out.log')) -RedirectStandardError (Join-Path $instanceRoot ('web-'+$tag+'.err.log')) -PassThru
        $processPath=Join-Path $instanceRoot 'processes.json'
        $processes=Get-Content -LiteralPath $processPath | ConvertFrom-Json
        $processes.web=$web.Id;$processes.tunnel=$tunnelId
        $processes | ConvertTo-Json | Set-Content -LiteralPath $processPath -Encoding utf8
        $ready=$false
        $deadline=[DateTime]::UtcNow.AddSeconds(90)
        while ([DateTime]::UtcNow -lt $deadline) {
            if (Test-Ready $backendUrl) { $ready=$true;break }
            Start-Sleep -Seconds 2
        }
        if (-not $ready) { throw 'Replacement connection is not ready; no Vercel deployment was activated.' }
    }
    $pointer.tunnel=$backendUrl
    $pointer | ConvertTo-Json | Set-Content -LiteralPath $pointerPath -Encoding utf8
    & npx --yes vercel@latest env update CAMPUSFIND_BACKEND_URL --environment production --value $backendUrl --type secret --yes --scope code-forge-6dd8
    if ($LASTEXITCODE -ne 0) { throw 'Vercel backend setting could not be updated.' }
    & npx --yes vercel@latest deploy --prod --yes --scope code-forge-6dd8
    if ($LASTEXITCODE -ne 0) { throw 'Vercel deployment failed; local reports remain intact.' }
    if (-not (Test-Ready $pointer.origin)) { throw 'Public verification failed after deployment.' }
    # Retire only our exact loopback-8020 quick-tunnel executable, never other tunnels.
    if ($tunnelId) {
        Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $tunnelExe -and $_.ProcessId -ne $tunnelId -and $_.CommandLine -match '--url\s+http://127\.0\.0\.1:8020(?:\s|$)' } | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    }
    Write-Output ('Public connection restored and verified: '+$pointer.origin)
} finally {
    if ($acquired) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
