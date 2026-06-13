from __future__ import annotations

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class WindowsHotkeyListener:
    def __init__(self, hotkey: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self.hotkey = hotkey
        self._on_press = on_press
        self._on_release = on_release
        self._listener = None
        self._thread: threading.Thread | None = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pynput.keyboard  # noqa: F401
            return True
        except ImportError:
            return False

    def check_permissions(self) -> tuple[bool, str]:
        return True, ""

    def _run(self):
        import pynput.keyboard

        parts = self.hotkey.lower().replace(" ", "").split("+")
        trigger_key = parts[-1]
        modifier_keys = set(parts[:-1])

        held = set()
        triggered = False

        _SPECIAL_CHARS = {" ": "space", "\t": "tab", "\r": "enter", "\n": "enter"}

        def _key_name(key) -> str | None:
            try:
                if hasattr(key, "char") and key.char is not None:
                    ch = key.char.lower()
                    if ch in _SPECIAL_CHARS:
                        return _SPECIAL_CHARS[ch]
                    return ch
                if hasattr(key, "name") and key.name:
                    return key.name.lower()
            except (AttributeError, ValueError):
                return None
            return None

        def on_press(key):
            nonlocal triggered
            k = _key_name(key)
            if k is None:
                return
            for mod in modifier_keys:
                if mod in k or k in mod:
                    held.add(mod)
            if k == trigger_key and held == modifier_keys and not triggered:
                triggered = True
                logger.debug("HOTKEY TRIGGERED via pynput: %s", self.hotkey)
                self._on_press()

        def on_release(key):
            nonlocal triggered
            k = _key_name(key)
            if k is None:
                return
            for mod in modifier_keys:
                if mod in k or k in mod:
                    held.discard(mod)
            if k == trigger_key and triggered:
                triggered = False
                logger.debug("HOTKEY RELEASED via pynput: %s", self.hotkey)
                self._on_release()

        with pynput.keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            self._listener = listener
            listener.join()

    def start(self):
        logger.debug("Starting Windows hotkey listener for '%s'", self.hotkey)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        logger.debug("Stopping Windows hotkey listener")
        if self._listener is not None:
            self._listener.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
