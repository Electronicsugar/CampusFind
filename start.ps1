param([switch]$PortableDatabase, [ValidateSet(8000,8010)][int]$Port=8000)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$campusPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if ($PortableDatabase) {
    & $campusPython -m scripts.local_postgres start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not start.' }
}
& $campusPython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Start PostgreSQL and check .env before launching CampusFind.' }
$env:CAMPUSFIND_ORIGIN="http://127.0.0.1:$Port"
$env:CAMPUSFIND_SECURE_COOKIE='false'
$campusWorker=Start-Process -FilePath $campusPython -ArgumentList @('-m','backend.worker') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
try { & $campusPython -m scripts.serve --port $Port }
finally { Stop-Process -Id $campusWorker.Id -ErrorAction SilentlyContinue }
