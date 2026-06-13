from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from voice_overlay.gui.settings_widgets import _is_valid_key_combo, _normalize_combo
from voice_overlay.gui.config_window import ConfigWindow
from voice_overlay.config import Config


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_config_window_creation(qapp):
    cfg = Config()
    window = ConfigWindow(cfg, tray_available=True)
    assert window.windowTitle() == "VoiceOverlay Configuration"
    assert not window._tray_available is False
    window.close()


def test_config_window_tray_unavailable_shows_quit_button(qapp):
    cfg = Config()
    window = ConfigWindow(cfg, tray_available=False)
    assert window._minimize_button is not None
    assert window._minimize_button.text() == "Hide to Background"
    window.close()


def test_config_window_tray_available_shows_minimize_button(qapp):
    cfg = Config()
    window = ConfigWindow(cfg, tray_available=True)
    window.show()
    assert window._minimize_button.isVisible() is True
    assert window._minimize_button.text() == "Minimize to Tray"
    window.close()


def test_config_window_validate_valid(qapp):
    cfg = Config()
    window = ConfigWindow(cfg)
    assert window._validate() is None
    window.close()


def test_config_window_validate_invalid_model(qapp):
    cfg = Config()
    window = ConfigWindow(cfg)
    window._model_combo.clear()
    window._model_combo.addItem("nonexistent-model")
    error = window._validate()
    assert error is not None
    assert "nonexistent-model" in error
    window.close()


def test_config_window_gather_settings_includes_model_changed(qapp):
    cfg = Config(model="tiny", device="cpu", compute_type="int8")
    window = ConfigWindow(cfg)
    settings = window._gather_settings()
    assert "model_changed" in settings
    assert isinstance(settings["model_changed"], bool)
    assert "device" in settings
    assert "compute_type" in settings
    window.close()


def test_config_window_gather_settings_model_changed_flag(qapp):
    cfg = Config(model="tiny", device="cpu")
    window = ConfigWindow(cfg)
    window._model_combo.setCurrentText("base")
    settings = window._gather_settings()
    assert settings["model_changed"] is True
    window.close()


def test_config_window_saved_signal(qapp):
    cfg = Config()
    window = ConfigWindow(cfg)
    received = []

    def on_saved(settings):
        received.append(settings)

    window.saved.connect(on_saved)
    window._on_save()
    assert len(received) == 1
    assert "hotkey" in received[0]
    assert "model_changed" in received[0]
    window.close()


def test_hotkey_recorder_invalid_modifier_only(qapp):
    from voice_overlay.gui.settings_widgets import HotkeyRecorder

    assert _is_valid_key_combo(["Ctrl", "Shift"]) is False
    assert _is_valid_key_combo(["Ctrl", "Alt"]) is False
    assert _is_valid_key_combo(["Ctrl", "A"]) is True
    assert _is_valid_key_combo(["Ctrl", "Shift", "Space"]) is True
    assert _is_valid_key_combo([]) is False


def test_normalize_combo(qapp):
    result = _normalize_combo(["Ctrl", "Shift", "A"])
    assert "Ctrl" in result
    assert "Shift" in result
    assert "A" in result or "a" in result


def test_compute_selector_filtering_cpu(qapp):
    from voice_overlay.gui.settings_widgets import ComputeSelector

    selector = ComputeSelector()
    selector.set_device("cpu")
    assert selector.device() == "cpu"
    # CPU should only show int8, float32
    types = [selector._compute_combo.itemText(i) for i in range(selector._compute_combo.count())]
    assert "int8" in types
    assert "float32" in types
    assert "float16" not in types


def test_compute_selector_filtering_gpu(qapp):
    from voice_overlay.gui.settings_widgets import ComputeSelector

    selector = ComputeSelector()
    selector.set_device("cuda")
    assert selector.device() == "cuda"
    types = [selector._compute_combo.itemText(i) for i in range(selector._compute_combo.count())]
    assert "float16" in types
    assert "bfloat16" in types


def test_compute_selector_filtering_auto(qapp):
    from voice_overlay.gui.settings_widgets import ComputeSelector

    selector = ComputeSelector()
    selector.set_device("auto")
    assert selector.device() == "auto"
    types = [selector._compute_combo.itemText(i) for i in range(selector._compute_combo.count())]
    assert "int8" in types
    assert "float32" in types
    assert "float16" in types
    assert "bfloat16" in types


def test_gui_does_not_import_engine_modules():
    import voice_overlay.gui
    import inspect

    gui_file = inspect.getfile(voice_overlay.gui)
    with open(gui_file) as f:
        content = f.read()
    assert "transcription" not in content
    assert "text_injector" not in content
    assert "audio_capture" not in content

    import voice_overlay.gui.config_window as cw
    import voice_overlay.gui.settings_widgets as sw
    import voice_overlay.gui.system_tray as st
    import voice_overlay.gui.theme as th

    for mod in [cw, sw, st, th]:
        source = inspect.getsource(mod)
        assert "voice_overlay.transcription" not in source
        assert "voice_overlay.text_injector" not in source


def test_config_window_close_event_tray_available(qapp):
    cfg = Config()
    window = ConfigWindow(cfg, tray_available=True)
    from PySide6.QtGui import QCloseEvent
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() is False
    window.close()


def test_config_window_close_event_tray_unavailable(qapp):
    cfg = Config()
    window = ConfigWindow(cfg, tray_available=False)
    from PySide6.QtGui import QCloseEvent
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() is False
    window.close()


def test_gather_settings_roundtrip(qapp):
    cfg = Config(model="base", device="cpu", compute_type="int8")
    window = ConfigWindow(cfg)
    settings = window._gather_settings()
    assert settings["model"] == "base"
    assert settings["device"] == "cpu" or settings["device"] == "auto"
    assert settings["compute_type"] in ("int8",)
    window.close()
