#!/bin/bash
# Installer per macOS: crea il venv, installa le dipendenze e configura
# l'avvio automatico al login (LaunchAgent). Doppio click per eseguire.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

echo "==> Creo l'ambiente Python…"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip -q
./.venv/bin/pip install -q -r requirements-mac.txt

PLIST="$HOME/Library/LaunchAgents/com.claude.usagebattery.plist"
echo "==> Configuro l'avvio automatico ($PLIST)…"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.claude.usagebattery</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/.venv/bin/python</string>
    <string>$DIR/menubar_mac.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>/tmp/claude-usagebattery.log</string>
  <key>StandardOutPath</key><string>/tmp/claude-usagebattery.log</string>
</dict>
</plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo ""
echo "==> Fatto! La batteria Claude è nella barra dei menu e partirà da sola al login."
echo "    Per disinstallare: launchctl unload \"$PLIST\" && rm \"$PLIST\""
