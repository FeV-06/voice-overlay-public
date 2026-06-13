from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

logger = logging.getLogger(__name__)


class SystemTray(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._window_shown = True
        self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()

        icon_path = Path(__file__).parent / "mic-icon.svg"
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            logger.warning("Tray icon SVG not found at %s", icon_path)

        self.setToolTip("VoiceOverlay")
        self._build_menu()
        self.activated.connect(self._on_activated)

        # Always try to show — on Qt6/Wayland this uses StatusNotifierItem protocol
        # and may work on GNOME with Background Apps even if isSystemTrayAvailable()
        # returns False
        self.show()

    @property
    def available(self) -> bool:
        return self._tray_available

    def _build_menu(self) -> None:
        menu = QMenu()

        self._show_action = QAction("Show Window")
        self._show_action.triggered.connect(self._on_show_window)
        menu.addAction(self._show_action)

        self._pause_action = QAction("Pause/Resume")
        self._pause_action.setEnabled(False)
        self._pause_action.setToolTip("Coming soon")
        menu.addAction(self._pause_action)

        menu.addSeparator()

        quit_action = QAction("Quit")
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _on_show_window(self) -> None:
        self._toggle_window(force_show=True)

    def _toggle_window(self, force_show: bool = False) -> None:
        parent = self.parent()
        if not parent:
            return

        if force_show or not parent.isVisible():
            parent.show()
            parent.raise_()
            parent.activateWindow()
            self._window_shown = True
        else:
            parent.hide()
            self._window_shown = False

    def _on_quit(self) -> None:
        QApplication.quit()

    def show_notification(self, title: str, message: str) -> None:
        self.showMessage(title, message, QIcon(), 3000)
