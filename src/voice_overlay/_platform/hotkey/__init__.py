from __future__ import annotations

"""Hotkey listener backends per platform."""

import sys

if sys.platform == "linux":
    from voice_overlay._platform.hotkey.linux import LinuxEvdevHotkeyListener as HotkeyListenerBackend
elif sys.platform == "win32":
    from voice_overlay._platform.hotkey.windows import WindowsHotkeyListener as HotkeyListenerBackend
