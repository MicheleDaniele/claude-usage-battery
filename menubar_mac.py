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

from usage_core import (fetch_all_accounts, fetch_account_info, human_reset,
                        _list_keychain_services, service_label)
from battery_icon import draw_battery

LOCK_PATH = os.path.join(tempfile.gettempdir(), "claude_battery.lock")
REFRESH_SECONDS = 60


def _acquire_singleton():
    """Exit immediately if another instance is already running."""
    f = open(LOCK_PATH, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)
    return f


ICON_PATH = os.path.join(tempfile.gettempdir(), "claude_battery_icon.png")

_CLAUDE_PROCESS_NAMES = ("claude",)
_CLAUDE_APP_NAME = "Claude"
_BROWSER_PROCESS_NAMES = ("Google Chrome", "Chromium", "Brave Browser", "Arc")
_ALWAYS_VISIBLE_FLAG = os.path.join(tempfile.gettempdir(), "claude_battery_always_visible")


def _always_visible() -> bool:
    return os.path.exists(_ALWAYS_VISIBLE_FLAG)


def _is_claude_active() -> bool:
    if _always_visible():
        return True
    try:
        r = subprocess.run(["ps", "-ax", "-o", "comm"], capture_output=True, text=True, timeout=5)
        # ps on macOS returns full paths (e.g. /Applications/Google Chrome.app/.../Google Chrome)
        # so we must compare against the basename, not the full path.
        basenames = {os.path.basename(line.strip()) for line in r.stdout.splitlines() if line.strip()}
        return (
            any(n in basenames for n in _CLAUDE_PROCESS_NAMES)
            or _CLAUDE_APP_NAME in basenames
            or any(n in basenames for n in _BROWSER_PROCESS_NAMES)
        )
    except Exception:
        return False


# Per account the menu shows (when multi-account):
#   [email — Subscription]      ← header (disabled)
#   5 hours — X% remaining (Y% used)
#      resets in Zh Mm
#   Weekly — X% remaining (Y% used)
#      resets in Xd Yh
#
# Single account: same but without the header row.

class _AccountRows:
    """Holds the rumps menu items for one account."""

    # rumps keys menu items by title; duplicate titles collapse entries.
    # We suffix every title with (idx+1) invisible zero-width spaces so all
    # items remain unique in the rumps dict regardless of display text.

    def __init__(self, header: rumps.MenuItem | None,
                 item_5h: rumps.MenuItem, item_5h_reset: rumps.MenuItem,
                 item_week: rumps.MenuItem, item_week_reset: rumps.MenuItem,
                 plan_label: str = "", idx: int = 0):
        self.header = header
        self.item_5h = item_5h
        self.item_5h_reset = item_5h_reset
        self.item_week = item_week
        self.item_week_reset = item_week_reset
        self._plan_label = plan_label
        self._u = "​" * (idx + 1)  # unique invisible suffix

    @staticmethod
    def _vis(item: rumps.MenuItem, visible: bool):
        item._menuitem.setHidden_(not visible)

    def as_list(self) -> list:
        rows = []
        if self.header is not None:
            rows.append(self.header)
        rows += [self.item_5h, self.item_5h_reset, self.item_week, self.item_week_reset]
        return rows

    def set_loading(self, label: str):
        if self.header is not None:
            self.header.title = self._plan_label + self._u
        self.item_5h.title = "5 hours: —" + self._u
        self.item_5h_reset.title = "   resets: —" + self._u
        self.item_week.title = "Weekly: —" + self._u
        self.item_week_reset.title = "   resets: —" + self._u

    def set_error(self, msg: str):
        if self.header is not None:
            self.header.title = self._plan_label + self._u
        self.item_5h.title = msg + self._u
        _AccountRows._vis(self.item_5h_reset, False)
        _AccountRows._vis(self.item_week, False)
        _AccountRows._vis(self.item_week_reset, False)

    def set_data(self, fh: dict | None, wk: dict | None, stale: bool = False):
        stale_tag = "  (cached)" if stale else ""
        _AccountRows._vis(self.item_5h_reset, fh is not None)
        _AccountRows._vis(self.item_week, True)
        _AccountRows._vis(self.item_week_reset, wk is not None)
        if fh:
            self.item_5h.title = (
                f"5 hours — {fh['remaining_pct']}% remaining"
                f"  ({fh['used_pct']}% used){stale_tag}" + self._u
            )
            self.item_5h_reset.title = f"   resets {human_reset(fh['reset'])}" + self._u
        else:
            self.item_5h.title = f"5 hours: no data{stale_tag}" + self._u
        if wk:
            self.item_week.title = (
                f"Weekly — {wk['remaining_pct']}% remaining"
                f"  ({wk['used_pct']}% used){stale_tag}" + self._u
            )
            self.item_week_reset.title = f"   resets {human_reset(wk['reset'])}" + self._u
        else:
            self.item_week.title = "Weekly: —" + self._u


