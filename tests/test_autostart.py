from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from voice_overlay._platform.autostart import (
    LinuxAutostart,
    WindowsAutostart,
    FallbackAutostart,
    create_autostart,
)


def test_linux_autostart_enable_disable():
    autostart = LinuxAutostart()
    with tempfile.TemporaryDirectory() as tmp:
        fake_path = Path(tmp) / "voice-overlay.desktop"
        with patch.object(autostart.__class__, "_autostart_path", return_value=fake_path):
            assert autostart.enable() is True
            assert fake_path.exists()
            assert autostart.is_enabled() is True

            assert autostart.disable() is True
            assert not fake_path.exists()
            assert autostart.is_enabled() is False


def test_linux_autostart_is_enabled_returns_false_when_missing():
    autostart = LinuxAutostart()
    with tempfile.TemporaryDirectory() as tmp:
        missing_path = Path(tmp) / "nonexistent.desktop"
        with patch.object(autostart.__class__, "_autostart_path", return_value=missing_path):
            assert autostart.is_enabled() is False


def test_linux_autostart_enable_creates_correct_content():
    autostart = LinuxAutostart()
    with tempfile.TemporaryDirectory() as tmp:
        fake_path = Path(tmp) / "voice-overlay.desktop"
        with patch.object(autostart.__class__, "_autostart_path", return_value=fake_path):
            autostart.enable()
            content = fake_path.read_text()
            assert "VoiceOverlay" in content
            assert "X-GNOME-Autostart-enabled=true" in content


def test_windows_autostart_stub():
    autostart = WindowsAutostart()
    assert autostart.enable() is False
    assert autostart.disable() is False
    assert autostart.is_enabled() is False


def test_fallback_autostart():
    autostart = FallbackAutostart()
    assert autostart.enable() is False
    assert autostart.disable() is False
    assert autostart.is_enabled() is False


def test_create_autostart_linux():
    with patch.object(sys, "platform", "linux"):
        autostart = create_autostart()
        assert isinstance(autostart, LinuxAutostart)


def test_create_autostart_windows():
    with patch.object(sys, "platform", "win32"):
        autostart = create_autostart()
        assert isinstance(autostart, WindowsAutostart)


def test_create_autostart_unsupported():
    with patch.object(sys, "platform", "darwin"):
        autostart = create_autostart()
        assert isinstance(autostart, FallbackAutostart)


def test_windows_autostart_command_uses_shutil_which_path():
    autostart = WindowsAutostart()
    with patch("voice_overlay._platform.autostart.shutil.which", return_value="C:\\Users\\test\\AppData\\Local\\uv\\tools\\voice-overlay\\voice-overlay.exe"):
        cmd = autostart._command()
        assert cmd == '"C:\\Users\\test\\AppData\\Local\\uv\\tools\\voice-overlay\\voice-overlay.exe"'


def test_windows_autostart_command_fallback_when_not_found():
    autostart = WindowsAutostart()
    with patch("voice_overlay._platform.autostart.shutil.which", return_value=None):
        cmd = autostart._command()
        assert cmd.startswith('"')
        assert cmd.endswith(' -m voice_overlay')


def test_windows_autostart_command_fallback_on_oserror():
    autostart = WindowsAutostart()
    with patch("voice_overlay._platform.autostart.shutil.which", side_effect=OSError("permission denied")):
        cmd = autostart._command()
        assert cmd.endswith(' -m voice_overlay')


def test_windows_autostart_command_quotes_spaces():
    autostart = WindowsAutostart()
    with patch("voice_overlay._platform.autostart.shutil.which", return_value="C:\\Program Files\\voice-overlay\\voice-overlay.exe"):
        cmd = autostart._command()
        assert cmd == '"C:\\Program Files\\voice-overlay\\voice-overlay.exe"'


def test_linux_desktop_file_content():
    autostart = LinuxAutostart()
    content = autostart.DESKTOP_FILE_CONTENT
    assert "[Desktop Entry]" in content
    assert "Name=VoiceOverlay" in content
    assert "Exec=voice-overlay" in content
