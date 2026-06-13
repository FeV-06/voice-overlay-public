from __future__ import annotations

"""Lockfile backends per platform."""

import sys

if sys.platform == "linux":
    from voice_overlay._platform.lockfile.linux import acquire_lock, is_available, check_permissions  # noqa: F401
elif sys.platform == "win32":
    from voice_overlay._platform.lockfile.windows import acquire_lock, is_available, check_permissions  # noqa: F401

__all__ = ["acquire_lock", "is_available", "check_permissions"]
