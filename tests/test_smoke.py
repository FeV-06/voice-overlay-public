from __future__ import annotations


def test_all_modules_importable():
    from voice_overlay.config import Config
    from voice_overlay.audio_capture import AudioCapture
    from voice_overlay.transcription import TranscriptionEngine
    from voice_overlay.text_injector import TextInjector
    from voice_overlay.hotkey import EvdevHotkeyListener
    from voice_overlay.gui import ConfigWindow, SystemTray, HotkeyRecorder, ComputeSelector, APP_STYLESHEET
    from voice_overlay._platform.autostart import create_autostart, LinuxAutostart, WindowsAutostart
    assert True


def test_config_roundtrip():
    from voice_overlay.config import Config
    cfg = Config(hotkey="ctrl+alt+x", model="base")
    assert cfg.hotkey == "ctrl+alt+x"
    assert cfg.model == "base"


def test_config_defaults():
    from voice_overlay.config import Config
    cfg = Config()
    assert cfg.model == "distil-large-v3"
    assert cfg.language == "en"
    assert cfg.hotkey == "ctrl+shift+space"


def test_smoke_audio_capture():
    from voice_overlay.audio_capture import AudioCapture, list_input_devices
    cap = AudioCapture()
    assert cap.sample_rate == 16000
    devices = list_input_devices()
    assert isinstance(devices, list)


def test_smoke_lockfile():
    from voice_overlay.lockfile import acquire_lock
    assert callable(acquire_lock)


def test_smoke_autostart():
    from voice_overlay._platform.autostart import create_autostart
    autostart = create_autostart()
    assert callable(autostart.enable)
    assert callable(autostart.disable)
    assert callable(autostart.is_enabled)
