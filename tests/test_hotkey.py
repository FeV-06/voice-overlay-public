from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from voice_overlay._platform import create_hotkey_listener


def test_listener_init():
    on_press = MagicMock()
    on_release = MagicMock()
    if sys.platform == "linux":
        from voice_overlay.hotkey import EvdevHotkeyListener
        listener = EvdevHotkeyListener(hotkey="ctrl+shift+v", on_press=on_press, on_release=on_release)
    else:
        listener = create_hotkey_listener("ctrl+shift+v", on_press, on_release)
    assert listener.hotkey == "ctrl+shift+v"


def test_start_stop_cycle():
    on_press = MagicMock()
    on_release = MagicMock()
    if sys.platform == "linux":
        from voice_overlay.hotkey import EvdevHotkeyListener
        listener = EvdevHotkeyListener(hotkey="ctrl+shift+v", on_press=on_press, on_release=on_release)
    else:
        listener = create_hotkey_listener("ctrl+shift+v", on_press, on_release)
    listener.start()
    listener.stop()
