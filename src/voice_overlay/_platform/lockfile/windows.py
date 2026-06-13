from __future__ import annotations

import atexit
import logging
import os
import sys
from pathlib import Path

from voice_overlay._platform.config import runtime_dir

logger = logging.getLogger(__name__)

_lock_fd = None


def _cleanup():
    global _lock_fd
    if _lock_fd is not None:
        try:
            os.close(_lock_fd)
        except OSError:
            pass
        _lock_fd = None


atexit.register(_cleanup)


def acquire_lock() -> bool:
    global _lock_fd
    import msvcrt

    lock_dir = runtime_dir() / "voice-overlay"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "instance.lock"

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        _lock_fd = fd
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, str(os.getpid()).encode())
        os.truncate(fd, os.lseek(fd, 0, os.SEEK_CUR))
        logger.info("Acquired instance lock at %s", lock_path)
        return True
    except BlockingIOError:
        print("VoiceOverlay is already running. Only one instance allowed.", file=sys.stderr)
        os.close(fd)
        return False
    except OSError:
        return False


def is_available() -> bool:
    return True


def check_permissions() -> tuple[bool, str]:
    lock_dir = runtime_dir() / "voice-overlay"
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
        test_file = lock_dir / ".perm_test"
        test_file.touch()
        test_file.unlink()
        return True, "Runtime directory is writable"
    except PermissionError:
        return False, f"Permission denied: {lock_dir} is not writable"
    except OSError as e:
        return False, str(e)
