from __future__ import annotations

import json
import tempfile
from pathlib import Path
from voice_overlay.config import Config


def test_default_values():
    cfg = Config()
    assert cfg.hotkey == "ctrl+shift+space"
    assert cfg.model == "distil-large-v3"
    assert cfg.language == "en"
    assert cfg.overlay_opacity == 0.85
    assert cfg.overlay_width == 400
    assert cfg.overlay_height == 100
    assert cfg.input_device is None
    assert cfg.compute_type == "int8"
    assert cfg.device == "cpu"
    assert cfg.vad_filter is True
    assert cfg.auto_inject is True
    assert cfg.launch_at_login is False
    assert cfg.show_config_window is True


def test_custom_values_overwrite_defaults():
    cfg = Config(hotkey="ctrl+alt+r", model="small")
    assert cfg.hotkey == "ctrl+alt+r"
    assert cfg.model == "small"
    assert cfg.language == "en"


def test_new_fields_custom_values():
    cfg = Config(
        input_device=2,
        compute_type="float16",
        device="cuda",
        vad_filter=False,
        auto_inject=False,
        launch_at_login=True,
        show_config_window=False,
    )
    assert cfg.input_device == 2
    assert cfg.compute_type == "float16"
    assert cfg.device == "cuda"
    assert cfg.vad_filter is False
    assert cfg.auto_inject is False
    assert cfg.launch_at_login is True
    assert cfg.show_config_window is False


def test_to_dict_includes_new_fields():
    cfg = Config()
    d = cfg.to_dict()
    assert "input_device" in d
    assert "compute_type" in d
    assert "device" in d
    assert "vad_filter" in d
    assert "auto_inject" in d
    assert "launch_at_login" in d
    assert "show_config_window" in d
    assert d["input_device"] is None
    assert d["compute_type"] == "int8"


def test_save_and_load_new_fields():
    cfg = Config(compute_type="float16", device="cuda", vad_filter=False)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
    cfg.save(temp_path)
    loaded = Config.from_file(temp_path)
    assert loaded.compute_type == "float16"
    assert loaded.device == "cuda"
    assert loaded.vad_filter is False
    Path(temp_path).unlink()


def test_load_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"hotkey": "ctrl+shift+t", "model": "base"}, f)
        temp_path = f.name
    cfg = Config.from_file(temp_path)
    assert cfg.hotkey == "ctrl+shift+t"
    assert cfg.model == "base"
    Path(temp_path).unlink()


def test_save_to_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
    cfg = Config(hotkey="ctrl+shift+a")
    cfg.save(temp_path)
    with open(temp_path) as f:
        data = json.load(f)
    assert data["hotkey"] == "ctrl+shift+a"
    Path(temp_path).unlink()


def test_default_config_path():
    cfg = Config()
    path = cfg.config_path()
    assert "voice-overlay" in path.parts
    assert path.name == "config.json"


def test_load_missing_file_returns_defaults():
    cfg = Config.from_file("/nonexistent/path/config.json")
    assert cfg.hotkey == "ctrl+shift+space"


def test_backward_compat_old_config_missing_new_fields():
    old_data = {
        "hotkey": "ctrl+shift+x",
        "model": "small",
        "language": "fr",
        "overlay_opacity": 0.5,
        "overlay_width": 300,
        "overlay_height": 200,
        "block_size": 1024,
        "word_replacements": {},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(old_data, f)
        temp_path = f.name
    cfg = Config.from_file(temp_path)
    assert cfg.hotkey == "ctrl+shift+x"
    assert cfg.model == "small"
    assert cfg.language == "fr"
    assert cfg.input_device is None
    assert cfg.compute_type == "int8"
    assert cfg.device == "cpu"
    assert cfg.vad_filter is True
    assert cfg.auto_inject is True
    assert cfg.launch_at_login is False
    assert cfg.show_config_window is True
    Path(temp_path).unlink()


def test_corrupted_json_returns_defaults():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{bad json}}")
        temp_path = f.name
    cfg = Config.from_file(temp_path)
    assert cfg.hotkey == "ctrl+shift+space"
    assert cfg.compute_type == "int8"
    Path(temp_path).unlink()
