# Levanta el backend Django y lo expone por Cloudflare Tunnel para que la
# Pages Function (valuebet-c7b.pages.dev/api/*) pueda alcanzarlo.
#
# Uso:  .\start_public.ps1            (puerto 8000)
#       .\start_public.ps1 -Port 8001 (si el 8000 está ocupado por otro proyecto)
#
# Al arrancar, cloudflared imprime una URL https://xxxx.trycloudflare.com.
# Copiarla en Cloudflare Pages -> valuebet -> Configuración -> Variables y
# secretos -> BACKEND_URL, y volver a implementar (Implementaciones -> ... ->
# Reintentar implementación). La URL cambia cada vez que se reinicia el tunnel.
param([int]$Port = 8000)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$django = Start-Process -FilePath ".\venv\Scripts\python.exe" `
    -ArgumentList "manage.py", "runserver", "127.0.0.1:$Port", "--noreload" `
    -PassThru -NoNewWindow

try {
    # --http-host-header localhost: Django recibe Host=localhost, que ya está
    # en ALLOWED_HOSTS, sin tener que agregar el dominio del tunnel.
    cloudflared tunnel --url "http://127.0.0.1:$Port" --http-host-header localhost
}
finally {
    Stop-Process -Id $django.Id -ErrorAction SilentlyContinue
}
