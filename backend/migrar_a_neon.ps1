# Copia todos los datos de db.sqlite3 a la base de Neon (una sola vez).
#
# Requisito: DATABASE_URL=postgresql://... ya pegada en backend/.env
# Uso:       cd backend; .\migrar_a_neon.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"  # dumpdata -o escribe con la codificación del sistema (cp1252) si no
$py = ".\venv\Scripts\python.exe"
$dump = Join-Path $env:TEMP "valuebet_sqlite_dump.json"

Write-Host "1/3 Exportando datos de SQLite..."
# DATABASE_URL del entorno tiene prioridad sobre la de .env -> apunta a SQLite.
# (No usar "" : en PowerShell 5.1 asignar "" borra la variable y se leería Neon.)
$env:DATABASE_URL = "sqlite:///db.sqlite3"
& $py manage.py dumpdata --natural-foreign --natural-primary `
    -e contenttypes -e auth.permission -e admin.logentry -e sessions `
    --indent 0 -o $dump
if ($LASTEXITCODE -ne 0) { throw "dumpdata falló" }
Remove-Item Env:DATABASE_URL

Write-Host "2/3 Creando tablas en Neon..."
& $py manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw "migrate falló" }

Write-Host "3/3 Cargando datos en Neon..."
& $py manage.py loaddata $dump
if ($LASTEXITCODE -ne 0) { throw "loaddata falló" }

Remove-Item $dump
Write-Host "Listo: los datos ya estan en Neon."
