$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Falta el entorno .venv. Consulta README.md.' }
$mysql = 'C:\wamp64\bin\mysql\mysql9.1.0\bin\mysqld.exe'
function Test-LocalPort([int]$Port) {
    $probe = New-Object System.Net.Sockets.TcpClient
    try { $probe.Connect('127.0.0.1',$Port); return $true } catch { return $false } finally { $probe.Dispose() }
}
$listener = Test-LocalPort 3307
if (-not $listener) {
    if (-not (Test-Path $mysql)) { throw 'No se encontro mysqld.exe. Ajusta la ruta en INICIAR.ps1.' }
    $data = (Join-Path $PSScriptRoot '.runtime\mysql').Replace('\','/')
    if (-not (Test-Path (Join-Path $data 'auto.cnf'))) { throw 'Falta el directorio de datos de MySQL. Consulta README.md.' }
    Start-Process -FilePath $mysql -ArgumentList @('--no-defaults','--basedir=C:/wamp64/bin/mysql/mysql9.1.0',("--datadir=`"$data`""),'--port=3307','--bind-address=127.0.0.1','--mysqlx=OFF','--console') -WindowStyle Hidden -RedirectStandardOutput '.runtime\logs\mysql.log' -RedirectStandardError '.runtime\logs\mysql-error.log'
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $client = New-Object System.Net.Sockets.TcpClient
        try { $client.Connect('127.0.0.1',3307); $ready=$true } catch { Start-Sleep -Milliseconds 500 } finally { $client.Dispose() }
        if ($ready) { break }
    }
    if (-not $ready) { throw 'MySQL no inicio. Revisa .runtime/logs/mysql-error.log.' }
}
$env:PYTHONIOENCODING='utf-8'
& $python scripts/migrate_areas.py
if ($LASTEXITCODE -ne 0) { throw 'No se pudo actualizar la estructura de areas.' }
if (Test-LocalPort 5000) { Write-Host 'Sistema disponible en http://127.0.0.1:5000'; return }
& $python -m waitress --listen=127.0.0.1:5000 app:app
