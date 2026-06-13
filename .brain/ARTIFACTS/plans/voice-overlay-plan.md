# VoiceOverlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time voice transcription overlay for Linux that captures mic audio, transcribes via faster-whisper, and injects text at cursor on push-to-talk hotkey release.

**Architecture:** Monolithic Python app. pynput thread listens for push-to-talk hotkey. On press: GTK overlay appears, audio capture begins. Audio chunks streamed to faster-whisper for incremental transcription, updating the overlay in near-real-time. On release: final transcription runs, text injected at cursor via ydotool/wtype/xdotool, overlay hides.

**Tech Stack:** Python 3.10+, faster-whisper, PyGObject (GTK3), pynput, sounddevice, numpy, ydotool/xdotool

---

## File Structure

```
VoiceOverlay/
├── pyproject.toml
├── requirements.txt
├── src/
│   └── voice_overlay/
│       ├── __init__.py
│       ├── main.py              # Entry point, wires everything
│       ├── config.py            # Config file handling
│       ├── audio_capture.py     # Microphone streaming
│       ├── transcription.py     # faster-whisper wrapper
│       ├── overlay_ui.py        # GTK3 floating window
│       ├── hotkey.py            # Global hotkey listener
│       └── text_injector.py     # Text injection at cursor
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_audio_capture.py
    ├── test_transcription.py
    ├── test_hotkey.py
    └── test_text_injector.py
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `src/voice_overlay/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Initialize git repo** (done)
- [ ] **Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "voice-overlay"
version = "0.1.0"
description = "Real-time voice transcription overlay for Linux"
requires-python = ">=3.10"
dependencies = [
    "faster-whisper>=1.0.0",
    "pynput>=1.7.0",
    "sounddevice>=0.4.6",
    "numpy>=1.24.0",
    "PyGObject>=3.44.0",
]

[project.scripts]
voice-overlay = "voice_overlay.main:main"
```

- [ ] **Step 3: Create requirements.txt**

```
faster-whisper>=1.0.0
pynput>=1.7.0
sounddevice>=0.4.6
numpy>=1.24.0
PyGObject>=3.44.0
```

- [ ] **Step 4: Create empty __init__.py files**
- [ ] **Step 5: Create directory structure and commit**

---

### Task 2: Config module

**Files:**
- Create: `src/voice_overlay/config.py`, `tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
import json
import tempfile
from pathlib import Path
from voice_overlay.config import Config

def test_default_values():
    cfg = Config()
    assert cfg.hotkey == "ctrl+shift+v"
    assert cfg.model == "tiny"
    assert cfg.language == "en"
    assert cfg.overlay_opacity == 0.85
    assert cfg.overlay_width == 400
    assert cfg.overlay_height == 100

def test_custom_values_overwrite_defaults():
    cfg = Config(hotkey="ctrl+alt+r", model="small")
    assert cfg.hotkey == "ctrl+alt+r"
    assert cfg.model == "small"
    assert cfg.language == "en"

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
    assert str(cfg.config_path()).endswith(".config/voice-overlay/config.json")

def test_load_missing_file_returns_defaults():
    cfg = Config.from_file("/nonexistent/path/config.json")
    assert cfg.hotkey == "ctrl+shift+v"
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'voice_overlay.config'`

- [ ] **Step 3: Implement Config class**

```python
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass
class Config:
    hotkey: str = "ctrl+shift+v"
    model: str = "tiny"
    language: str = "en"
    overlay_opacity: float = 0.85
    overlay_width: int = 400
    overlay_height: int = 100

    @classmethod
    def from_file(cls, path: str) -> "Config":
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with open(config_path) as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: str) -> None:
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def config_path() -> Path:
        xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return Path(xdg_config) / "voice-overlay" / "config.json"
```

- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 3: Audio capture module

**Files:**
- Create: `src/voice_overlay/audio_capture.py`, `tests/test_audio_capture.py`

- [ ] **Step 1: Write tests**

```python
import time
import numpy as np
from voice_overlay.audio_capture import AudioCapture

def test_audio_capture_default_parameters():
    cap = AudioCapture()
    assert cap.sample_rate == 16000
    assert cap.channels == 1
    assert cap.block_size == 16000

def test_audio_capture_custom_parameters():
    cap = AudioCapture(sample_rate=8000, block_size=8000)
    assert cap.sample_rate == 8000
    assert cap.block_size == 8000

def test_start_stop_cycles():
    cap = AudioCapture(block_size=4000)
    cap.start()
    assert cap.is_recording()
    cap.stop()
    assert not cap.is_recording()
    cap.start()
    assert cap.is_recording()
    cap.stop()

def test_recording_produces_audio():
    cap = AudioCapture(block_size=4000)
    cap.start()
    time.sleep(0.5)
    cap.stop()
    audio = cap.get_audio()
    assert isinstance(audio, np.ndarray)
    assert audio.dtype == np.float32
    assert len(audio) > 0
    assert audio.ndim == 1

def test_clear_resets_buffer():
    cap = AudioCapture(block_size=4000)
    cap.start()
    time.sleep(0.2)
    cap.stop()
    cap.clear()
    audio = cap.get_audio()
    assert len(audio) == 0

def test_multiple_recordings_accumulate():
    cap = AudioCapture(block_size=4000)
    cap.start()
    time.sleep(0.2)
    cap.stop()
    first_len = len(cap.get_audio())
    cap.start()
    time.sleep(0.2)
    cap.stop()
    second_len = len(cap.get_audio())
    assert second_len > first_len
```

- [ ] **Step 2: Run tests to see them fail**
- [ ] **Step 3: Implement AudioCapture**

```python
import queue
import numpy as np

try:
    import sounddevice as _sd
except ImportError:
    _sd = None

class AudioCapture:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, block_size: int = 16000):
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self._audio_queue: queue.Queue = queue.Queue()
        self._stream = None
        self._recording = False
        self._buffer: list[np.ndarray] = []

    def _audio_callback(self, indata, frames, time_info, status):
        if self._recording:
            chunk = indata[:, 0].copy().astype(np.float32)
            self._buffer.append(chunk)

    def start(self) -> None:
        if _sd is None:
            raise RuntimeError("sounddevice not installed")
        self._buffer.clear()
        self._recording = True
        self._stream = _sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.float32,
            blocksize=self.block_size,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def is_recording(self) -> bool:
        return self._recording

    def get_audio(self) -> np.ndarray:
        if not self._buffer:
            return np.array([], dtype=np.float32)
        return np.concatenate(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()
```

- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

### Task 4: Transcription engine

**Files:**
- Create: `src/voice_overlay/transcription.py`, `tests/test_transcription.py`

- [ ] **Step 1: Write tests**

```python
import numpy as np
from voice_overlay.transcription import TranscriptionEngine

def test_engine_init_defaults():
    engine = TranscriptionEngine()
    assert engine.model_size == "tiny"
    assert engine.language == "en"
    assert engine.compute_type == "int8"

def test_transcribe_empty_audio_returns_empty():
    engine = TranscriptionEngine(model_size="tiny")
    audio = np.array([], dtype=np.float32)
    text = engine.transcribe(audio)
    assert text.strip() == ""

def test_transcribe_silence():
    engine = TranscriptionEngine(model_size="tiny")
    audio = np.zeros(16000, dtype=np.float32)
    text = engine.transcribe(audio)
    assert isinstance(text, str)
    assert text.strip() == ""

def test_transcribe_returns_segments():
    engine = TranscriptionEngine(model_size="tiny")
    audio = np.zeros(16000 * 3, dtype=np.float32)
    segments = engine.transcribe_with_segments(audio)
    assert isinstance(segments, list)

def test_vad_filter_enabled_by_default():
    engine = TranscriptionEngine()
    assert engine.vad_filter is True
```

- [ ] **Step 2: Run tests to see them fail**
- [ ] **Step 3: Implement TranscriptionEngine**

```python
import numpy as np
from faster_whisper import WhisperModel

class TranscriptionEngine:
    def __init__(
        self,
        model_size: str = "tiny",
        language: str = "en",
        compute_type: str = "int8",
        device: str = "cpu",
        vad_filter: bool = True,
    ):
        self.model_size = model_size
        self.language = language
        self.compute_type = compute_type
        self.vad_filter = vad_filter
        self.device = device
        self._model = None

    def _load_model(self):
        if self._model is None:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) == 0:
            return ""
        self._load_model()
        segments, _ = self._model.transcribe(
            audio,
            language=self.language,
            vad_filter=self.vad_filter,
            beam_size=1,
            best_of=1,
        )
        return " ".join(segment.text.strip() for segment in segments)

    def transcribe_with_segments(self, audio: np.ndarray) -> list[dict]:
        if len(audio) == 0:
            return []
        self._load_model()
        segments, _ = self._model.transcribe(
            audio,
            language=self.language,
            vad_filter=self.vad_filter,
            beam_size=1,
            best_of=1,
        )
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
            for seg in segments
        ]
