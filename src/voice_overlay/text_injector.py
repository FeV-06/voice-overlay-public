from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time

from voice_overlay._platform import create_text_injector

logger = logging.getLogger(__name__)


class TextInjector:
    def __init__(self):
        self.display_server = self._detect_display_server()
        self._backend = create_text_injector()
        logger.debug("TextInjector: display_server=%s", self.display_server)

    @staticmethod
    def _detect_display_server() -> str:
        if os.name == "nt":
            return "windows"
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session_type == "wayland":
            return "wayland"
        elif session_type == "x11":
            return "x11"
        elif "WAYLAND_DISPLAY" in os.environ:
            return "wayland"
        elif "DISPLAY" in os.environ:
            return "x11"
        return "unknown"

    def inject(self, text: str) -> bool:
        if not text:
            return True
        logger.debug("inject(%d chars) via %s", len(text), self.display_server)

        typed = self._backend.type_text(text)
        if typed:
            return True

        logger.debug("backend could not type all chars, using clipboard paste")
        copied = self._copy_to_clipboard(text)
        if copied and self._backend.paste_clipboard():
            return True

        logger.warning("Text copied to clipboard only (paste manually: Ctrl+V)")
        return False

    def _copy_to_clipboard(self, text: str) -> bool:
        if os.name == "nt":
            return self._windows_copy_to_clipboard(text)

        if self.display_server == "wayland":
            tool = shutil.which("wl-copy")
            if tool:
                subprocess.run(["wl-copy", text])
                return True
        elif self.display_server == "x11":
            tool = shutil.which("xclip")
            if tool:
                subprocess.run(["xclip", "-selection", "c"], input=text, text=True)
                return True
        return False

    @staticmethod
    def _windows_copy_to_clipboard(text: str) -> bool:
        import ctypes
        from ctypes import wintypes

        CF_UNICODETEXT = 13
        GMEM_MOVABLE = 0x0002

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        user32.OpenClipboard.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.restype = wintypes.BOOL
        kernel32.GlobalAlloc.restype = wintypes.HANDLE
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
        kernel32.GlobalFree.restype = wintypes.HANDLE
        kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

        for attempt in range(3):
            if user32.OpenClipboard(None):
                break
            time.sleep(0.01)
        else:
            logger.warning("Failed to open clipboard after 3 attempts")
            return False

        try:
            user32.EmptyClipboard()

            text_bytes = text.encode("utf-16-le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(GMEM_MOVABLE, len(text_bytes))
            if not h_mem:
                logger.warning("GlobalAlloc failed")
                return False

            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                logger.warning("GlobalLock failed")
                kernel32.GlobalFree(h_mem)
                return False

            ctypes.memmove(p_mem, text_bytes, len(text_bytes))
            kernel32.GlobalUnlock(h_mem)

            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        finally:
            user32.CloseClipboard()

        return True
