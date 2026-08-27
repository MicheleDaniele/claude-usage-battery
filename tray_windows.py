"""
tray_windows.py — App per la system tray di Windows (funziona anche su Linux).

Mostra un'icona a batteria colorata nella tray (in basso a destra, vicino
all'orologio/batteria). Passando il mouse sopra vedi la percentuale rimasta;
col tasto destro apri il menu con i dettagli 5 ore / settimana e i reset.

Avvio:  pythonw tray_windows.py     (pythonw = senza finestra console)
"""

import threading
import time

import pystray

from usage_core import fetch_status, human_reset, AuthError
from battery_icon import draw_battery

REFRESH_SECONDS = 15


class ClaudeBatteryTray:
    def __init__(self):
        self.status = None
        self.error = None
        self.icon = pystray.Icon(
            "claude_battery",
            icon=draw_battery(0, scale=2),
            title="Claude — caricamento…",
            menu=self._build_menu(),
        )

    # Le voci di menu leggono lo stato corrente tramite lambda dinamiche.
    def _build_menu(self):
        def line_5h(_):
            if self.error:
                return self.error
            fh = self.status and self.status["five_hour"]
            if not fh:
                return "5 ore: —"
            return f"5 ore — rimasto {fh['remaining_pct']}% · rinnovo {human_reset(fh['reset'])}"

        def line_week(_):
            wk = self.status and self.status["seven_day"]
            if not wk:
                return "Settimana: —"
            return f"Settimana — rimasto {wk['remaining_pct']}% · rinnovo {human_reset(wk['reset'])}"

        def line_updated(_):
            if not self.status:
                return "Aggiornato: mai"
            return "Aggiornato: " + self.status["updated"].astimezone().strftime("%H:%M:%S")

        return pystray.Menu(
            pystray.MenuItem(line_5h, None, enabled=False),
            pystray.MenuItem(line_week, None, enabled=False),
            pystray.MenuItem(line_updated, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Aggiorna adesso", self.on_refresh),
            pystray.MenuItem("Esci", self.on_quit),
        )

    def on_refresh(self, icon, item):
        self.refresh_once()

    def on_quit(self, icon, item):
        icon.stop()

    def refresh_once(self):
        try:
            self.status = fetch_status()
            self.error = None
            fh = self.status["five_hour"]
            if fh:
                rem = fh["remaining_pct"]
                self.icon.icon = draw_battery(rem, scale=2, charging=rem >= 95)
                self.icon.title = f"Claude — {rem}% (5h) · rinnovo {human_reset(fh['reset'])}"
        except AuthError as e:
            self.error = str(e)
            self.icon.title = "Claude — accedi in Claude Code"
        except Exception as e:
            self.error = f"Errore: {e}"
            self.icon.title = f"Claude — errore"
        self.icon.update_menu()

    def _loop(self):
        while True:
            self.refresh_once()
            time.sleep(REFRESH_SECONDS)

    def run(self):
        threading.Thread(target=self._loop, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    ClaudeBatteryTray().run()