```

- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

---

### Task 5: Text injector module

**Files:**
- Create: `src/voice_overlay/text_injector.py`, `tests/test_text_injector.py`

- [ ] **Step 1: Write tests**

```python
from unittest.mock import patch
from voice_overlay.text_injector import TextInjector

def test_init_detects_wayland():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="wayland"):
        injector = TextInjector()
        assert injector.display_server == "wayland"

def test_init_detects_x11():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="x11"):
        injector = TextInjector()
        assert injector.display_server == "x11"

def test_inject_wayland_calls_ydotool():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="wayland"):
        injector = TextInjector()
    with patch("subprocess.run") as mock_run:
        with patch("shutil.which", return_value="/usr/bin/ydotool"):
            injector.inject("hello world")
            mock_run.assert_called_once()

def test_inject_x11_calls_xdotool():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="x11"):
        injector = TextInjector()
    with patch("subprocess.run") as mock_run:
        with patch("shutil.which", return_value="/usr/bin/xdotool"):
            injector.inject("hello world")
            mock_run.assert_called_once()

def test_inject_fallback_to_clipboard():
    with patch("voice_overlay.text_injector.TextInjector._detect_display_server", return_value="unsupported"):
        injector = TextInjector()
    with patch("subprocess.run") as mock_run:
        injector.inject("fallback text")
        mock_run.assert_called()
```

- [ ] **Step 2: Run tests to see them fail**
- [ ] **Step 3: Implement TextInjector**

```python
import os
import subprocess
import shutil

class TextInjector:
    def __init__(self):
        self.display_server = self._detect_display_server()

    @staticmethod
    def _detect_display_server() -> str:
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session_type == "wayland":
            return "wayland"
        elif session_type == "x11":
            return "x11"
        elif "WAYLAND_DISPLAY" in os.environ:
            return "wayland"
        elif "DISPLAY" in os.environ:
            return "x11"
        return "unknown"

    def inject(self, text: str) -> bool:
        if not text:
            return True
        if self.display_server == "wayland":
            return self._inject_wayland(text)
        elif self.display_server == "x11":
            return self._inject_x11(text)
        else:
            return self._inject_clipboard_fallback(text)

    def _inject_wayland(self, text: str) -> bool:
        tool = shutil.which("ydotool") or shutil.which("wtype")
        if tool is None:
            return self._inject_clipboard_fallback(text)
        if "ydotool" in tool:
            result = subprocess.run(
                ["ydotool", "type", "--file", "-"],
                input=text, capture_output=True, text=True,
            )
        else:
            result = subprocess.run(["wtype", text], capture_output=True)
        return result.returncode == 0

    def _inject_x11(self, text: str) -> bool:
        if shutil.which("xdotool") is None:
            return self._inject_clipboard_fallback(text)
        result = subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "1", text],
            capture_output=True,
        )
        return result.returncode == 0

    def _inject_clipboard_fallback(self, text: str) -> bool:
        if self.display_server == "wayland":
            clip_tool = shutil.which("wl-copy")
            if clip_tool:
                subprocess.run(["wl-copy", text])
        elif self.display_server == "x11":
            clip_tool = shutil.which("xclip")
            if clip_tool:
                subprocess.run(["xclip", "-selection", "c"], input=text, text=True)
        return False
```

- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

---

### Task 6: Hotkey listener module

**Files:**
- Create: `src/voice_overlay/hotkey.py`, `tests/test_hotkey.py`

- [ ] **Step 1: Write tests**

```python
from unittest.mock import MagicMock
from voice_overlay.hotkey import HotkeyListener

def test_parse_hotkey_modifiers():
    result = HotkeyListener._parse_hotkey("ctrl+shift+v")
    assert result == {"ctrl", "shift", "v"}

def test_parse_single_modifier():
    result = HotkeyListener._parse_hotkey("ctrl+r")
    assert result == {"ctrl", "r"}

def test_listener_init():
    on_press = MagicMock()
    on_release = MagicMock()
    listener = HotkeyListener(hotkey="ctrl+shift+v", on_press=on_press, on_release=on_release)
    assert listener.hotkey == "ctrl+shift+v"
    assert not listener.is_pressed()

def test_start_stop_cycle():
    on_press = MagicMock()
    on_release = MagicMock()
    listener = HotkeyListener(hotkey="ctrl+shift+v", on_press=on_press, on_release=on_release)
    listener.start()
    assert listener._running.is_set()
    listener.stop()
    assert not listener._running.is_set()
```

- [ ] **Step 2: Run tests to see them fail**
- [ ] **Step 3: Implement HotkeyListener**

```python
import threading
from collections.abc import Callable

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

