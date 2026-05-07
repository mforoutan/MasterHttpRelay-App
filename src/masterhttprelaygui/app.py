from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QSystemTrayIcon

from .window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MasterHttpRelayVPN")
    app.setOrganizationName("MasterHttpRelayVPN")
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        # System tray support is not guaranteed on every desktop, but the UI
        # still works as a normal window when tray integration is absent.
        pass

    window = MainWindow()
    window.show()
    return app.exec()
