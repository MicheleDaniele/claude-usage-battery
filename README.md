# Claude Usage Battery 🔋

Una batteria colorata con il **logo di Claude** al centro, che mostra la tua
**percentuale rimasta di Claude Code** accanto alla batteria del sistema:

- **macOS** → barra dei menu, in alto a destra.
- **Windows / Linux** → system tray, in basso a destra.

Il riempimento e il colore indicano quanto ti resta della **finestra di 5 ore**
(quella che determina quando "si rinnovano i token"):
🟢 verde ≥50% · 🟠 giallo 20–49% · 🔴 rosso <20%.
Cliccando l'icona vedi i dettagli e il conto alla rovescia del reset, sia 5 ore
sia settimana. Si aggiorna da sola ogni 15 secondi.

## Come funziona il dato
L'app legge il tuo token di login di Claude Code **in locale** (Portachiavi su
Mac, `~/.claude/.credentials.json` altrove) e interroga lo stesso endpoint
ufficiale usato da `/usage` (`https://api.anthropic.com/api/oauth/usage`). Il
token **non lascia mai il tuo computer** e viene rinnovato in automatico quando
scade. Serve solo aver fatto login in Claude Code almeno una volta.

---

## 📦 Installazione (per chi la riceve)

### Opzione A — con `pipx` (consigliata, comando globale pulito)
`pipx` installa l'app isolata e crea il comando `claude-battery`.
```bash
python3 -m pip install --user pipx     # se non hai pipx
python3 -m pipx ensurepath
# poi, da una delle sorgenti qui sotto:
pipx install claude-usage-battery                       # se pubblicata su PyPI
pipx install git+https://github.com/TUONOME/claude-usage-battery   # da GitHub
pipx install ./claude_usage_battery-1.0.0-py3-none-any.whl          # dal file .whl
```
Avvio:
```bash
claude-battery
```

### Opzione B — con `pip` in un ambiente virtuale
```bash
python3 -m venv .venv
./.venv/bin/pip install claude-usage-battery      # o git+... o il file .whl
./.venv/bin/claude-battery
```

### Opzione C — installer "doppio click" (senza pip)
- **macOS**: doppio click su `install-mac.command` (crea tutto + avvio automatico).
- **Windows**: `powershell -ExecutionPolicy Bypass -File install-windows.ps1`.

## ▶️ Avvio automatico
- **Al login**: lo fanno gli installer (Opzione C) — LaunchAgent su Mac,
  collegamento in Esecuzione automatica su Windows.
- **Quando parte Claude Code** (da terminale, app, ovunque): è già configurato
  sul tuo Mac con un hook `SessionStart` in `~/.claude/settings.json` che lancia
  `launch-mac.sh` (parte solo se non è già attiva). Per replicarlo su un altro
  PC, aggiungi in `~/.claude/settings.json`:
  ```json
  {
    "hooks": {
      "SessionStart": [
        { "hooks": [ { "type": "command", "command": "claude-battery &" } ] }
      ]
    }
  }
  ```

---

## 🚀 Come condividerla (per te, l'autore)

Hai già il pacchetto pronto in `dist/claude_usage_battery-1.0.0-py3-none-any.whl`.
Tre modi, dal più semplice:

1. **Manda il file `.whl`** (WhatsApp, email, drive). Chi lo riceve fa:
   `pipx install ./claude_usage_battery-1.0.0-py3-none-any.whl`.

2. **Metti il progetto su GitHub** e condividi il link. Gli altri fanno:
   `pipx install git+https://github.com/TUONOME/claude-usage-battery`.
   Passi:
   ```bash
   cd ~/ClaudeUsageBattery
   git init && git add . && git commit -m "Claude Usage Battery"
   gh repo create claude-usage-battery --public --source=. --push   # con GitHub CLI
   ```

3. **Pubblicala su PyPI** (così basta `pip install claude-usage-battery`).
   Serve un account PyPI e un token tuo (io non posso pubblicarla per te):
   ```bash
   ./.venv/bin/pip install build twine
   ./.venv/bin/python -m build            # crea dist/*.whl e *.tar.gz
   ./.venv/bin/twine upload dist/*        # chiede il token PyPI
   ```

> Nota: l'app usa endpoint interni di Claude Code. Sono affidabili ma non
> ufficialmente documentati: se Anthropic li cambia, potrebbe servire un piccolo
> aggiornamento di `usage_core.py`.

---

## File del progetto
| File | Ruolo |
|------|-------|
| `usage_core.py`   | Legge il token, chiama l'endpoint usage, rinnova il token |
| `battery_icon.py` | Disegna la batteria colorata con il logo Claude |
| `menubar_mac.py`  | App barra dei menu (macOS, `rumps`) |
| `tray_windows.py` | App system tray (Windows/Linux, `pystray`) |
| `claude_battery.py` | Entry point `claude-battery` (sceglie la piattaforma) |
| `pyproject.toml`  | Configurazione pacchetto pip |
| `install-*.…`     | Installer con avvio automatico |

## Disinstallazione
- **pipx**: `pipx uninstall claude-usage-battery`
- **macOS (installer)**: `launchctl unload ~/Library/LaunchAgents/com.claude.usagebattery.plist && rm ~/Library/LaunchAgents/com.claude.usagebattery.plist`
- **Windows (installer)**: elimina `ClaudeUsageBattery.lnk` da Esecuzione automatica.
- **Hook**: togli la voce `SessionStart` da `~/.claude/settings.json`.
