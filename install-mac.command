#!/bin/bash
# macOS installer: creates the venv, installs dependencies and configures
# auto-start at login (LaunchAgent). Double-click to run.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

echo "==> Creating Python environment…"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip -q
./.venv/bin/pip install -q -r requirements-mac.txt

PLIST="$HOME/Library/LaunchAgents/com.claude.usagebattery.plist"
echo "==> Configuring auto-start ($PLIST)…"
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
echo "==> Done! Claude Battery is running in the menu bar and will start automatically at login."
echo "    To uninstall: launchctl unload \"$PLIST\" && rm \"$PLIST\""
