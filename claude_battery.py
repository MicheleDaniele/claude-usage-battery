"""
claude_battery.py — Cross-platform entry point.

Installed via pip, this exposes the `claude-battery` command, which launches
the appropriate front-end based on the current OS:
  - macOS  → menu bar app (menubar_mac.py)
  - others → system tray app (tray_windows.py)
"""

import platform
import sys


def main():
    system = platform.system()
    if system == "Darwin":
        from menubar_mac import ClaudeBatteryApp
        ClaudeBatteryApp().run()
    else:
        from tray_windows import ClaudeBatteryTray
        ClaudeBatteryTray().run()


if __name__ == "__main__":
    sys.exit(main())
