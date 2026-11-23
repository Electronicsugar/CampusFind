param([switch]$Status)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$pointer=Get-Content '.local/public-host-pointer.json' | ConvertFrom-Json
$instanceRoot=[IO.Path]::GetFullPath($pointer.directory)
$allowedRoot=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'CampusFind\public'))+[IO.Path]::DirectorySeparatorChar
if (-not $instanceRoot.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase) -or (Split-Path $instanceRoot -Leaf) -notmatch '^[a-f0-9]{32}$') { throw 'Unexpected private instance directory; refusing to start.' }
try {
    $ready=Invoke-RestMethod ($pointer.origin+'/health/ready') -TimeoutSec 10
    if ($ready.status -eq 'ready') { Write-Output ('CampusFind is online: '+$pointer.origin); return }
} catch { }
if ($Status) { Write-Output 'Public backend is offline. Run this script without -Status to start it.'; return }
if (Get-NetTCPConnection -LocalPort 8020 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8020 is occupied. Inspect existing public processes before restarting; nothing was stopped.' }
$pgctl=Join-Path $PSScriptRoot '.local\postgres\pgsql\bin\pg_ctl.exe'
$pgdata=Join-Path $instanceRoot 'pgdata'
& $pgctl -D $pgdata status *> $null
if ($LASTEXITCODE -ne 0) {
    & $pgctl -D $pgdata -l (Join-Path $instanceRoot 'postgres.log') -o '-h 127.0.0.1 -p 5434' start
    if ($LASTEXITCODE -ne 0) { throw 'Isolated PostgreSQL did not start.' }
}
$tunnelExe=Join-Path $PSScriptRoot '.local\cloudflared\cloudflared-windows-amd64.exe'
$tunnelLog=Join-Path $instanceRoot ('tunnel-'+[guid]::NewGuid().ToString('N')+'.log')
$tunnel=Start-Process -FilePath $tunnelExe -ArgumentList @('tunnel','--url','http://127.0.0.1:8020','--no-autoupdate','--protocol','http2') -WindowStyle Hidden -RedirectStandardError $tunnelLog -PassThru
$backendUrl=$null
for ($attempt=0;$attempt -lt 50;$attempt++) {
    if (Test-Path $tunnelLog) {
        $match=[regex]::Match((Get-Content $tunnelLog -Raw),'https://[a-z0-9-]+\.trycloudflare\.com')
        if ($match.Success) { $backendUrl=$match.Value; break }
    }
    Start-Sleep -Milliseconds 500
}
if (-not $backendUrl) { throw 'A tunnel address was not assigned. Inspect the private log; no database was reset.' }
$configPath=Join-Path $instanceRoot 'runtime.json'
$config=Get-Content $configPath | ConvertFrom-Json
$config.CAMPUSFIND_TRUSTED_HOSTS=([uri]$backendUrl).Host+',localhost'
$config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
$pointer.tunnel=$backendUrl
$pointer | ConvertTo-Json | Set-Content '.local/public-host-pointer.json' -Encoding utf8
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$processes=@{tunnel=$tunnel.Id}
foreach ($mode in @('worker','web')) {
    $process=Start-Process -FilePath $python -WorkingDirectory $PSScriptRoot -ArgumentList @('-m','scripts.public_process','--config',('"'+$configPath+'"'),$mode) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $instanceRoot ($mode+'.out.log')) -RedirectStandardError (Join-Path $instanceRoot ($mode+'.err.log')) -PassThru
    $processes[$mode]=$process.Id
}
$processes | ConvertTo-Json | Set-Content (Join-Path $instanceRoot 'processes.json')
& npx --yes vercel@latest env update CAMPUSFIND_BACKEND_URL --environment production --value $backendUrl --type config --yes --scope code-forge-6dd8
if ($LASTEXITCODE -ne 0) { throw 'Vercel could not update the backend address. Local processes are running; sign in to Vercel before retrying deployment.' }
& npx --yes vercel@latest deploy --prod --yes --scope code-forge-6dd8
if ($LASTEXITCODE -ne 0) { throw 'Vercel deployment failed. The local database and files remain intact.' }
Write-Output ('Public URL: '+$pointer.origin)
