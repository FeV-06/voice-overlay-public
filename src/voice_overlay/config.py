from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass, field

from voice_overlay._platform.config import config_dir

logger = logging.getLogger(__name__)


@dataclass
class Config:
    hotkey: str = "ctrl+shift+space"
    model: str = "distil-large-v3"
    language: str = "en"
    overlay_opacity: float = 0.85
    overlay_width: int = 400
    overlay_height: int = 100
    block_size: int = 2048
    word_replacements: dict[str, str] = field(default_factory=dict)
    input_device: str | None = None
    compute_type: str = "int8"
    device: str = "cpu"
    vad_filter: bool = True
    auto_inject: bool = True
    launch_at_login: bool = False
    show_config_window: bool = True

    @classmethod
    def from_file(cls, path: str) -> Config:
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        try:
            with open(config_path) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.warning("Corrupted config.json at %s — falling back to defaults", path)
            return cls()
        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_fields)

    def save(self, path: str) -> None:
        config_path = Path(path)
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
        except PermissionError:
            logger.error("Permission denied writing to %s", path)
            raise

    def to_dict(self) -> dict:
        return {
            "hotkey": self.hotkey,
            "model": self.model,
            "language": self.language,
            "overlay_opacity": self.overlay_opacity,
            "overlay_width": self.overlay_width,
            "overlay_height": self.overlay_height,
            "block_size": self.block_size,
            "word_replacements": self.word_replacements,
            "input_device": self.input_device,
            "compute_type": self.compute_type,
            "device": self.device,
            "vad_filter": self.vad_filter,
            "auto_inject": self.auto_inject,
            "launch_at_login": self.launch_at_login,
            "show_config_window": self.show_config_window,
        }

    @staticmethod
    def config_path() -> Path:
        return config_dir() / "voice-overlay" / "config.json"
