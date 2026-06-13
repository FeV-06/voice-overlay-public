from __future__ import annotations

import logging
import os
import struct
import threading
import time
from collections.abc import Callable
from select import select

logger = logging.getLogger(__name__)

try:
    from evdev import InputDevice, ecodes, list_devices
except ImportError:
    InputDevice = None
    ecodes = None
    list_devices = None

_MODIFIER_NAMES = {"ctrl", "ctrl_l", "ctrl_r", "shift", "shift_l", "shift_r",
                   "alt", "alt_l", "alt_r", "alt_gr", "cmd", "cmd_l", "cmd_r",
                   "super", "win"}

_KEY_NAME_TO_CODE = {
    "space": 57,
    "a": 30, "b": 48, "c": 46, "d": 32, "e": 18, "f": 33, "g": 34, "h": 35,
    "i": 23, "j": 36, "k": 37, "l": 38, "m": 50, "n": 49, "o": 24, "p": 25,
    "q": 16, "r": 19, "s": 31, "t": 20, "u": 22, "v": 47, "w": 17, "x": 45,
    "y": 21, "z": 44,
    "0": 11, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10,
    "ctrl": ecodes.KEY_LEFTCTRL if ecodes else 29,
    "ctrl_l": ecodes.KEY_LEFTCTRL if ecodes else 29,
    "ctrl_r": ecodes.KEY_RIGHTCTRL if ecodes else 97,
    "shift": ecodes.KEY_LEFTSHIFT if ecodes else 42,
    "shift_l": ecodes.KEY_LEFTSHIFT if ecodes else 42,
    "shift_r": ecodes.KEY_RIGHTSHIFT if ecodes else 54,
    "alt": ecodes.KEY_LEFTALT if ecodes else 56,
    "alt_l": ecodes.KEY_LEFTALT if ecodes else 56,
    "alt_r": ecodes.KEY_RIGHTALT if ecodes else 100,
    "super": ecodes.KEY_LEFTMETA if ecodes else 125,
    "win": ecodes.KEY_LEFTMETA if ecodes else 125,
}

_CTRL_CODES = {29, 97}
_SHIFT_CODES = {42, 54}
_ALT_CODES = {56, 100}
_SUPER_CODES = {125, 126}


def _resolve_modifier_code(key_name: str) -> int | None:
    return _KEY_NAME_TO_CODE.get(key_name)


class LinuxEvdevHotkeyListener:
    def __init__(self, hotkey: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self.hotkey = hotkey
        self._on_press = on_press
        self._on_release = on_release
        self._all_keys, self._primary_key = self._parse_hotkey(hotkey)
        self._held_codes: set[int] = set()
        self._on_press_triggered = False
        self._trigger_time: float = 0.0
        self._min_hold_ms: float = 200.0
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            from evdev import InputDevice  # noqa: F401
            return True
        except ImportError:
            return False

    def check_permissions(self) -> tuple[bool, str]:
        if not os.path.exists("/dev/input"):
            return False, "/dev/input does not exist on this system"
        blocked = 0
        accessible = 0
        for name in sorted(os.listdir("/dev/input")):
            if not name.startswith("event"):
                continue
            path = f"/dev/input/{name}"
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                os.close(fd)
                accessible += 1
            except PermissionError:
                blocked += 1
            except OSError:
                continue
        if accessible > 0:
            return True, ""
        if blocked > 0:
            return False, (
                "No accessible /dev/input/event* devices. "
                "Try: sudo usermod -a -G input $USER && log out and back in"
            )
        return False, "No input event devices found"

    @staticmethod
    def _parse_hotkey(hotkey: str) -> tuple[set[int], int]:
        parts = hotkey.lower().replace(" ", "").split("+")
        all_codes = set()
        primary_code = None
        for k in parts:
            code = _KEY_NAME_TO_CODE.get(k)
            if code is not None:
                all_codes.add(code)
                if k not in _MODIFIER_NAMES:
                    primary_code = code
        if primary_code is None:
            primary_code = list(all_codes)[-1] if all_codes else 57
        return all_codes, primary_code

    def _find_keyboards(self) -> list[str]:
        if list_devices is None:
            return self._find_keyboards_manual()
        devices = []
        for path in list_devices():
            try:
                caps = InputDevice(path).capabilities(verbose=False)
                if ecodes.EV_KEY in caps:
                    key_codes = caps[ecodes.EV_KEY]
                    if any(code in key_codes for code in self._all_keys):
                        devices.append(path)
            except Exception:
                continue
        return devices if devices else self._find_keyboards_manual()

    def _find_keyboards_manual(self) -> list[str]:
        devices = []
        blocked = 0
        for name in sorted(os.listdir("/dev/input")):
            if not name.startswith("event"):
                continue
            path = f"/dev/input/{name}"
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                os.close(fd)
                devices.append(path)
            except PermissionError:
                blocked += 1
            except OSError:
                continue
        if not devices and blocked > 0:
            logger.debug("Permission denied on %d input device(s)", blocked)
        return devices

    def _handle_event(self, code: int, value: int):
        if code not in self._all_keys:
            return

        if value == 1:
            self._held_codes.add(code)
            if self._all_keys.issubset(self._held_codes) and not self._on_press_triggered:
                self._trigger_time = time.monotonic()
                logger.debug("HOTKEY TRIGGERED via evdev (codes: %s)", self._all_keys)
                self._on_press_triggered = True
                self._on_press()
        elif value == 0:
            self._held_codes.discard(code)
            if self._on_press_triggered and code == self._primary_key:
                elapsed = (time.monotonic() - self._trigger_time) * 1000
                if elapsed < self._min_hold_ms:
                    logger.debug("Primary key release ignored (%.0fms < %.0fms hold gate)", elapsed, self._min_hold_ms)
                    return
                logger.debug("HOTKEY RELEASED via evdev (held %.0fms)", elapsed)
                self._on_press_triggered = False
                self._on_release()

    def _read_loop(self, device_paths: list[str]):
        fds = []
        try:
            for path in device_paths:
                try:
                    fd = os.open(path, os.O_RDONLY)
                    fds.append(fd)
                except PermissionError:
                    logger.debug("No permission for %s", path)
                except OSError:
                    continue
        except Exception:
            return

        if not fds:
            logger.warning("No accessible keyboard devices found")
            return

        logger.debug("Listening on %d evdev device(s)", len(fds))

        EVENT_FORMAT = "llHHi"
        EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

        while self._running.is_set():
            try:
                r, _, _ = select(fds, [], [], 0.5)
            except Exception:
                break
            for fd in r:
                try:
                    data = os.read(fd, EVENT_SIZE * 32)
                except Exception:
                    continue
                for i in range(0, len(data), EVENT_SIZE):
                    chunk = data[i:i + EVENT_SIZE]
                    if len(chunk) < EVENT_SIZE:
                        break
                    _, _, event_type, code, value = struct.unpack(EVENT_FORMAT, chunk)
                    if event_type == 1:
                        self._handle_event(code, value)

        for fd in fds:
            try:
                os.close(fd)
            except Exception:
                pass

    def start(self):
        logger.debug("Starting evdev hotkey listener for '%s'", self.hotkey)
        device_paths = self._find_keyboards()
        if not device_paths:
            logger.warning("No keyboard devices found. Ensure you are in the 'input' group: sudo usermod -a -G input $USER")
            logger.warning("Then log out and back in for the change to take effect.")
        self._running.set()
        self._thread = threading.Thread(target=self._read_loop, args=(device_paths,), daemon=True)
        self._thread.start()

    def stop(self):
        logger.debug("Stopping evdev hotkey listener")
        self._running.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
