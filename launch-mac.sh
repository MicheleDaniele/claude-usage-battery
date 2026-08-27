#!/bin/bash
# Avvia la batteria Claude nel menu bar SE non è già in esecuzione.
# Idempotente: richiamato ad ogni avvio di Claude Code (hook SessionStart).
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
