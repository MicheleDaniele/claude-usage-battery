"""
menubar_mac.py — App per la barra dei menu di macOS.

Mostra una batteria colorata + percentuale RIMASTA della finestra di 5 ore
(quella che determina "quando si rinnovano i token"), accanto allo stato
della batteria del Mac. Nel menu a tendina trovi i dettagli e il conto alla
rovescia del reset, sia per le 5 ore sia per la settimana.

Avvio:  python3 menubar_mac.py
"""

import os
import tempfile

import rumps

from usage_core import fetch_status, human_reset, AuthError
from battery_icon import draw_battery

REFRESH_SECONDS = 15
ICON_PATH = os.path.join(tempfile.gettempdir(), "claude_battery_icon.png")


class ClaudeBatteryApp(rumps.App):
    def __init__(self):
        super().__init__("Claude", title=" …", quit_button=None)
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
        # Primo aggiornamento immediato + timer periodico.
        self.timer = rumps.Timer(self.update, REFRESH_SECONDS)
        self.timer.start()
        self.update(None)

    def _set_icon(self, remaining_pct, charging=False):
        img = draw_battery(remaining_pct, scale=4, charging=charging, mono=False)
        img.save(ICON_PATH)
        self.icon = ICON_PATH
        self.template = False  # icona a colori (verde/giallo/rosso)

    def manual_refresh(self, _):
        self.update(None)

    def update(self, _):
        try:
            st = fetch_status()
        except AuthError as e:
            self.title = " login?"
            self.item_5h.title = "Accedi in Claude Code"
            self.item_5h_reset.title = f"   {e}"
            self.item_week.title = "Settimana: —"
            self.item_week_reset.title = "   reset: —"
            return
        except Exception as e:
            self.title = " ⚠"
            self.item_updated.title = f"Errore: {str(e)[:40]}"
            return

        fh = st["five_hour"]
        wk = st["seven_day"]

        if fh:
            rem = fh["remaining_pct"]
            # "in ricarica" quando la finestra è appena ripartita (quasi piena).
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
    ClaudeBatteryApp().run()
