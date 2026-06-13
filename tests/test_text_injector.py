from __future__ import annotations

from unittest.mock import patch, MagicMock
from voice_overlay.text_injector import TextInjector


def test_init_detects_wayland():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="wayland"):
        with patch("voice_overlay.text_injector.create_text_injector") as mock_factory:
            mock_factory.return_value = MagicMock()
            injector = TextInjector()
            assert injector.display_server == "wayland"


def test_init_detects_x11():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="x11"):
        with patch("voice_overlay.text_injector.create_text_injector") as mock_factory:
            mock_factory.return_value = MagicMock()
            injector = TextInjector()
            assert injector.display_server == "x11"


def test_inject_types_via_uinput():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="wayland"):
        with patch("voice_overlay.text_injector.create_text_injector") as mock_factory:
            mock_backend = MagicMock()
            mock_backend.type_text.return_value = True
            mock_factory.return_value = mock_backend
            injector = TextInjector()
            ok = injector.inject("hello")
            assert ok is True
            mock_backend.type_text.assert_called_once_with("hello")


def test_inject_falls_back_to_clipboard():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="wayland"):
        with patch("voice_overlay.text_injector.create_text_injector") as mock_factory:
            with patch("voice_overlay.text_injector.TextInjector._copy_to_clipboard") as mock_clip:
                mock_backend = MagicMock()
                mock_backend.type_text.return_value = False
                mock_backend.paste_clipboard.return_value = False
                mock_factory.return_value = mock_backend
                injector = TextInjector()
                ok = injector.inject("fallback text")
                assert ok is False
