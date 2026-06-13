from __future__ import annotations

import logging
import sys

from voice_overlay._platform import create_hotkey_listener

logger = logging.getLogger(__name__)

if sys.platform == "linux":
    from voice_overlay._platform.hotkey.linux import LinuxEvdevHotkeyListener as EvdevHotkeyListener
else:
    class EvdevHotkeyListener:
        """Linux only."""
        def __init__(self, *args, **kwargs):
            raise RuntimeError("EvdevHotkeyListener is Linux-only")

__all__ = ["EvdevHotkeyListener"]
