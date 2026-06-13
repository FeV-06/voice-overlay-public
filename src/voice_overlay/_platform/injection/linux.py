from __future__ import annotations

import fcntl
import logging
import os
import struct
import time

logger = logging.getLogger(__name__)

UI_DEV_CREATE = 0x5501
UI_SET_EV_BIT = 0x40045564
UI_SET_KEY_BIT = 0x40045565

EV_SYN = 0x00
EV_KEY = 0x01

KEY_ESC = 1
KEY_1 = 2; KEY_2 = 3; KEY_3 = 4; KEY_4 = 5; KEY_5 = 6
KEY_6 = 7; KEY_7 = 8; KEY_8 = 9; KEY_9 = 10; KEY_0 = 11
KEY_MINUS = 12; KEY_EQUAL = 13
KEY_BACKSPACE = 14; KEY_TAB = 15
KEY_Q = 16; KEY_W = 17; KEY_E = 18; KEY_R = 19; KEY_T = 20
KEY_Y = 21; KEY_U = 22; KEY_I = 23; KEY_O = 24; KEY_P = 25
KEY_LEFTBRACE = 26; KEY_RIGHTBRACE = 27
KEY_ENTER = 28
KEY_A = 30; KEY_S = 31; KEY_D = 32; KEY_F = 33; KEY_G = 34
KEY_H = 35; KEY_J = 36; KEY_K = 37; KEY_L = 38
KEY_SEMICOLON = 39; KEY_APOSTROPHE = 40
KEY_GRAVE = 41
KEY_LEFTSHIFT = 42; KEY_BACKSLASH = 43
KEY_Z = 44; KEY_X = 45; KEY_C = 46; KEY_V = 47; KEY_B = 48
KEY_N = 49; KEY_M = 50
KEY_COMMA = 51; KEY_DOT = 52; KEY_SLASH = 53
KEY_RIGHTSHIFT = 54
KEY_LEFTCTRL = 29
KEY_RIGHTCTRL = 97
KEY_LEFTALT = 56
KEY_SPACE = 57
KEY_CAPSLOCK = 58
KEY_LEFT = 105; KEY_RIGHT = 106; KEY_UP = 103; KEY_DOWN = 108

LOWER_MAP = {
    'a': KEY_A, 'b': KEY_B, 'c': KEY_C, 'd': KEY_D, 'e': KEY_E,
    'f': KEY_F, 'g': KEY_G, 'h': KEY_H, 'i': KEY_I, 'j': KEY_J,
    'k': KEY_K, 'l': KEY_L, 'm': KEY_M, 'n': KEY_N, 'o': KEY_O,
    'p': KEY_P, 'q': KEY_Q, 'r': KEY_R, 's': KEY_S, 't': KEY_T,
    'u': KEY_U, 'v': KEY_V, 'w': KEY_W, 'x': KEY_X, 'y': KEY_Y, 'z': KEY_Z,
    '0': KEY_0, '1': KEY_1, '2': KEY_2, '3': KEY_3, '4': KEY_4,
    '5': KEY_5, '6': KEY_6, '7': KEY_7, '8': KEY_8, '9': KEY_9,
    ' ': KEY_SPACE, '\t': KEY_TAB, '\n': KEY_ENTER,
    '-': KEY_MINUS, '=': KEY_EQUAL,
    '[': KEY_LEFTBRACE, ']': KEY_RIGHTBRACE,
    ';': KEY_SEMICOLON, "'": KEY_APOSTROPHE,
    '`': KEY_GRAVE, '\\': KEY_BACKSLASH,
    ',': KEY_COMMA, '.': KEY_DOT, '/': KEY_SLASH,
}

SHIFT_MAP = {
    'A': KEY_A, 'B': KEY_B, 'C': KEY_C, 'D': KEY_D, 'E': KEY_E,
    'F': KEY_F, 'G': KEY_G, 'H': KEY_H, 'I': KEY_I, 'J': KEY_J,
    'K': KEY_K, 'L': KEY_L, 'M': KEY_M, 'N': KEY_N, 'O': KEY_O,
    'P': KEY_P, 'Q': KEY_Q, 'R': KEY_R, 'S': KEY_S, 'T': KEY_T,
    'U': KEY_U, 'V': KEY_V, 'W': KEY_W, 'X': KEY_X, 'Y': KEY_Y, 'Z': KEY_Z,
    '!': KEY_1, '@': KEY_2, '#': KEY_3, '$': KEY_4,
    '%': KEY_5, '^': KEY_6, '&': KEY_7, '*': KEY_8,
    '(': KEY_9, ')': KEY_0,
    '_': KEY_MINUS, '+': KEY_EQUAL,
    '{': KEY_LEFTBRACE, '}': KEY_RIGHTBRACE,
    ':': KEY_SEMICOLON, '"': KEY_APOSTROPHE,
    '~': KEY_GRAVE, '|': KEY_BACKSLASH,
    '<': KEY_COMMA, '>': KEY_DOT, '?': KEY_SLASH,
}

EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

UINPUT_USER_DEV_NAME = b"VoiceOverlay Keyboard\0"
UI_DEV_SETUP = 0x405c5503


class UinputInjector:
    def __init__(self):
        self._fd: int | None = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)
            return True
        except (PermissionError, OSError):
            return False

    def check_permissions(self) -> tuple[bool, str]:
        if not os.path.exists("/dev/uinput"):
            return False, "/dev/uinput does not exist"
        try:
            fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)
            return True, ""
        except PermissionError:
            return False, "No write permission on /dev/uinput (need root or uinput group)"
        except OSError as e:
            return False, f"OS error accessing /dev/uinput: {e}"

    def _open_uinput(self) -> int:
        try:
            fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        except PermissionError:
            raise RuntimeError("Cannot open /dev/uinput — need root or uinput group") from None
        return fd

    def _write_event(self, fd: int, event_type: int, code: int, value: int):
        event = struct.pack(EVENT_FORMAT, 0, 0, event_type, code, value)
        os.write(fd, event)

    def _create_device(self) -> int:
        fd = self._open_uinput()

        fcntl.ioctl(fd, UI_SET_EV_BIT, EV_KEY)

        all_codes = set(LOWER_MAP.values()) | set(SHIFT_MAP.values())
        all_codes.add(KEY_LEFTSHIFT)
        all_codes.add(KEY_LEFTCTRL)
        all_codes.add(KEY_LEFTALT)
        for code in all_codes:
            fcntl.ioctl(fd, UI_SET_KEY_BIT, code)

        uinput_setup = struct.pack("HHHH80sI", 0x03, 0, 0, 0, UINPUT_USER_DEV_NAME, 0)
        fcntl.ioctl(fd, UI_DEV_SETUP, uinput_setup)

        fcntl.ioctl(fd, UI_DEV_CREATE, 0)
        time.sleep(0.15)

        return fd

    def _destroy_device(self, fd: int):
        try:
            fcntl.ioctl(fd, UI_DEV_CREATE, 1)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass

    def _key_event(self, fd: int, code: int, pressed: bool):
        self._write_event(fd, EV_KEY, code, 1 if pressed else 0)
        self._write_event(fd, EV_SYN, 0, 0)

    def _type_char(self, fd: int, char: str):
        if char in LOWER_MAP:
            self._key_event(fd, LOWER_MAP[char], True)
            time.sleep(0.001)
            self._key_event(fd, LOWER_MAP[char], False)
        elif char in SHIFT_MAP:
            self._key_event(fd, KEY_LEFTSHIFT, True)
            time.sleep(0.001)
            self._key_event(fd, SHIFT_MAP[char], True)
            time.sleep(0.001)
            self._key_event(fd, SHIFT_MAP[char], False)
            time.sleep(0.001)
            self._key_event(fd, KEY_LEFTSHIFT, False)
        else:
            pass

    def type_text(self, text: str) -> bool:
        if not text:
            return True
        has_untypeable = any(ch not in LOWER_MAP and ch not in SHIFT_MAP for ch in text)
        if has_untypeable:
            typeable = "".join(ch for ch in text if ch in LOWER_MAP or ch in SHIFT_MAP)
            if typeable:
                logger.debug("Typing typeable portion via uinput")
                self._type_text_uinput(typeable)
            return False

        logger.debug("Typing %d chars via uinput", len(text))
        return self._type_text_uinput(text)

    def _type_text_uinput(self, text: str) -> bool:
        try:
            fd = self._create_device()
        except RuntimeError as e:
            logger.warning("uinput unavailable: %s", e)
            return False

        try:
            for char in text:
                self._type_char(fd, char)
                time.sleep(0.002)
            time.sleep(0.01)
            return True
        finally:
            self._destroy_device(fd)

    def paste_clipboard(self) -> bool:
        try:
            fd = self._create_device()
        except RuntimeError:
            return False

        try:
            self._key_event(fd, KEY_LEFTCTRL, True)
            time.sleep(0.005)
            self._key_event(fd, KEY_V, True)
            time.sleep(0.005)
            self._key_event(fd, KEY_V, False)
            time.sleep(0.005)
            self._key_event(fd, KEY_LEFTCTRL, False)
            time.sleep(0.01)
            return True
        finally:
            self._destroy_device(fd)
