<div align="center">

# 🔋 Claude Usage Battery

**La tua percentuale rimasta di Claude Code, come una batteria — accanto alla batteria del sistema.**

<img src="docs/preview.png" alt="Anteprima: batteria verde, gialla e rossa con il logo Claude" width="620">

*macOS (barra dei menu) · Windows / Linux (system tray) · installabile con `pip`/`pipx`*

</div>

---

## Indice
- [Cos'è](#cosè)
- [Come appare](#come-appare)
- [Come funziona il dato (e la privacy)](#come-funziona-il-dato-e-la-privacy)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
  - [A · pipx (consigliata)](#a--pipx-consigliata)
  - [B · pip in un virtualenv](#b--pip-in-un-virtualenv)
  - [C · installer doppio-click](#c--installer-doppio-click)
- [Avvio automatico](#avvio-automatico)
  - [Quando avvii Claude Code (`claude` nel terminale)](#quando-avvii-claude-code-claude-nel-terminale)
  - [All'accensione del computer](#allaccensione-del-computer)
- [Configurazione](#configurazione)
- [Aggiornare l'app](#aggiornare-lapp)
- [Condividerla con altri](#condividerla-con-altri)
- [Disinstallazione](#disinstallazione)
- [Risoluzione problemi (FAQ)](#risoluzione-problemi-faq)
- [Come è fatta (dettagli tecnici)](#come-è-fatta-dettagli-tecnici)
- [Struttura del progetto](#struttura-del-progetto)
- [Note e limiti](#note-e-limiti)
- [Licenza](#licenza)

---

## Cos'è
`Claude Usage Battery` è una piccola app che vive nella barra di stato del tuo
computer e mostra, come un'icona a batteria, **quanto ti resta del tuo utilizzo
di Claude Code**. Il riempimento e il colore rappresentano la **finestra di 5
ore** (quella che determina quando "si rinnovano i token"). Al centro c'è il
**logo di Claude**, così la distingui a colpo d'occhio dalla batteria di sistema.

Cliccando l'icona vedi i dettagli: percentuale usata/rimasta e **conto alla
rovescia del reset**, sia per le **5 ore** sia per la **settimana**.

## Come appare
| Livello | Colore | Significato |
|:------:|:------:|:------------|
| ≥ 50 % | 🟢 verde  | Sei tranquillo |
| 20–49 % | 🟠 giallo | Occhio, stai consumando |
| < 20 % | 🔴 rosso  | Quasi esaurito, sta per rinnovarsi |

Accanto all'icona compare anche la percentuale in numero (es. `42%`).
L'app si aggiorna da sola ogni **30 secondi**.

## Come funziona il dato (e la privacy)
Questa percentuale **non è salvata in nessun file locale**: Claude Code la
ottiene chiamando un endpoint di Anthropic con il tuo token di login. L'app fa
esattamente la stessa cosa:

1. Legge il tuo **token OAuth locale** — dal **Portachiavi** su macOS (voce
   `Claude Code-credentials`), oppure dal file `~/.claude/.credentials.json` su
   Windows/Linux.
2. Chiama `GET https://api.anthropic.com/api/oauth/usage` (lo stesso endpoint del
   comando `/usage`).
3. Se il token è scaduto, lo **rinnova automaticamente** e riprova.

> 🔒 **Il token non lascia mai il tuo computer.** Viene usato solo per parlare
> con `api.anthropic.com`, come fa già Claude Code. Nessun dato viene inviato a
> terzi. Serve soltanto aver fatto **login in Claude Code almeno una volta**.

## Requisiti
- **Python 3.9+**
- **Claude Code** installato e con login effettuato
- macOS, Windows o Linux con una barra di stato / system tray

---

## Installazione

### A · pipx (consigliata)
`pipx` installa l'app in un ambiente isolato e crea il comando globale
`claude-battery`. È il modo più pulito.

```bash
# 1) installa pipx se non ce l'hai
python3 -m pip install --user pipx
python3 -m pipx ensurepath      # poi riapri il terminale

# 2) installa l'app (scegli UNA sorgente)
pipx install git+https://github.com/MicheleDaniele/claude-usage-battery   # da GitHub
pipx install ./claude_usage_battery-1.0.0-py3-none-any.whl                # dal file .whl
pipx install claude-usage-battery                                         # se su PyPI

# 3) avvia
claude-battery
```

### B · pip in un virtualenv
```bash
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install git+https://github.com/MicheleDaniele/claude-usage-battery
claude-battery
```

### C · installer doppio-click
Se non vuoi toccare il terminale, dopo aver scaricato il progetto:
- **macOS** → doppio click su **`install-mac.command`**
- **Windows** → tasto destro su **`install-windows.ps1`** → *Esegui con PowerShell*
  (oppure `powershell -ExecutionPolicy Bypass -File install-windows.ps1`)

Gli installer creano l'ambiente, installano le dipendenze **e** configurano
l'avvio automatico al login.

---

## Avvio automatico
Puoi collegare la batteria a Claude in due modi (non esclusivi).

### Quando avvii Claude Code (`claude` nel terminale)
Ogni volta che apri una sessione di Claude Code — scrivendo `claude` nel
terminale, aprendo l'IDE o l'app — la batteria parte da sola, grazie a un
**hook `SessionStart`** in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "claude-battery &" } ] }
    ]
  }
}
```

> Se hai installato dalla cartella locale, il comando può puntare a
> `launch-mac.sh` invece di `claude-battery`: fa la stessa cosa. L'hook è
> **idempotente**, quindi non avvia mai due icone.

### All'accensione del computer
Lo configurano gli installer (Opzione C): un *LaunchAgent* su macOS
(`~/Library/LaunchAgents/com.claude.usagebattery.plist`) o un collegamento nella
cartella *Esecuzione automatica* su Windows.

---

## Configurazione
Le impostazioni sono costanti in cima ai file, facili da cambiare:

| Cosa | Dove | Default |
|------|------|---------|
| Intervallo di aggiornamento | `menubar_mac.py` / `tray_windows.py` → `REFRESH_SECONDS` | `30` (secondi) |
| Soglie di colore verde/giallo/rosso | `usage_core.py` → `level_color()` | `50` / `20` |
| Dimensioni e proporzioni dell'icona | `battery_icon.py` → `draw_battery()` | — |

---

## Aggiornare l'app
Dopo aver modificato il codice:

```bash
cd ~/Desktop/ClaudeUsageBattery
# se usi pipx dalla cartella locale:
python -m build                                   # ricrea dist/*.whl
pipx install ./dist/claude_usage_battery-1.0.0-py3-none-any.whl --force

# per aggiornare il repo GitHub:
git add . && git commit -m "descrizione modifica" && git push
```

Chi l'ha installata da GitHub aggiorna con:
```bash
pipx upgrade claude-usage-battery
# oppure: pipx install git+https://github.com/MicheleDaniele/claude-usage-battery --force
```

---

## Condividerla con altri
Dal più semplice:

1. **File `.whl`** — manda `dist/claude_usage_battery-1.0.0-py3-none-any.whl`.
   Chi lo riceve: `pipx install ./claude_usage_battery-1.0.0-py3-none-any.whl`.
2. **Link GitHub** — `pipx install git+https://github.com/MicheleDaniele/claude-usage-battery`.
3. **PyPI** (così basta `pip install claude-usage-battery`). Serve un account
   PyPI e un token tuo:
   ```bash
   pip install build twine
   python -m build
   twine upload dist/*
   ```

---

## Disinstallazione
| Metodo di installazione | Come rimuovere |
|-------------------------|----------------|
| pipx | `pipx uninstall claude-usage-battery` |
| Installer macOS | `launchctl unload ~/Library/LaunchAgents/com.claude.usagebattery.plist && rm ~/Library/LaunchAgents/com.claude.usagebattery.plist` |
| Installer Windows | Elimina `ClaudeUsageBattery.lnk` dalla cartella *Esecuzione automatica* |
| Hook di avvio | Togli la voce `SessionStart` da `~/.claude/settings.json` |

---

## Risoluzione problemi (FAQ)

**Vedo `login?` / "Accedi in Claude Code".**
Non è stato trovato un token valido: apri Claude Code e fai login almeno una
volta, poi clicca *Aggiorna adesso* nel menu dell'icona.

**Ogni tanto compare "Aggiornamento non riuscito".**
Normale: è un intoppo momentaneo di rete o un limite temporaneo di richieste.
L'app tiene l'ultimo valore valido e riprova al ciclo successivo, da sola.

**L'icona non compare nella barra dei menu (macOS).**
Controlla il log: `cat /tmp/claude-usagebattery.log`. Assicurati che l'app abbia
i permessi per leggere il Portachiavi (la prima volta macOS può chiedere conferma).

**Compaiono due icone.**
Ne hai avviate due (es. da pipx e dal venv). Chiudine una dal menu *Esci*; l'hook
di avvio evita i doppioni ai lanci successivi.

**Le percentuali non cambiano.**
Cambiano solo quando consumi/rilasci token: se non stai usando Claude, restano
stabili fino al reset della finestra.

---

## Come è fatta (dettagli tecnici)
- **Linguaggio:** Python, un unico core condiviso + due front-end di barra di stato.
- **macOS:** [`rumps`](https://github.com/jaredks/rumps) per la barra dei menu.
- **Windows/Linux:** [`pystray`](https://github.com/moses-palmer/pystray) per la tray.
- **Icona:** disegnata con `Pillow` in super-sampling e ridotta con anti-aliasing;
  il logo Claude è uno *stencil* attraversato dalla linea di carica, così resta
  leggibile a ogni percentuale.
- **Endpoint usati (interni di Claude Code):**
  - Usage: `GET https://api.anthropic.com/api/oauth/usage`
    (header `Authorization: Bearer …`, `anthropic-beta: oauth-2025-04-20`)
  - Refresh token: `POST https://platform.claude.com/v1/oauth/token`
    (`grant_type=refresh_token`, client id di Claude Code)
  - Risposta: `five_hour` e `seven_day`, ciascuno con `utilization` (percentuale)
    e `resets_at` (data ISO).

## Struttura del progetto
```
ClaudeUsageBattery/
├── usage_core.py        # token locale + chiamata usage + refresh
├── battery_icon.py      # disegno batteria colorata con logo Claude
├── menubar_mac.py       # app barra dei menu (macOS, rumps)
├── tray_windows.py      # app system tray (Windows/Linux, pystray)
├── claude_battery.py    # entry point: comando `claude-battery`
├── pyproject.toml       # pacchetto pip
├── install-mac.command  # installer + avvio automatico (macOS)
├── install-windows.ps1  # installer + avvio automatico (Windows)
├── launch-mac.sh        # launcher idempotente (usato dall'hook)
└── docs/preview.png     # immagine di anteprima
```

## Note e limiti
- L'app usa **endpoint interni** di Claude Code: affidabili ma **non
  documentati ufficialmente**. Se Anthropic li cambia, potrebbe servire un
  piccolo aggiornamento di `usage_core.py`.
- I valori mostrati sono gli stessi del comando `/usage`.

## Licenza
MIT — vedi il campo `license` in `pyproject.toml`. Usala e modificala liberamente.
