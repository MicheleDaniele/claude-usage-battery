#!/bin/bash
# Start the Claude Battery in the menu bar only if not already running.
# Idempotent: called on every Claude Code session start (SessionStart hook).
DIR="$(cd "$(dirname "$0")" && pwd)"

# Già attiva? (sia versione pipx 'claude-battery' sia venv 'menubar_mac.py')
if pgrep -f "claude-battery" >/dev/null 2>&1 || pgrep -f "menubar_mac.py" >/dev/null 2>&1; then
  exit 0
fi

# Preferisci il comando installato con pip/pipx; altrimenti usa il venv locale.
if command -v claude-battery >/dev/null 2>&1; then
  nohup claude-battery >/tmp/claude-usagebattery.log 2>&1 &
else
  nohup "$DIR/.venv/bin/python" "$DIR/menubar_mac.py" >/tmp/claude-usagebattery.log 2>&1 &
fi
exit 0
