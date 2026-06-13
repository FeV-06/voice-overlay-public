from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import fcntl

from voice_overlay._platform.config import runtime_dir

logger = logging.getLogger(__name__)

_lock_fd = None


def acquire_lock() -> bool:
    global _lock_fd
    lock_dir = runtime_dir() / "voice-overlay"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "instance.lock"

    try:
        _lock_fd = open(lock_path, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
        logger.info("Acquired instance lock at %s", lock_path)
        return True
    except (IOError, OSError):
        print("VoiceOverlay is already running. Only one instance allowed.", file=sys.stderr)
        return False


def is_available() -> bool:
    try:
        import fcntl  # noqa: F401
        return True
    except ImportError:
        return False


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
