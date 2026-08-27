"""
claude_battery.py — Entry point unico multipiattaforma.

Installato via pip, espone il comando `claude-battery`, che avvia l'app giusta
in base al sistema operativo: menu bar su macOS, system tray su Windows/Linux.
"""

import platform
import sys


def main():
    system = platform.system()
    if system == "Darwin":
        from menubar_mac import ClaudeBatteryApp
        ClaudeBatteryApp().run()
    else:
        # Windows e Linux usano la system tray.
        from tray_windows import ClaudeBatteryTray
        ClaudeBatteryTray().run()


if __name__ == "__main__":
    sys.exit(main())
