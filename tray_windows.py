"""
tray_windows.py — Windows / Linux system tray app for Claude Usage Battery.

Shows a color-coded battery icon in the tray (bottom-right, near the clock).
Hovering shows the remaining percentage; right-clicking opens a menu with
5-hour / weekly details and reset countdowns.

Launch:  pythonw tray_windows.py     (pythonw = no console window)
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
            title="Claude — loading…",
            menu=self._build_menu(),
        )

    def _build_menu(self):
        """Build a dynamic menu that reads current state via lambdas."""
        def line_5h(_):
            if self.error:
                return self.error
            fh = self.status and self.status["five_hour"]
            if not fh:
                return "5 hours: —"
            return f"5 hours — {fh['remaining_pct']}% remaining · resets {human_reset(fh['reset'])}"

        def line_week(_):
            wk = self.status and self.status["seven_day"]
            if not wk:
                return "Weekly: —"
            return f"Weekly — {wk['remaining_pct']}% remaining · resets {human_reset(wk['reset'])}"

        def line_updated(_):
            if not self.status:
                return "Updated: never"
            return "Updated: " + self.status["updated"].astimezone().strftime("%H:%M:%S")

        return pystray.Menu(
            pystray.MenuItem(line_5h, None, enabled=False),
            pystray.MenuItem(line_week, None, enabled=False),
            pystray.MenuItem(line_updated, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh now", self.on_refresh),
            pystray.MenuItem("Quit", self.on_quit),
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
                self.icon.title = f"Claude — {rem}% (5h) · resets {human_reset(fh['reset'])}"
        except AuthError as e:
            self.error = str(e)
            self.icon.title = "Claude — log in to Claude Code"
        except Exception as e:
            self.error = f"Error: {e}"
            self.icon.title = "Claude — error"
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
