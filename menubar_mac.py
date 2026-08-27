"""
menubar_mac.py — App per la barra dei menu di macOS.

Mostra la batteria SOLO quando una sessione Claude Code (CLI o app) è attiva.
Scompare dalla barra quando Claude non è in uso.
"""

import fcntl
import os
import subprocess
import sys
import tempfile

import rumps
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

from usage_core import fetch_status, human_reset, AuthError
from battery_icon import draw_battery

LOCK_PATH = os.path.join(tempfile.gettempdir(), "claude_battery.lock")
REFRESH_SECONDS = 15


def _acquire_singleton():
    """Esce subito se un'altra istanza è già in esecuzione."""
    f = open(LOCK_PATH, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)  # istanza già attiva, chiudi silenziosamente
    return f  # tieni il file aperto per mantenere il lock
ICON_PATH = os.path.join(tempfile.gettempdir(), "claude_battery_icon.png")

# Processi che indicano sessione Claude attiva (nome esatto del binario).
_CLAUDE_PROCESS_NAMES = ("claude",)
# Nome del processo dell'app desktop Claude (come appare in pgrep).
_CLAUDE_APP_NAME = "Claude"


def _is_claude_active() -> bool:
    """True se almeno un processo Claude (CLI o app desktop) è in esecuzione."""
    try:
        r = subprocess.run(
            ["ps", "-ax", "-o", "comm"],
            capture_output=True, text=True, timeout=5
        )
        names = set(line.strip() for line in r.stdout.splitlines())
        return any(n in names for n in _CLAUDE_PROCESS_NAMES) or _CLAUDE_APP_NAME in names
    except Exception:
        return False


class ClaudeBatteryApp(rumps.App):
    def __init__(self):
        super().__init__("Claude", title="", quit_button=None)

        # Nasconde l'icona Python dal Dock: l'app gira solo nella menu bar.
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self.item_5h = rumps.MenuItem("5 ore: —")
        self.item_5h_reset = rumps.MenuItem("   reset: —")
        self.item_week = rumps.MenuItem("Settimana: —")
        self.item_week_reset = rumps.MenuItem("   reset: —")
        self.item_updated = rumps.MenuItem("Aggiornato: mai")
        self.menu = [
            self.item_5h,
            self.item_5h_reset,
            None,
            self.item_week,
            self.item_week_reset,
            None,
            self.item_updated,
            rumps.MenuItem("Aggiorna adesso", callback=self.manual_refresh),
            None,
            rumps.MenuItem("Esci", callback=rumps.quit_application),
        ]

        self._visible = True  # rumps parte visibile; il primo tick decide

        # Primo tick rapido (1s) per nascondersi subito se Claude non è attivo.
        self._init_timer = rumps.Timer(self._first_tick, 1)
        self._init_timer.start()

        self.timer = rumps.Timer(self.update, REFRESH_SECONDS)
        self.timer.start()

    def _first_tick(self, _):
        self._init_timer.stop()
        self.update(None)

    def _show(self):
        if not self._visible:
            self._status_item.setVisible_(True)
            self._visible = True

    def _hide(self):
        if self._visible:
            self._status_item.setVisible_(False)
            self._visible = False

    def _set_icon(self, remaining_pct, charging=False):
        img = draw_battery(remaining_pct, scale=4, charging=charging, mono=False)
        img.save(ICON_PATH)
        self.icon = ICON_PATH
        self.template = False

    def manual_refresh(self, _):
        self.update(None)

    def update(self, _):
        if not _is_claude_active():
            self._hide()
            return

        try:
            st = fetch_status()
        except AuthError as e:
            self._show()
            self.title = " login?"
            self.item_5h.title = "Accedi in Claude Code"
            self.item_5h_reset.title = f"   {e}"
            self.item_week.title = "Settimana: —"
            self.item_week_reset.title = "   reset: —"
            return
        except Exception as e:
            self._fails = getattr(self, "_fails", 0) + 1
            if self._fails >= 4 and not getattr(self, "_had_ok", False):
                self._show()
                self.title = " ⚠"
                self.item_updated.title = f"Errore: {str(e)[:40]}"
            else:
                self.item_updated.title = "Aggiornamento non riuscito, riprovo…"
            return

        self._fails = 0
        self._had_ok = True
        self._show()

        fh = st["five_hour"]
        wk = st["seven_day"]

        if fh:
            rem = fh["remaining_pct"]
            self._set_icon(rem, charging=rem >= 95)
            self.title = f" {rem}%"
            self.item_5h.title = f"5 ore — rimasto {rem}%  (usato {fh['used_pct']}%)"
            self.item_5h_reset.title = f"   si rinnova {human_reset(fh['reset'])}"
        else:
            self.title = " —"
            self.item_5h.title = "5 ore: dato non disponibile"

        if wk:
            self.item_week.title = (
                f"Settimana — rimasto {wk['remaining_pct']}%  (usato {wk['used_pct']}%)"
            )
            self.item_week_reset.title = f"   si rinnova {human_reset(wk['reset'])}"

        self.item_updated.title = "Aggiornato: " + st["updated"].astimezone().strftime("%H:%M:%S")


if __name__ == "__main__":
    _lock = _acquire_singleton()
    ClaudeBatteryApp().run()
