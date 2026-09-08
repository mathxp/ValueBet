$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
Set-Location "D:\Proyectos\ValueBet\backend"

$logFile = "D:\Proyectos\ValueBet\backend\logs\pipeline.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

"----- $timestamp -----" | Out-File -FilePath $logFile -Append -Encoding utf8

# Se corre via cmd.exe (no con el call operator de PowerShell) para que stdout/
# stderr se combinen como texto plano, sin que PowerShell envuelva cada línea
# de stderr en un NativeCommandError que ensucia el log.
cmd.exe /c "chcp 65001>nul && `"D:\Proyectos\ValueBet\backend\venv\Scripts\python.exe`" manage.py run_pipeline_once 2>&1" |
    Out-File -FilePath $logFile -Append -Encoding utf8
