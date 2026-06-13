from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


class PlatformBackendError(Exception):
    pass


def create_hotkey_listener(hotkey: str, on_press: Callable, on_release: Callable):
    if sys.platform == "linux":
        try:
            from voice_overlay._platform.hotkey.linux import LinuxEvdevHotkeyListener
        except ImportError as e:
            raise PlatformBackendError(
                "Linux hotkey backend requires 'evdev'. Install with: pip install voice-overlay[linux]"
            ) from e
        return LinuxEvdevHotkeyListener(hotkey, on_press, on_release)
    elif sys.platform == "win32":
        try:
            from voice_overlay._platform.hotkey.windows import WindowsHotkeyListener
        except ImportError as e:
            raise PlatformBackendError(
                "Windows hotkey backend requires ctypes (stdlib)"
            ) from e
        return WindowsHotkeyListener(hotkey, on_press, on_release)
    else:
        raise PlatformBackendError(f"Unsupported platform: {sys.platform}")


def create_text_injector():
    if sys.platform == "linux":
        try:
            from voice_overlay._platform.injection.linux import UinputInjector
        except ImportError as e:
            raise PlatformBackendError(
                "Linux text injection backend requires uinput support"
            ) from e
        return UinputInjector()
    elif sys.platform == "win32":
        try:
            from voice_overlay._platform.injection.windows import WindowsInjector
        except ImportError as e:
            raise PlatformBackendError(
                "Windows text injection backend requires ctypes (stdlib)"
            ) from e
        return WindowsInjector()
    else:
        raise PlatformBackendError(f"Unsupported platform: {sys.platform}")


def acquire_lock() -> bool:
    if sys.platform == "linux":
        try:
            from voice_overlay._platform.lockfile.linux import acquire_lock as _al
        except ImportError as e:
            raise PlatformBackendError(
                "Linux lockfile backend unavailable"
            ) from e
        return _al()
    elif sys.platform == "win32":
        try:
            from voice_overlay._platform.lockfile.windows import acquire_lock as _al
        except ImportError as e:
            raise PlatformBackendError(
                "Windows lockfile backend unavailable"
            ) from e
        return _al()
    else:
        raise PlatformBackendError(f"Unsupported platform: {sys.platform}")


def config_dir() -> Path:
    from voice_overlay._platform.config import config_dir as _cd
    return _cd()


def runtime_dir() -> Path:
    from voice_overlay._platform.config import runtime_dir as _rd
    return _rd()
