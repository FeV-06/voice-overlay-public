from __future__ import annotations

import logging
import time
import ctypes
from ctypes import wintypes

logger = logging.getLogger(__name__)

VK_CONTROL = 0x11
VK_V = 0x56
VK_SHIFT = 0x10

KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
CF_UNICODETEXT = 13
GMEM_MOVABLE = 0x0002

_CLIPBOARD_RETRIES = 3
_CLIPBOARD_RETRY_DELAY = 0.01
_CHAR_TYPING_DELAY = 0.003


class WindowsInjector:
    def __init__(self):
        pass

    @classmethod
    def is_available(cls) -> bool:
        try:
            return hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32")
        except Exception:
            return False

    def check_permissions(self) -> tuple[bool, str]:
        return True, ""

    def _build_structures(self):
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class _INPUT_UNION(ctypes.Union):
            _fields_ = [
                ("mi", MOUSEINPUT),
                ("ki", KEYBDINPUT),
                ("hi", HARDWAREINPUT),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("union", _INPUT_UNION),
            ]

        return KEYBDINPUT, INPUT, _INPUT_UNION

    def _send_key(self, vk_code: int, press: bool):
        KEYBDINPUT, INPUT, _INPUT_UNION = self._build_structures()

        flags = 0 if press else KEYEVENTF_KEYUP
        ki = KEYBDINPUT(vk_code, 0, flags, 0, 0)
        inp = INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=ki))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _send_ctrl_v(self) -> bool:
        KEYBDINPUT, INPUT, _INPUT_UNION = self._build_structures()
        user32 = ctypes.windll.user32
        user32.SendInput.restype = wintypes.UINT

        key_events = [
            (VK_CONTROL, True),
            (VK_V, True),
            (VK_V, False),
            (VK_CONTROL, False),
        ]

        sent = 0
        for i, (vk, is_press) in enumerate(key_events):
            flags = 0 if is_press else KEYEVENTF_KEYUP
            ki = KEYBDINPUT(vk, 0, flags, 0, 0)
            inp = INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=ki))
            result = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
            if result == 0:
                logger.warning("SendInput failed for key event %d (vk=%d)", i, vk)
            sent += result
            time.sleep(0.01)

        return sent == 4

    def _ensure_restypes(self):
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

    def _copy_to_clipboard(self, text: str) -> bool:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        self._ensure_restypes()

        for attempt in range(_CLIPBOARD_RETRIES):
            if user32.OpenClipboard(None):
                break
            logger.debug("OpenClipboard attempt %d failed, retrying...", attempt + 1)
            time.sleep(_CLIPBOARD_RETRY_DELAY)
        else:
            logger.warning("Failed to open clipboard after %d attempts", _CLIPBOARD_RETRIES)
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

    def _type_char(self, char: str) -> bool:
        user32 = ctypes.windll.user32
        user32.VkKeyScanW.restype = wintypes.SHORT
        user32.VkKeyScanW.argtypes = [wintypes.WCHAR]

        result = user32.VkKeyScanW(char)
        if result == -1:
            logger.debug("VkKeyScanW cannot type character U+%04X", ord(char))
            return False

        vk = result & 0xFF
        needs_shift = bool((result >> 8) & 1)

        KEYBDINPUT, INPUT, _INPUT_UNION = self._build_structures()
        user32.SendInput.restype = wintypes.UINT

        key_events = []
        if needs_shift:
            key_events.append((VK_SHIFT, True))
        key_events.append((vk, True))
        key_events.append((vk, False))
        if needs_shift:
            key_events.append((VK_SHIFT, False))

        sent = 0
        for i, (vk_code, is_press) in enumerate(key_events):
            flags = 0 if is_press else KEYEVENTF_KEYUP
            ki = KEYBDINPUT(vk_code, 0, flags, 0, 0)
            inp = INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=ki))
            result = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
            if result == 0:
                logger.warning("SendInput failed for char 0x%04X event %d", ord(char), i)
                return False
            sent += result
            time.sleep(_CHAR_TYPING_DELAY)

        return sent == len(key_events)

    def type_text(self, text: str) -> bool:
        if not text:
            return True
        try:
            for char in text:
                if not self._type_char(char):
                    return False
            return True
        except Exception:
            logger.exception("Windows type_text failed")
            return False

    def paste_clipboard(self) -> bool:
        try:
            return self._send_ctrl_v()
        except Exception:
            logger.exception("Windows paste_clipboard failed")
            return False