class HotkeyListener:
    def __init__(self, hotkey: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self.hotkey = hotkey
        self._on_press = on_press
        self._on_release = on_release
        self._modifiers = self._parse_hotkey(hotkey)
        self._pressed_keys: set[str] = set()
        self._on_press_triggered = False
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._listener = None

    @staticmethod
    def _parse_hotkey(hotkey: str) -> set[str]:
        return set(hotkey.lower().replace(" ", "").split("+"))

    def is_pressed(self) -> bool:
        return self._on_press_triggered

    def _on_key_press(self, key):
        try:
            key_name = key.char
        except AttributeError:
            key_name = str(key).replace("Key.", "")
        self._pressed_keys.add(key_name)
        if self._modifiers.issubset(self._pressed_keys) and not self._on_press_triggered:
            self._on_press_triggered = True
            self._on_press()

    def _on_key_release(self, key):
        try:
            key_name = key.char
        except AttributeError:
            key_name = str(key).replace("Key.", "")
        self._pressed_keys.discard(key_name)
        if self._on_press_triggered and not self._modifiers.issubset(self._pressed_keys):
            self._on_press_triggered = False
            self._on_release()

    def start(self):
        if keyboard is None:
            raise RuntimeError("pynput not installed")
        self._running.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._listener.start()
        while self._running.is_set():
            self._running.wait(0.5)
        self._listener.stop()

    def stop(self):
        self._running.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
```

- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

---

### Task 7: GTK Overlay UI

**Files:**
- Create: `src/voice_overlay/overlay_ui.py`

- [ ] **Step 1: Implement OverlayWindow**

```python
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

class OverlayWindow(Gtk.Window):
    def __init__(self, config):
        super().__init__(title="VoiceOverlay")
        self.config = config
        self._setup_window()
        self._build_ui()
        self.connect("destroy", Gtk.main_quit)

    def _setup_window(self):
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_default_size(self.config.overlay_width, self.config.overlay_height)

        screen = self.get_screen()
        if screen:
            monitor = screen.get_monitor_geometry(0)
            x = monitor.width - self.config.overlay_width - 20
            y = 20
            self.move(x, y)

        self.set_opacity(self.config.overlay_opacity)

        css = b"""
        .overlay-frame {
            background-color: rgba(0, 0, 0, 0.85);
            border-radius: 12px;
            padding: 12px;
        }
        .status-label {
            color: #00ff88;
            font-size: 12px;
            font-weight: bold;
        }
        .status-label.recording {
            color: #ff4444;
        }
        .transcription-label {
            color: #ffffff;
            font-size: 16px;
            font-weight: normal;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self):
        frame = Gtk.Frame()
        frame.get_style_context().add_class("overlay-frame")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        self.status_label = Gtk.Label(label="VoiceOverlay")
        self.status_label.get_style_context().add_class("status-label")
        self.status_label.set_halign(Gtk.Align.START)

        self.text_label = Gtk.Label(label="")
        self.text_label.get_style_context().add_class("transcription-label")
        self.text_label.set_halign(Gtk.Align.START)
        self.text_label.set_line_wrap(True)
        self.text_label.set_max_width_chars(40)

        vbox.pack_start(self.status_label, False, False, 0)
        vbox.pack_start(self.text_label, True, True, 0)
        frame.add(vbox)
        self.add(frame)

    def show_overlay(self):
        self.show_all()
        self.text_label.set_text("")

    def hide_overlay(self):
        self.hide()

    def update_status(self, recording: bool):
        ctx = self.status_label.get_style_context()
        if recording:
            ctx.add_class("recording")
            self.status_label.set_text("RECORDING")
        else:
            ctx.remove_class("recording")
            self.status_label.set_text("VoiceOverlay")

    def update_text(self, text: str):
        GLib.idle_add(self.text_label.set_text, text)
```

- [ ] **Step 2: Commit**

---

### Task 8: Main entry point — wire everything

**Files:**
- Create: `src/voice_overlay/main.py`

- [ ] **Step 1: Implement main.py**

```python
import sys
import signal
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from voice_overlay.config import Config
from voice_overlay.audio_capture import AudioCapture
from voice_overlay.transcription import TranscriptionEngine
from voice_overlay.hotkey import HotkeyListener
from voice_overlay.text_injector import TextInjector
from voice_overlay.overlay_ui import OverlayWindow


class VoiceOverlayApp:
    def __init__(self):
        self.config = Config.from_file(str(Config.config_path()))
        self.audio = AudioCapture()
        self.transcriber = TranscriptionEngine(
            model_size=self.config.model,
            language=self.config.language,
        )
        self.injector = TextInjector()
        self.overlay = OverlayWindow(self.config)

        self.hotkey = HotkeyListener(
            hotkey=self.config.hotkey,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )

    def _on_hotkey_press(self):
        self.audio.start()
        GLib.idle_add(self.overlay.show_overlay)
        GLib.idle_add(self.overlay.update_status, True)

    def _on_hotkey_release(self):
        self.audio.stop()
        audio_data = self.audio.get_audio()
        text = self.transcriber.transcribe(audio_data)
        if text.strip():
            self.injector.inject(text.strip())
        GLib.idle_add(self.overlay.update_status, False)
        GLib.idle_add(self.overlay.hide_overlay)
        self.audio.clear()

    def run(self):
        self.hotkey.start()
        self.overlay.show_all()
        self.overlay.hide()
        Gtk.main()


def main():
    app = VoiceOverlayApp()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make package installable**

```
pip install -e .
```

- [ ] **Step 3: Commit all remaining files**

```
git add -A && git commit -m "feat: main entry point, wire all components"
```

---

### Task 9: Integration test & smoke test

- [ ] **Step 1: Write smoke test**

Create `tests/test_smoke.py`:

```python
def test_imports():
    from voice_overlay.config import Config
    from voice_overlay.audio_capture import AudioCapture
    from voice_overlay.transcription import TranscriptionEngine
    from voice_overlay.text_injector import TextInjector
    from voice_overlay.hotkey import HotkeyListener

def test_config_defaults():
    from voice_overlay.config import Config
    cfg = Config()
    assert cfg.model == "tiny"
    assert cfg.language == "en"

def test_app_creation():
    from voice_overlay.main import VoiceOverlayApp
    app = VoiceOverlayApp()
    assert app.config is not None
    assert app.audio is not None
    assert app.injector is not None
```

- [ ] **Step 2: Run full test suite**

```
python -m pytest tests/ -v
```

- [ ] **Step 3: Commit final changes**

---

## Plan Refinement (2026-06-09)

> Applied by: plan-refiner agent. Original content preserved above. This section augments the plan with structural fixes, gap resolution, and risk mitigations.

---

### Structural Improvements

#### S1 — Prerequisites task (insert before Task 1)

The plan assumes Python packages are installable but ignores system-level dependencies. Add a **Task 0: System dependencies** to validate the host:

```
Fedora:
  sudo dnf install python3-devel gcc gtk3-devel gobject-introspection-devel \
    cairo-gobject-devel portaudio-devel

Ubuntu/Debian:
  sudo apt install python3-dev gcc libgtk-3-dev libgirepository1.0-dev \
    libcairo2-dev portaudio19-dev

Verify:
  python3 -c "import gi; gi.require_version('Gtk','3.0')"
  python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

Also verify text-injection tools are available:
```
  ydotool (Wayland, needs ydotoold daemon)  OR  wtype
  xdotool (X11)
  wl-copy / xclip (clipboard fallback)
```

- [ ] Step 1: Document required system packages in a SYSTEM_DEPENDENCIES.md reference
- [ ] Step 2: Add startup validation in main.py that checks each Python import + tool availability before launching GTK

#### S2 — Fix incremental transcription (affects Tasks 3, 4, 7, 8)

The plan header describes incremental ("near-real-time") transcription but the implementation only does batch-on-release. This is the single largest gap.

**Solution**: AudioCapture adds a generator method for streaming chunks; TranscriptionEngine adds an iterative transcribe method; main.py wires the two.

Changes to **Task 3 (AudioCapture)** — add to `audio_capture.py`:

```python
def iter_chunks(self) -> Generator[np.ndarray, None, None]:
    """Yield recorded chunks as they arrive (for live transcription)."""
    # Use a threading.Condition to block until new chunks arrive
    while self._recording or self._buffer:
        if not self._buffer:
            with self._condition:
                self._condition.wait(timeout=0.1)
            continue
        yield self._buffer[-1]  # latest chunk
```

Changes to **Task 4 (TranscriptionEngine)** — add speculative decoding fallback:

The `_on_hotkey_release` in main.py must become **two-phase**:
1. **While recording**: a background thread consumes `audio.iter_chunks()`, transcribes the latest chunk with a very short context window, and pushes interim text to the overlay via `GLib.idle_add`.
2. **On release**: stop recording, run a final full-audio transcription for accuracy, inject, hide overlay.

- [ ] Step: Expand TranscriptionEngine with `transcribe_streaming(audio_chunk, previous_context)` that uses `initial_prompt` from prior text
- [ ] Step: Update main.py with a transcription thread that runs during recording
- [ ] Step: Add `update_interim_text()` to OverlayUindow distinct from final `update_text()`

#### S3 — App state machine (affects Task 8)

Scattered boolean flags (`is_recording`, `_on_press_triggered`) risk re-entrance bugs. Add an explicit `AppState` enum.

```python
from enum import Enum, auto

class AppState(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    INJECTING = auto()
```

Guard every hotkey callback with a state check to prevent rapid-fire corruption.

- [ ] Step: Add `AppState` to main.py
- [ ] Step: In `_on_hotkey_press`, only proceed if state == IDLE
- [ ] Step: In `_on_hotkey_release`, only proceed if state == RECORDING
- [ ] Step: Transition state through each phase

#### S4 — Fix OverlayUI thread safety (Task 7)

`OverlayWindow.update_text()` wraps `GLib.idle_add` internally, but callers in main.py also wrap it in `GLib.idle_add`. Remove the inner wrapping — let callers decide. Keep only GTK operations thread-safe by convention: _callers_ use `GLib.idle_add`.

- [ ] Step: Remove `GLib.idle_add` from `update_text()` and `update_status()`
- [ ] Step: Ensure all callers in main.py wrap with `GLib.idle_add`

#### S5 — Add cleanup/shutdown (Task 8)

`SignalHandler(signal.SIGINT, signal.SIG_DFL)` kills GTK uncleanly. Replace with a proper shutdown routine:

```python
def _shutdown(self):
    self.hotkey.stop()
    self.audio.stop()
    Gtk.main_quit()

signal.signal(signal.SIGINT, lambda *a: GLib.idle_add(self._shutdown))
```

- [ ] Step: Implement `_shutdown()` in VoiceOverlayApp
- [ ] Step: Wire SIGINT + SIGTERM to it via `GLib.idle_add`

---

### Execution Gaps Resolved

#### G1 — Config bootstrap (Task 2)

`Config.from_file()` returns defaults when file missing but never persists them. On first run, the user gets no config file. Fix: `VoiceOverlayApp.__init__` should call `config.save(str(Config.config_path()))` if the file doesn't exist.

- [ ] Step: In main.py, after loading config, save defaults if path doesn't exist

#### G2 — Error visibility in overlay (Tasks 7, 8)

If mic is unavailable or whisper model fails to download, the app silently fails. Add an error display to the overlay:

```python
def show_error(self, message: str):
    """Show error in overlay with red styling for 3 seconds."""
    self.text_label.set_text(f"ERROR: {message}")
    self.text_label.get_style_context().add_class("error")
    GLib.timeout_add(3000, self._clear_error)
```

- [ ] Step: Add `.error` CSS class (red text) to the CSS provider
- [ ] Step: Add `show_error()` to OverlayWindow
- [ ] Step: Wrap AudioCapture.start() and TranscriptionEngine._load_model() in try/except in main.py, routing errors to overlay

#### G3 — Logging (all modules)

Zero logging in a multi-threaded app. Add structured logging:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)
```

- [ ] Step: Add logging to every module (config, audio, transcription, hotkey, injector, overlay, main)
- [ ] Step: Log state transitions, errors, transcription timing

#### G4 — Missing tests for OverlayWindow (Task 7)

Task 7 has no `tests/test_overlay_ui.py`. Add lightweight tests for the CSS parsing, label management, and GTK mock interactions.

- [ ] Step: Create `tests/test_overlay_ui.py`
- [ ] Step: Test `_parse_hotkey` edge cases (empty string, extra spaces, uppercase)
- [ ] Step: Mock GTK to test label text updates, CSS class toggling

#### G5 — Fix smoke test (Task 9)

`test_app_creation()` instantiates `VoiceOverlayApp` which loads GTK, opens audio devices, and downloads a whisper model. This is a full integration test, not a smoke test. Make it a true smoke test:

```python
def test_all_modules_importable():
    from voice_overlay.config import Config
    from voice_overlay.audio_capture import AudioCapture
    from voice_overlay.transcription import TranscriptionEngine
    from voice_overlay.text_injector import TextInjector
    from voice_overlay.hotkey import HotkeyListener
    # Do NOT instantiate VoiceOverlayApp (requires GTK main loop)

def test_config_roundtrip():
    cfg = Config(hotkey="ctrl+alt+x", model="base")
    assert cfg.hotkey == "ctrl+alt+x"
```

- [ ] Step: Rewrite `test_app_creation` to only test imports + config
- [ ] Step: Add a separate integration test (manual-only) to the README

#### G6 — TranscriptionEngine tests trigger model download (Task 4)

`test_transcribe_silence()` and `test_transcribe_returns_segments()` call `engine.transcribe()` which calls `_load_model()` which downloads the whisper model. Tests should mock `WhisperModel` to avoid network dependency.

- [ ] Step: Add `from unittest.mock import patch` to test_transcription.py
- [ ] Step: Patch `WhisperModel` in any test that calls `transcribe()`
- [ ] Step: Keep `test_transcribe_empty_audio_returns_empty()` as is (early return before model load)

---

### Dependency & Execution Order Fixes

The original task order (Config → Audio → Transcription → Injector → Hotkey → Overlay → Main → Smoke) is mostly sound but has two issues:

1. **Overlay (Task 7) should come before Main (Task 8)** — already correct, no change needed.
2. **Hotkey (Task 6) and Overlay (Task 7) have no mutual dependency** — they can be implemented in parallel.
3. **New Task 0 (System Deps) must come first** — inserted above.
4. **New Task 10 (Incremental Transcription Wiring)** — the streaming pipeline requires all modules, so add after Task 8:

- [ ] **Task 10: Incremental transcription wiring**
  - Files: update `audio_capture.py`, `transcription.py`, `overlay_ui.py`, `main.py`
  - Step 1: Add `iter_chunks()` generator to AudioCapture
  - Step 2: Add `transcribe_streaming()` to TranscriptionEngine
  - Step 3: Add `update_interim_text()` to OverlayWindow
  - Step 4: Add transcription thread to main.py
  - Step 5: Add AppState state machine
  - Step 6: Run full test suite
  - Step 7: Commit

---

### Risk Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| pynput keyboard listener fails on Wayland without root | High | Document that Wayland users must run `sudo` or switch to X11. Add detection + warning in startup. |
| ydotool requires `ydotoold` daemon running | Medium | Check for daemon in startup validation; fallback to wtype/clipboard with warning |
| Whisper model download blocks first launch (150MB tiny model) | Medium | Show overlay status "Loading model..." during first download; cache in `~/.cache/voice-overlay/` |
| GTK3 is not thread-safe — all UI calls must use `GLib.idle_add` | Medium | Audit every GTK call from non-main threads; enforce in code review |
| Rapid hotkey spamming corrupts audio buffer | Medium | AppState enum prevents re-entrance; audio.clear() before new recording |
| sounddevice portaudio buffer overflow on slow CPU | Low | Use block_size=4000 (smaller chunks); drop chunks if queue backs up |

---

### Skill Injections

The following skills apply to improve implementation quality:

1. **clean-code** — Enforce no unnecessary comments, pragmatic structure across all modules
2. **systematic-debugging** — Add structured logging at every error boundary and state transition
3. **testing-patterns** — Mock external dependencies (WhisperModel, sounddevice, pynput) in unit tests; keep hardware tests manual

---

### Planner Feedback

- **Major Weakness Fixed**: Incremental (live) transcription — the plan description required it but the implementation omitted it entirely. Now resolved with streaming architecture.
- **Remaining Risks**: Wayland pynput limitation cannot be fixed in code (requires system-level permissions); ydotool daemon dependency is a user-env concern.
- **Suggested Focus for Next Iteration**: After M1 prototype ships, evaluate offline VAD for better chunk boundary detection; consider hotkey remapping via config UI.

---

## Pass 2 Additions: Diversity Enhancement

### T11: Error boundary architecture

**Files:**
- Create: `src/voice_overlay/errors.py`, `src/voice_overlay/resilience.py`

```python
# errors.py
class VoiceOverlayError(Exception): ...
class AudioDeviceError(VoiceOverlayError): ...
class TranscriptionError(VoiceOverlayError): ...
class InjectionError(VoiceOverlayError): ...
class HotkeyCaptureError(VoiceOverlayError): ...
```

```python
# resilience.py
import time
import logging
from voice_overlay.errors import AudioDeviceError, TranscriptionError, InjectionError

logger = logging.getLogger(__name__)

class Resilience:
    @staticmethod
    def retry_inject(injector, text: str, max_attempts=3, base_delay=0.5):
        for attempt in range(max_attempts):
            try:
                if injector.inject(text):
                    return True
                raise InjectionError(f"Injection attempt {attempt+1} failed")
            except InjectionError:
                if attempt == max_attempts - 1:
                    return injector._inject_clipboard_fallback(text)
                time.sleep(base_delay * (2 ** attempt))
        return False

    @staticmethod
    def safe_transcribe(engine, audio, timeout=20.0):
        try:
            return engine.transcribe(audio)
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise TranscriptionError(str(e)) from e
```

### T12: Audio buffer improvements (ring buffer, dropped-chunk tracking)

**Files:**
- Modify: `src/voice_overlay/audio_capture.py`

Changes:
- Replace `self._buffer: list` with `collections.deque(maxlen=120)` for bounded ring buffer
- Add `dropped_chunks` counter
- Reduce default `block_size` to 4000 (250ms for live feedback)
- Add `chunks_dropped` property exposed to main.py for overlay warning

### T13: Dependency injection & contract tests

**Files:**
- Create: `tests/test_contracts.py`
- Modify: `src/voice_overlay/transcription.py`, `src/voice_overlay/main.py`

Changes:
- TranscriptionEngine accepts optional `WhisperModel` injection
- VoiceOverlayApp accepts all components as optional constructor args
- Contract tests verify public method signatures match expected interfaces

### T14: Push-to-talk edge case hardening

**Files:**
- Modify: `src/voice_overlay/hotkey.py`, `src/voice_overlay/main.py`

Changes:
- Add 200ms debounce: ignore releases under `min_recording_ms=200`
- Add `max_recording_seconds=30` auto-stop with overlay countdown
- Add stuck-modifier recovery: if no key events for 2s while `_on_press_triggered`, force-reset
- Add hotkey clash detection log (known conflicts: ctrl+shift+v = terminal paste-without-formatting)

### T15: Config hot-reloading

**Files:**
- Create: `src/voice_overlay/config_watcher.py`

```python
import threading
from pathlib import Path
from collections.abc import Callable
from voice_overlay.config import Config

class ConfigWatcher:
    HOT_RELOADABLE = {"overlay_opacity", "overlay_width", "overlay_height", "max_recording_seconds"}
    REQUIRES_RESTART = {"hotkey", "model", "language"}

    def __init__(self, path: Path, on_change: Callable[[Config, set[str]], None]):
        self.path = path
        self._on_change = on_change
        self._last_mtime = None
        self._thread = None
        self._running = threading.Event()

    def start(self):
        self._running.set()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running.clear()

    def _poll_loop(self):
        while self._running.is_set():
            try:
                if self.path.exists():
                    mtime = self.path.stat().st_mtime
                    if self._last_mtime is not None and mtime != self._last_mtime:
                        cfg = Config.from_file(str(self.path))
                        changed = self._detect_changes(cfg)
                        if changed:
                            self._on_change(cfg, changed)
                    self._last_mtime = mtime
            except Exception:
                pass
            self._running.wait(1.0)

    def _detect_changes(self, new_cfg: Config) -> set[str]:
        old = Config.from_file(str(self.path))
        changes = set()
        for field in Config.__dataclass_fields__:
            if getattr(new_cfg, field) != getattr(old, field):
                changes.add(field)
        return changes
```

### T16: First-run onboarding

**Files:**
- Create: `src/voice_overlay/onboarding.py`
- Modify: `src/voice_overlay/main.py`, `src/voice_overlay/overlay_ui.py`

Onboarding flow:
1. Welcome screen + brief description
2. Model download with progress bar (150MB, show ETA)
3. Hotkey test ("Press and hold Ctrl+Shift+V")
4. Mic check (record 2s, transcribe, show result)
5. Completion screen ("All set! Hold hotkey to dictate anywhere.")

Error recovery at each step (skip, retry, alternative offered). Onboarding persisted via `onboarding_completed: true` in config.

### T17: Structured logging across all modules

**Files:**
- Modify: All modules

Every module gets `logger = logging.getLogger(__name__)`. Log at state transitions (IDLE->RECORDING->TRANSCRIBING->INJECTING), errors, and hotkey events. Log level controlled via `VOICE_OVERLAY_LOG` env var (default WARNING).

---

## Verification Requirements (verification-before-completion)

Each test step must mandate actual output recording:
```
python -m pytest tests/path/test.py::test_name -v 2>&1 | tee -a .brain/CHANGES/test-output.log
```
Expected: PASS/FAIL with explicit assertion. No "verify tests pass" without recorded evidence.

---

## Pass 3 Additions: Immediate Edge-Case Filtering

### Critical Crashers (must fix during M1 implementation):

**E1 - No microphone:** `PortAudioError` crash in hotkey thread.
- Fix: Startup device enumeration in `_validate_environment()`, try/except around `stream.start()`, graceful error in overlay.

**E2 - Headless/no display:** `GLib.GError` at `Gtk.Window()`.
- Fix: Check `os.environ.get("DISPLAY")` or `os.environ.get("WAYLAND_DISPLAY")` before GTK import.

**E3 - Python < 3.10:** `TypeError` on `X | None` union syntax.
- Fix: Version gate at top of `__init__.py` and `main.py`: `assert sys.version_info >= (3, 10)`.

**E4 - pip install fails (PyGObject needs system deps):** GCC `pygobject.h` not found.
- Fix: `scripts/check_deps.sh` pre-flight script (HARD GATE for Task 0).

**E5 - Two instances launched:** Duplicate pynput listeners, audio contention, double injection.
- Fix: `fcntl.flock` PID lock file in `$XDG_RUNTIME_DIR/voice-overlay.lock`.

**E6 - No internet for model download:** App hangs 30s+ on first hotkey press.
- Fix: Move model download to startup (`preload_or_verify()`), add 60s timeout, show progress in overlay.

**E7 - Thread safety (sounddevice callback vs pynput vs GTK):** `np.concatenate` segfault when callback appends mid-iteration.
- Fix: `threading.Lock` on `_buffer` reads/writes; 50ms drain sleep after `stream.stop()`.

**E8 - Accidental hotkey tap (< 200ms):** Near-silence audio → hallucinated text injected.
- Fix: Timestamp guard: ignore releases where `elapsed < 200ms`.

### Structural bugs found:

**B1:** ConfigWatcher `_detect_changes` compares new against itself (always returns empty).
- Fix: Store `self._prev_config` instead of re-reading file.

**B2:** Missing `from __future__ import annotations` across all modules.
- Fix: Add to every `.py` file.

**B3:** `test_smoke.py` instantiates `VoiceOverlayApp` (side effects) despite Pass 1 claim of fix.
- Fix: Actually rewrite the test to use mocks.

### Deferred to M2:
- Config hot-reloading UI flow
- Full onboarding wizard
- Full dependency injection framework
- Unicode > U+FFFF injection handling
- Ctrl+C cache corruption guard
- Max recording timeout (auto-stop)
- Stuck-modifier recovery watchdog
- Hotkey clash detection UI
- Ring buffer for audio

### Implementation Order (Revised):

| Task | Edge-Case Guardrails |
|------|---------------------|
| Task 0 | E4 (check_deps.sh), Python version gate |
| Task 1 | `from __future__ import annotations`, E5 (lock file) |
| Task 2 | N/A |
| Task 3 | E7 (threading.Lock on buffer) |
| Task 4 | E6 (model preload at startup) |
| Task 5 | N/A |
| Task 6 | E8 (200ms debounce), B1 fix |
| Task 7 | E2 (display check before GTK) |
| Task 8 | E1 (mic check), E5 (lock on startup), E7 (lock in state transitions), E6 (preload model) |
| Task 9 | B3 (fix smoke test) |

---

## Pass 3 Additions: M1 Edge-Case Hardening (2026-06-09)

> Applied by: final refinement pass. Scrutinized every component for immediate failures that could block the working prototype. Deferred future/luxury risks to M2.

---

### E1: No microphone — `sounddevice` raises PortAudioError (IMMEDIATE)

**What breaks:** `AudioCapture.start()` calls `sd.InputStream()` with default device. If no mic is plugged in, portaudio raises `OSError("[PaErrorCode -9985] Device unavailable")`. This crashes inside the pynput hotkey thread — the overlay appears, then the app silently dies. On laptops with only HDMI audio, portaudio enumerates zero input devices.

**Fix — two-layer guard:**

Layer 1 (startup): Add a `validate_devices()` function to `audio_capture.py` that queries input devices and returns a list. Call it from `main.py` before constructing the app. If the list is empty, print a clear error to stderr and exit(1) before GTK initializes. Never let the user get to the hotkey stage without a mic.

```python
# Add to audio_capture.py
def list_input_devices() -> list[dict]:
    """Return list of available input devices. Empty list = no mic."""
    if _sd is None:
        return []
    devices = _sd.query_devices()
    return [{"index": i, "name": d["name"], "channels": d["max_input_channels"]}
            for i, d in enumerate(devices) if d["max_input_channels"] > 0]

def validate_microphone() -> bool:
    """Return True if at least one input device exists. Logs details."""
    devices = list_input_devices()
    if not devices:
        return False
    return True
```

Layer 2 (runtime): Wrap `sd.InputStream()` in try/except `OSError` inside `AudioCapture.start()`. On failure, set a `_device_error` string that callers can check.

```python
# In AudioCapture.__init__:
self._device_error: str | None = None

# In AudioCapture.start(), around sd.InputStream():
try:
    self._stream = _sd.InputStream(...)
except OSError as e:
    self._device_error = f"Microphone unavailable: {e}"
    self._recording = False
    raise AudioDeviceError(str(e)) from e
```

Layer 3 (startup check in main.py):
```python
def _validate_environment():
    if not validate_microphone():
        sys.exit("ERROR: No microphone found. Plug in a mic and retry.")
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        sys.exit("ERROR: No display server detected. VoiceOverlay requires a graphical session (X11 or Wayland).")
```

- [ ] Step E1.1: Add `list_input_devices()` and `validate_microphone()` to `audio_capture.py`
- [ ] Step E1.2: Add `_device_error` field and try/except to `AudioCapture.start()`
- [ ] Step E1.3: Add `_validate_environment()` call at top of `VoiceOverlayApp.run()`

---

### E2: Headless system / no GTK display (IMMEDIATE)

**What breaks:** `OverlayWindow.__init__` → `super().__init__()` → GTK checks `$DISPLAY`/`$WAYLAND_DISPLAY`. On headless (SSH, CI, Docker), this raises `GLib.GError: "cannot open display"` and crashes with an unhelpful traceback.

**Fix:** The startup validator from E1 handles this. Additionally, the `gi.require_version("Gtk", "3.0")` at the module top of `main.py` and `overlay_ui.py` succeeds even headless — it only fails when `Gtk.Window()` is instantiated. So the validator must run BEFORE `VoiceOverlayApp.__init__` constructs the overlay.

**Add to `main.py` module-level guard:**
```python
# At the top of main(), before VoiceOverlayApp()
def _check_display():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        sys.exit("ERROR: No display server found. VoiceOverlay requires X11 or Wayland.")

def main():
    _check_display()
    _validate_environment()  # from E1
    # ... rest of startup
```

Note: `import gi; gi.require_version(...)` works headless — only `Gtk.Window()` fails. But the import chain in `main.py` imports `OverlayWindow` which imports `Gtk`. This is fine; the error only triggers at `OverlayWindow(self.config)` in `VoiceOverlayApp.__init__`.

- [ ] Step E2.1: Add `_check_display()` before `VoiceOverlayApp()` in `main()`

---

### E3: Python < 3.10 (IMMEDIATE)

**What breaks:** The codebase uses:
- `X | None` union syntax (PEP 604, Python 3.10+) — e.g., `threading.Thread | None` in hotkey.py line 605
- `list[np.ndarray]` (built-in generics, 3.9+) but without `from __future__ import annotations` on 3.9
- `dataclasses.dataclass` kwargs like `kw_only` (not used, so fine)

A user on Python 3.8 or 3.9 gets `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` at import time — before any useful error message.

**Fix:** Add a version gate at the absolute top of `main.py` before any local imports. Also add it to `__init__.py` so `import voice_overlay` also fails clearly.

```python
# At the very top of src/voice_overlay/__init__.py (new file) AND main.py
import sys
if sys.version_info < (3, 10):
    sys.exit("VoiceOverlay requires Python 3.10 or higher. You have Python {}.{}.".format(*sys.version_info[:2]))
```

The `pyproject.toml` already has `requires-python = ">=3.10"`, but pip only enforces this during `pip install`, not when running directly via `python src/voice_overlay/main.py`. The runtime guard catches both paths.

- [ ] Step E3.1: Add version check to `src/voice_overlay/__init__.py`
- [ ] Step E3.2: Add version check to top of `src/voice_overlay/main.py` (before any voice_overlay imports)

---

### E4: `pip install -e .` failure from missing system deps (IMMEDIATE)

**What breaks:** `pip install PyGObject` compiles C extensions. Without `gobject-introspection-devel`, `cairo-gobject-devel`, `gtk3-devel` (Fedora) or their Debian equivalents, the pip install fails with a cryptic GCC error: `fatal error: pygobject.h: No such file or directory`. Similarly, `pip install sounddevice` needs `portaudio-devel` to compile.

The user sees a wall of compiler errors and gives up. Task 0 (S1) documents the packages but doesn't gate the pip install.

**Fix:** Make Task 0 a **hard prerequisite** with a pre-flight check script.

**Create `scripts/check_deps.sh`:**
```bash
#!/usr/bin/env bash
# Verify system dependencies before pip install
set -euo pipefail

MISSING=""
check_pkg() {
    local name="$1" header="$2"
    if ! pkg-config --exists "$name" 2>/dev/null; then
        MISSING="$MISSING  - $name ($header)\n"
    fi
}

check_pkg "gobject-introspection-1.0" "gobject-introspection-devel / libgirepository1.0-dev"
check_pkg "gtk+-3.0" "gtk3-devel / libgtk-3-dev"
check_pkg "cairo-gobject" "cairo-gobject-devel / libcairo2-dev"
check_pkg "portaudio-2.0" "portaudio-devel / portaudio19-dev"

# Check Python version
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$(python3 -c 'import sys; print(sys.version_info >= (3,10))')" != "True" ]]; then
    echo "ERROR: Python >= 3.10 required, found $PYVER"
    exit 1
fi

if [[ -n "$MISSING" ]]; then
    echo "ERROR: Missing system dependencies:"
    echo -e "$MISSING"
    echo ""
    echo "Install them first:"
    echo "  Fedora: sudo dnf install python3-devel gcc gtk3-devel gobject-introspection-devel cairo-gobject-devel portaudio-devel"
    echo "  Debian/Ubuntu: sudo apt install python3-dev gcc libgtk-3-dev libgirepository1.0-dev libcairo2-dev portaudio19-dev"
    exit 1
fi

echo "All system dependencies satisfied."
```

**Add to Task 0 (S1):**
```
Step 0 (HARD GATE): Run `bash scripts/check_deps.sh`. If it fails, STOP. Do not proceed to pip install. Fix system deps first.
```

- [ ] Step E4.1: Create `scripts/check_deps.sh`
- [ ] Step E4.2: Add Step 0 as a hard gate in Task 0
- [ ] Step E4.3: Make `pip install -e .` step conditional on deps check passing

---

### E5: Two instances of the app (IMMEDIATE)

**What breaks:** Two processes: two pynput keyboard listeners grabbing the same device (evdev), two GTK main loops competing, two audio streams on the same mic. Results: duplicate transcription injected, corrupted audio buffer, or a crash from device contention.

**Fix:** PID-based single-instance lock using `fcntl.flock` on a lock file.

**Create `src/voice_overlay/lockfile.py`:**
```python
import os
import sys
import fcntl
from pathlib import Path

def acquire_lock() -> bool:
    """Acquire exclusive single-instance lock. Returns True if successful."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    lock_dir = Path(runtime_dir) / "voice-overlay"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "instance.lock"

    global _lock_fd
    _lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
        return True
    except (IOError, OSError):
        print("VoiceOverlay is already running. Only one instance allowed.", file=sys.stderr)
        return False
```

**Integrate in `main.py`:**
```python
from voice_overlay.lockfile import acquire_lock

def main():
    if not acquire_lock():
        sys.exit(1)
    # ... rest
```

The lock is automatically released when the process exits (fd closes). `XDG_RUNTIME_DIR` cleans up on reboot, avoiding stale locks.

- [ ] Step E5.1: Create `src/voice_overlay/lockfile.py`
- [ ] Step E5.2: Call `acquire_lock()` at top of `main()`, exit on failure

---

### E6: No internet / model download blocked (IMMEDIATE)

**What breaks:** `WhisperModel("tiny", ...)` downloads 150MB from HuggingFace Hub on first call. If there's no internet, the download hangs indefinitely (no timeout by default) or raises `requests.ConnectionError` after a socket timeout (~30s). The user presses the hotkey, releases, and... nothing happens for 30+ seconds. The overlay is hidden (via `GLib.idle_add`), but no text appears.

The download happens inside `_load_model()` called from `transcribe()`, which runs on the pynput hotkey thread — blocking further hotkey events.

**Fix — preload + timeout:**

```python
# In TranscriptionEngine, add preload method:
import os
import time

def preload_or_verify(self) -> bool:
    """Attempt to download/verify the model. Return True if ready.
    Call at startup, not on first hotkey press."""
    try:
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
        start = time.monotonic()
        self._load_model()
        elapsed = time.monotonic() - start
        logger.info(f"Model '{self.model_size}' loaded in {elapsed:.1f}s")
        return True
    except (OSError, ConnectionError, RuntimeError) as e:
        logger.error(f"Model download failed: {e}")
        return False
```

**In `main.py` startup sequence:**
```python
def _startup_sequence(self):
    """Run pre-flight checks before entering the main loop."""
    if not self.transcriber.preload_or_verify():
        GLib.idle_add(self.overlay.show_error,
            "Cannot download speech model. Check your internet connection.")
        return False
    return True
```

The overlay stays visible with the status message while the model downloads. If it fails, the error shows in the overlay for 5 seconds, then the app exits cleanly.

**Additional: check for cached model:**
```python
# In TranscriptionEngine:
@property
def is_model_cached(self) -> bool:
    """Return True if the model is already in the HuggingFace cache."""
    from pathlib import Path
    cache_dir = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface/hub"))
    model_dir = Path(cache_dir) / "models--Systran--faster-whisper-tiny"
    return model_dir.exists() and any(model_dir.glob("snapshots/*/model.bin"))
```

Use this at startup to skip the preload message if the model is already cached.

- [ ] Step E6.1: Add `preload_or_verify()` to TranscriptionEngine
- [ ] Step E6.2: Add `is_model_cached` property
- [ ] Step E6.3: Move model loading from first `transcribe()` call to startup in `main.py`
- [ ] Step E6.4: Show progress/error in overlay during download

---

### E7: Thread safety — GTK main loop vs pynput vs sounddevice callback (IMMEDIATE)

**What breaks:** Three threads touch shared state without any synchronization:

| Thread | Writes | Reads |
|--------|--------|-------|
| sounddevice callback | `AudioCapture._buffer` (append) | `AudioCapture._recording` |
| pynput hotkey (via callbacks) | `_recording`, `_buffer` (clear), calls `get_audio()` | `_recording`, `_buffer` (concatenation) |
| GTK main loop | overlay labels (via `GLib.idle_add`) | — |

**Specific race conditions:**

1. **`_buffer` race:** sounddevice callback appends to `_buffer` while `get_audio()` calls `np.concatenate(self._buffer)`. In CPython, individual list operations are GIL-atomic, but `np.concatenate` iterates the list in C, releasing the GIL. A callback could fire mid-concatenation and append, causing a segfault or corrupted numpy array.

2. **`_recording` race:** `stop()` sets `_recording = False`, then calls `stream.stop()`. But in-flight callbacks queued before `stop()` may still fire after `stop()` returns, checking `_recording` (which is now False) and discarding the last chunk. Data loss on short recordings.

3. **Hotkey callback blocking:** `_on_hotkey_release()` runs transcription (seconds) on the pynput listener thread. During this time, no new key events are processed. The AppState guard (S3) prevents re-entrance but relies on a plain Python variable read/written from the pynput thread — no lock guarantees visibility across cores.

**Fix — comprehensive locking strategy:**

```python
# In AudioCapture.__init__:
import threading
self._lock = threading.Lock()
self._buffer: list[np.ndarray] = []

# In _audio_callback:
def _audio_callback(self, indata, frames, time_info, status):
    if self._recording:
        chunk = indata[:, 0].copy().astype(np.float32)
        with self._lock:
            self._buffer.append(chunk)

# In get_audio:
def get_audio(self) -> np.ndarray:
    with self._lock:
        if not self._buffer:
            return np.array([], dtype=np.float32)
        return np.concatenate(list(self._buffer))

# In clear:
def clear(self) -> None:
    with self._lock:
        self._buffer.clear()

# After stop() — drain in-flight callbacks:
def stop(self) -> None:
    self._recording = False
    if self._stream:
        self._stream.stop()
        self._stream.close()
        self._stream = None
    # Drain any callbacks queued before stream.stop()
    time.sleep(0.05)
```

**For AppState in main.py, wrap state transitions:**
```python
import threading

class VoiceOverlayApp:
    def __init__(self):
        self._state_lock = threading.Lock()
        self._state = AppState.IDLE
        # ...

    def _transition(self, to_state):
        with self._state_lock:
            if to_state == AppState.RECORDING and self._state != AppState.IDLE:
                return False  # reject if not idle
            if to_state == AppState.IDLE and self._state not in (AppState.RECORDING, AppState.TRANSCRIBING):
                return False
            self._state = to_state
            return True

    def _on_hotkey_press(self):
        if not self._transition(AppState.RECORDING):
            return
        self.audio.start()
        GLib.idle_add(self.overlay.show_overlay)
        GLib.idle_add(self.overlay.update_status, True)

    def _on_hotkey_release(self):
        if not self._transition(AppState.TRANSCRIBING):
            return
        self.audio.stop()
        audio_data = self.audio.get_audio()
        # ... transcription ...
        self._transition(AppState.IDLE)
```

**Move transcription off the pynput thread:** Don't call `transcriber.transcribe()` in the hotkey release callback. Instead, post it to a thread pool or use `GLib.idle_add` with a callback chain. The simplest M1 fix: keep it on the hotkey thread but add a 200ms minimum recording check (E8) that prevents transcription on accidental taps. For M1, the transcription blocking the listener for 2-3 seconds is acceptable — the AppState lock prevents re-entrance during that time.

- [ ] Step E7.1: Add `threading.Lock` to `AudioCapture._buffer` access (all read/write paths)
- [ ] Step E7.2: Add 50ms drain sleep after `stream.stop()` in `AudioCapture.stop()`
- [ ] Step E7.3: Wrap `AppState` transitions in `threading.Lock` in `main.py`
- [ ] Step E7.4: Replace bare `self._state = ...` assignments with `_transition()` calls

---

### E8: Accidental hotkey tap (sub-200ms press) (IMMEDIATE)

**What breaks:** User accidentally taps `Ctrl+Shift+V` (or a cat walks on the keyboard). The pynput listener fires both press and release callbacks in rapid succession. The app: starts audio → stops audio immediately → transcribes near-silence → potentially injects hallucinated text. Even if `transcribe()` returns `""`, the overlay flashes on/off which is jarring.

**Fix:** Track press timestamp, ignore releases under 200ms.

```python
# In VoiceOverlayApp.__init__:
self._min_recording_ms = 200
self._press_time: float = 0.0

# In _on_hotkey_press:
def _on_hotkey_press(self):
    if not self._transition(AppState.RECORDING):
        return
    self._press_time = time.monotonic()
    self.audio.start()
    GLib.idle_add(self.overlay.show_overlay)
    GLib.idle_add(self.overlay.update_status, True)

# In _on_hotkey_release:
def _on_hotkey_release(self):
    elapsed = (time.monotonic() - self._press_time) * 1000
    if elapsed < self._min_recording_ms:
        self.audio.stop()
        self.audio.clear()
        self._transition(AppState.IDLE)
        GLib.idle_add(self.overlay.hide_overlay)
        return
    # ... normal release flow
```

This is critical: without it, any stray hotkey press injects noise into the user's active application.

- [ ] Step E8.1: Add `_press_time` and 200ms minimum guard to `main.py` hotkey callbacks

---

### E9: TextInjector Unicode handling on X11 (LOW — deferred to M2)

**Risk:** `xdotool type` uses `XSendEvent` which doesn't handle Unicode > U+FFFF. `ydotool type` handles full Unicode. `wtype` also does. For M1, this is acceptable — most dictation is ASCII/Latin-1. M2 should use `uinput`-based injection directly.

**Deferred to M2.**

---

### E10: Ctrl+C during model download leaves corrupted cache (LOW — deferred to M2)

**Risk:** KeyboardInterrupt during HuggingFace hub download may leave partial files. faster-whisper's CTranslate2 backend validates model files with checksums and should reject partial downloads on next launch. But the initial download timeout (30s socket) is the bigger M1 concern, already addressed by E6.

**Deferred to M2.**

---

### E11: Rapid-fire hotkey while transcription running (MITIGATED by E7)

The AppState lock (E7.3) prevents re-entrance. If the user presses the hotkey while transcription is in progress, `_transition(RECORDING)` returns False because state != IDLE. The press is silently ignored. Acceptable for M1.

---

### E12: `stream.stop()` with no blocks recorded (MITIGATED by E8)

With the 200ms minimum recording guard, a <200ms tap won't reach transcription. With block_size changing to 4000 (T12), the minimum useful recording is ~250ms. The 200ms guard from E8 covers this — any press under 200ms is discarded entirely. If the user holds for 250ms+ (one block), at least one callback fires and _buffer has data.

**Verdict:** E8 + T12 (reduced block_size to 4000) together handle this. No additional fix needed.

---

### Structural Bug Fixes Found During Pass 3

#### B1: ConfigWatcher `_detect_changes` logic bug (T15)

The `_detect_changes` method reads the file a second time to get "old" state, but gets the same new state (file was just modified). It compares `new_cfg` against `new_cfg`, always returning empty changes.

**Fix:** Store the previous `Config` object as `self._prev_config`, not a re-read.
```python
def _poll_loop(self):
    while self._running.is_set():
        try:
            if self.path.exists():
                mtime = self.path.stat().st_mtime
                if self._last_mtime is not None and mtime != self._last_mtime:
                    new_cfg = Config.from_file(str(self.path))
                    if self._prev_config:
                        changed = self._detect_changes(new_cfg)
                        if changed:
                            self._on_change(new_cfg, changed)
                    self._prev_config = new_cfg
                self._last_mtime = mtime
        except Exception:
            pass
        self._running.wait(1.0)
```

- [ ] Step B1.1: Fix `_detect_changes` to compare against `self._prev_config`

#### B2: `from __future__ import annotations` missing where needed

The plan code uses `list[np.ndarray]` (line 277) and `threading.Thread | None` (line 605) and `str | None` (E1 additions). While `|` requires 3.10+ (handled by E3), the `list[np.ndarray]` syntax on Python 3.9 would need `from __future__ import annotations`. Since we require 3.10+, this is fine — but the type annotation `self._buffer: list[np.ndarray] = []` causes Pylance/Pyright to complain without the import. Add `from __future__ import annotations` to all modules for consistency.

- [ ] Step B2.1: Add `from __future__ import annotations` to top of every `.py` file in `src/voice_overlay/`

#### B3: `test_smoke.py` still creates app with side effects

The Pass 1 G5 fix says "rewrite test_app_creation to only test imports + config" but the plan still shows the original `test_app_creation()` that instantiates `VoiceOverlayApp`. The fix text contradicts the code block — the test needs to actually be rewritten.

- [ ] Step B3.1: Ensure `tests/test_smoke.py` only tests imports, never instantiates `VoiceOverlayApp`

---

### Immediate Edge Cases Summary

| # | Edge Case | Crash? | Fix Level | Applied In |
|---|-----------|--------|-----------|------------|
| E1 | No microphone | Yes (PortAudioError) | 3-layer | audio_capture.py, main.py |
| E2 | Headless / no display | Yes (GLib.GError) | Startup gate | main.py |
| E3 | Python < 3.10 | Yes (SyntaxError) | Version check | __init__.py, main.py |
| E4 | pip install fails (system deps) | Yes (compile error) | Pre-flight script | scripts/check_deps.sh |
| E5 | Two instances | Corruption | PID lock file | lockfile.py |
| E6 | No internet for model | Hang (30s+) | Preload + timeout | transcription.py, main.py |
| E7 | Thread safety (3-thread race) | Segfault/corruption | Locking strategy | audio_capture.py, main.py |
| E8 | Accidental tap (<200ms) | Noise injection | Timestamp guard | main.py |
| B1 | ConfigWatcher logic bug | Silent no-op | Store prev_config | config_watcher.py |
| B2 | Missing `from __future__` | IDE/linter errors | Add import | all .py files |
| B3 | Smoke test creates side effects | CI flakiness | Rewrite test | tests/test_smoke.py |

### Deferred to M2

| Risk | Rationale |
|------|-----------|
| T13: Dependency injection | Nice-to-have for testing, not blocking prototype |
| T15: Config hot-reloading | Luxury feature; config changes require restart for M1 |
| T16: Onboarding wizard | Manual setup via docs acceptable for M1 |
| E9: Unicode > U+FFFF injection | Most dictation is ASCII; xdotool handles Latin-1 |
| E10: Corrupted cache from Ctrl+C | HuggingFace hub validates checksums on next download |
| Max recording timeout (30s) | Can be added later; users unlikely to hit in testing |
| Stuck modifier recovery | Rare edge case with specific window managers |
| Hotkey clash detection | Nice-to-have, not a crash |
| T12: Ring buffer / deque | Performance optimization, not correctness |

### Implementation Order Revision

With E1-E8 injected into M1, the task ordering becomes:

```
Task 0: System dependency verification (S1 + E4 pre-flight)
  → HARD GATE, must pass before any pip install
Task 1: Project scaffolding (+ E3 version check in __init__.py)
Task 2: Config module (+ B2 annotations)
Task 3: Audio capture module (+ E1 layer 1-2, E7 locking, B2 annotations)
Task 4: Transcription engine (+ E6 preload, E6 timeout, B2 annotations)
Task 5: Text injector module (+ B2 annotations)
Task 6: Hotkey listener module (+ B2 annotations)
Task 7: GTK Overlay UI (+ B2 annotations)
Task 8: Main entry point (+ E1 layer 3, E2 display check, E5 lock file,
                         E7 AppState lock, E8 debounce, B2 annotations)
Task 9: Integration test & smoke test (+ B3 fix)
```

Edge cases E1-E8 and bugs B1-B3 should be implemented INLINE with their respective tasks, not as a separate pass — they are guardrails, not features.
