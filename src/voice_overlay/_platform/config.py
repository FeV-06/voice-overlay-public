from __future__ import annotations

import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming")))
    return Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")))


def runtime_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")))
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
