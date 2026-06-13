from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class PlatformAutostart:
    def enable(self) -> bool:
        raise NotImplementedError

    def disable(self) -> bool:
        raise NotImplementedError

    def is_enabled(self) -> bool:
        raise NotImplementedError


class LinuxAutostart(PlatformAutostart):
    DESKTOP_FILE_CONTENT = """\
[Desktop Entry]
Type=Application
Name=VoiceOverlay
Exec=voice-overlay
X-GNOME-Autostart-enabled=true
NoDisplay=true
"""

    @staticmethod
    def _autostart_path() -> Path:
        return Path(os.environ.get(
            "XDG_CONFIG_HOME",
            os.path.expanduser("~/.config"),
        )) / "autostart" / "voice-overlay.desktop"

    def enable(self) -> bool:
        path = self._autostart_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.DESKTOP_FILE_CONTENT)
            logger.info("Autostart enabled at %s", path)
            return True
        except OSError as e:
            logger.warning("Failed to enable autostart: %s", e)
            return False

    def disable(self) -> bool:
        path = self._autostart_path()
        if path.exists():
            try:
                path.unlink()
                logger.info("Autostart disabled at %s", path)
                return True
            except OSError as e:
                logger.warning("Failed to disable autostart: %s", e)
                return False
        return True

    def is_enabled(self) -> bool:
        path = self._autostart_path()
        return path.exists()


class WindowsAutostart(PlatformAutostart):
    _RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _VALUE_NAME = "VoiceOverlay"

    def _command(self) -> str:
        try:
            cmd = shutil.which("voice-overlay")
            if cmd:
                return f'"{cmd}"'
        except OSError:
            pass
        return f'"{sys.executable}" -m voice_overlay'

    def enable(self) -> bool:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, self._VALUE_NAME, 0, winreg.REG_SZ, self._command())
            logger.info("Windows autostart enabled")
            return True
        except (ImportError, OSError) as e:
            logger.warning("Failed to enable Windows autostart: %s", e)
            return False

    def disable(self) -> bool:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, self._VALUE_NAME)
            logger.info("Windows autostart disabled")
            return True
        except FileNotFoundError:
            return True
        except (ImportError, OSError) as e:
            logger.warning("Failed to disable Windows autostart: %s", e)
            return False

    def is_enabled(self) -> bool:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._RUN_KEY, 0, winreg.KEY_QUERY_VALUE) as key:
                winreg.QueryValueEx(key, self._VALUE_NAME)
            return True
        except FileNotFoundError:
            return False
        except (ImportError, OSError) as e:
            logger.warning("Failed to check Windows autostart: %s", e)
            return False


class FallbackAutostart(PlatformAutostart):
    def enable(self) -> bool:
        logger.warning("Autostart not supported on platform: %s", sys.platform)
        return False

    def disable(self) -> bool:
        return False

    def is_enabled(self) -> bool:
        return False


def create_autostart() -> PlatformAutostart:
    if sys.platform == "linux":
        return LinuxAutostart()
    elif sys.platform == "win32":
        return WindowsAutostart()
    return FallbackAutostart()
