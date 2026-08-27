# Installer per Windows (PowerShell): crea il venv, installa le dipendenze e
# aggiunge un collegamento in Esecuzione automatica (avvio al login).
# Esegui:  powershell -ExecutionPolicy Bypass -File install-windows.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$dir = $PSScriptRoot

Write-Host "==> Creo l'ambiente Python..."
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip -q
& ".\.venv\Scripts\python.exe" -m pip install -q -r requirements-windows.txt

# pythonw.exe avvia senza finestra della console.
$pythonw = Join-Path $dir ".venv\Scripts\pythonw.exe"
$script  = Join-Path $dir "tray_windows.py"

Write-Host "==> Configuro l'avvio automatico..."
$startup = [Environment]::GetFolderPath("Startup")
$lnkPath = Join-Path $startup "ClaudeUsageBattery.lnk"
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $pythonw
$lnk.Arguments  = "`"$script`""
$lnk.WorkingDirectory = $dir
$lnk.Save()

# Avvio subito
Start-Process $pythonw -ArgumentList "`"$script`"" -WorkingDirectory $dir
Write-Host ""
Write-Host "==> Fatto! La batteria Claude e' nella system tray e partira' da sola al login."
Write-Host "    Per disinstallare: elimina $lnkPath"
