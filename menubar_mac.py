"""
menubar_mac.py — macOS menu bar app for Claude Usage Battery.

Shows the battery icon ONLY while a Claude Code session (CLI or desktop app)
is active. Disappears from the menu bar when Claude is not running.
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
    """Exit immediately if another instance is already running."""
    f = open(LOCK_PATH, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)  # another instance is active, exit silently
    return f  # keep file open to hold the lock

ICON_PATH = os.path.join(tempfile.gettempdir(), "claude_battery_icon.png")

# Exact process names that indicate an active Claude session.
_CLAUDE_PROCESS_NAMES = ("claude",)
# Desktop app process name as it appears in pgrep.
_CLAUDE_APP_NAME = "Claude"
# Browser process names that may host Claude (e.g. Claude for Chrome extension).
_BROWSER_PROCESS_NAMES = ("Google Chrome", "Chromium", "Brave Browser", "Arc")

# Path to the "always visible" preference file.
_ALWAYS_VISIBLE_FLAG = os.path.join(tempfile.gettempdir(), "claude_battery_always_visible")


def _always_visible() -> bool:
    return os.path.exists(_ALWAYS_VISIBLE_FLAG)


def _is_claude_active() -> bool:
    """Return True if at least one Claude process (CLI, desktop app, or browser) is running."""
    if _always_visible():
        return True
    try:
        r = subprocess.run(
            ["ps", "-ax", "-o", "comm"],
            capture_output=True, text=True, timeout=5
        )
        names = set(line.strip() for line in r.stdout.splitlines())
        return (
            any(n in names for n in _CLAUDE_PROCESS_NAMES)
            or _CLAUDE_APP_NAME in names
            or any(n in names for n in _BROWSER_PROCESS_NAMES)
        )
    except Exception:
        return False


class ClaudeBatteryApp(rumps.App):
    def __init__(self):
        super().__init__("Claude", title="", quit_button=None)

        # Hide the Python icon from the Dock: the app lives only in the menu bar.
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self.item_5h = rumps.MenuItem("5 hours: —")
        self.item_5h_reset = rumps.MenuItem("   resets: —")
        self.item_week = rumps.MenuItem("Weekly: —")
        self.item_week_reset = rumps.MenuItem("   resets: —")
        self.item_updated = rumps.MenuItem("Updated: never")
        self.item_always_visible = rumps.MenuItem(
            self._always_visible_label(),
            callback=self.toggle_always_visible,
        )
        self.menu = [
            self.item_5h,
            self.item_5h_reset,
            None,
            self.item_week,
            self.item_week_reset,
            None,
            self.item_updated,
            rumps.MenuItem("Refresh now", callback=self.manual_refresh),
            self.item_always_visible,
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

        self._visible = True  # rumps starts visible; first tick decides

        # Fast first tick (1 s) to hide immediately if Claude is not active.
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

    def _always_visible_label(self) -> str:
        return "Always visible: ON" if _always_visible() else "Always visible: OFF (Chrome)"

    def toggle_always_visible(self, _):
        if _always_visible():
            os.remove(_ALWAYS_VISIBLE_FLAG)
        else:
            open(_ALWAYS_VISIBLE_FLAG, "w").close()
        self.item_always_visible.title = self._always_visible_label()
        self.update(None)

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
            self.item_5h.title = "Log in to Claude Code"
            self.item_5h_reset.title = f"   {e}"
            self.item_week.title = "Weekly: —"
            self.item_week_reset.title = "   resets: —"
            return
        except Exception as e:
            self._fails = getattr(self, "_fails", 0) + 1
            if self._fails >= 4 and not getattr(self, "_had_ok", False):
                self._show()
                self.title = " ⚠"
                self.item_updated.title = f"Error: {str(e)[:40]}"
            else:
                self.item_updated.title = "Update failed, retrying…"
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
            self.item_5h.title = f"5 hours — {rem}% remaining  ({fh['used_pct']}% used)"
            self.item_5h_reset.title = f"   resets {human_reset(fh['reset'])}"
        else:
            self.title = " —"
            self.item_5h.title = "5 hours: data unavailable"

        if wk:
            self.item_week.title = (
                f"Weekly — {wk['remaining_pct']}% remaining  ({wk['used_pct']}% used)"
            )
            self.item_week_reset.title = f"   resets {human_reset(wk['reset'])}"

        self.item_updated.title = "Updated: " + st["updated"].astimezone().strftime("%H:%M:%S")


if __name__ == "__main__":
    _lock = _acquire_singleton()
    ClaudeBatteryApp().run()