class ClaudeBatteryApp(rumps.App):
    def __init__(self):
        super().__init__("Claude", title="", quit_button=None)
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self._account_services = _list_keychain_services()

        # Cache: svc -> last successful fetch result
        self._cache: dict[str, dict] = {}
        # Cache: svc -> {"email", "subscription_type"}
        self._info_cache: dict[str, dict] = {}

        self._rows: dict[str, _AccountRows] = {}
        self.item_updated = rumps.MenuItem("Updated: never")
        self.item_always_visible = rumps.MenuItem(
            self._always_visible_label(), callback=self.toggle_always_visible
        )

        menu_items: list = []
        for i, svc in enumerate(self._account_services):
            if i > 0:
                menu_items.append(None)
            label = service_label(svc)
            u = "​" * (i + 1)  # same invisible suffix used in _AccountRows
            header = rumps.MenuItem(label + u)
            rows = _AccountRows(
                header=header,
                item_5h=rumps.MenuItem("5 hours: —" + u),
                item_5h_reset=rumps.MenuItem("   resets: —" + u),
                item_week=rumps.MenuItem("Weekly: —" + u),
                item_week_reset=rumps.MenuItem("   resets: —" + u),
                plan_label=label,
                idx=i,
            )
            rows.set_loading("loading…")
            self._rows[svc] = rows
            menu_items += rows.as_list()

        menu_items += [
            None,
            self.item_updated,
            rumps.MenuItem("Refresh now", callback=self.manual_refresh),
            self.item_always_visible,
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]
        self.menu = menu_items

        self._visible = True

        self._init_timer = rumps.Timer(self._first_tick, 1)
        self._init_timer.start()
        self.timer = rumps.Timer(self.update, REFRESH_SECONDS)
        self.timer.start()

    def _first_tick(self, _):
        self._init_timer.stop()
        self.update(None)

    def _show(self):
        if not self._visible:
            self._nsapp.nsstatusitem.setVisible_(True)
            self._visible = True

    def _hide(self):
        if self._visible:
            self._nsapp.nsstatusitem.setVisible_(False)
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

    def _header_title(self, svc: str) -> str:
        info = self._info_cache.get(svc)
        if info and info.get("email"):
            return f"{info['email']} — {info['subscription_type']}"
        return service_label(svc)

    def update(self, _):
        if not _is_claude_active():
            self._hide()
            return

        accounts = fetch_all_accounts()

        # Separate fresh vs transient-error results; update cache
        fresh_svcs: set[str] = set()
        for acct in accounts:
            svc = acct["service"]
            if acct["error"] is None:
                self._cache[svc] = acct
                fresh_svcs.add(svc)
                # Fetch account info once (email) if not yet cached
                if svc not in self._info_cache:
                    try:
                        self._info_cache[svc] = fetch_account_info(svc)
                    except Exception:
                        self._info_cache[svc] = {"email": "", "subscription_type": service_label(svc)}

        active_svcs = {svc for svc in self._account_services if svc in self._cache}

        if not active_svcs:
            self._show()
            self.title = " login?"
            for svc, rows in self._rows.items():
                if rows.header is not None:
                    rows.header.title = self._header_title(svc) + rows._u
                rows.set_error("Log in to Claude Code")
            return

        self._show()

        # Title bar icon: most critical (lowest remaining) 5h across active accounts
        primary_fh = None
        for svc in active_svcs:
            fh = self._cache[svc].get("five_hour")
            if fh and (primary_fh is None or fh["remaining_pct"] < primary_fh["remaining_pct"]):
                primary_fh = fh

        if primary_fh:
            rem = primary_fh["remaining_pct"]
            self._set_icon(rem, charging=rem >= 95)
            self.title = f" {rem}%"
        else:
            self.title = " —"

        # Update per-account rows
        for svc, rows in self._rows.items():
            if rows.header is not None:
                rows.header.title = self._header_title(svc) + rows._u
            if svc not in self._cache:
                rows.set_error("not logged in")
                continue
            cached = self._cache[svc]
            rows.set_data(
                fh=cached.get("five_hour"),
                wk=cached.get("seven_day"),
                stale=svc not in fresh_svcs,
            )

        # Timestamp from most recent successful fetch
        latest = max(
            (self._cache[s] for s in active_svcs if self._cache[s].get("updated")),
            key=lambda a: a["updated"],
            default=None,
        )
        if latest:
            self.item_updated.title = (
                "Updated: " + latest["updated"].astimezone().strftime("%H:%M:%S")
            )


if __name__ == "__main__":
    _acquire_singleton()
    ClaudeBatteryApp().run()
