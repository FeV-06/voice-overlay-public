from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from copy import deepcopy
from enum import Enum, auto

from voice_overlay.config import Config
from voice_overlay.audio_capture import AudioCapture, AudioDeviceError, validate_microphone, list_input_devices
from voice_overlay.transcription import TranscriptionEngine
from voice_overlay._platform import create_hotkey_listener
from voice_overlay._platform.autostart import create_autostart
from voice_overlay.text_injector import TextInjector
from voice_overlay.lockfile import acquire_lock

logger = logging.getLogger(__name__)


class AppState(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    INJECTING = auto()


def _validate_environment() -> None:
    devices = list_input_devices()
    logger.debug("Found %d input device(s): %s", len(devices), [d["name"] for d in devices])
    if not validate_microphone():
        sys.exit("ERROR: No microphone found. Plug in a mic and retry.")


class VoiceOverlayApp:
    def __init__(self):
        self.config = Config.from_file(str(Config.config_path()))
        self._state_lock = threading.Lock()
        self._state = AppState.IDLE
        self._engine_started = False
        self._preload_cancel = threading.Event()

        self.audio = AudioCapture(block_size=self.config.block_size)
        self.transcriber = TranscriptionEngine(
            model_size=self.config.model,
            language=self.config.language,
        )
        self.injector = TextInjector()
        self._hotkey = None

        self._transcription_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

    def _transition(self, to_state: AppState) -> bool:
        with self._state_lock:
            old = self._state
            if to_state == AppState.RECORDING and self._state != AppState.IDLE:
                logger.debug("_transition %s->%s DENIED (not IDLE)", self._state.name, to_state.name)
                return False
            if to_state == AppState.TRANSCRIBING and self._state != AppState.RECORDING:
                logger.debug("_transition %s->%s DENIED (not RECORDING)", self._state.name, to_state.name)
                return False
            if to_state == AppState.INJECTING and self._state != AppState.TRANSCRIBING:
                logger.debug("_transition %s->%s DENIED (not TRANSCRIBING)", self._state.name, to_state.name)
                return False
            self._state = to_state
            logger.debug("_transition %s->%s OK", old.name, to_state.name)
            return True

    def _on_hotkey_press(self):
        logger.debug("HOTKEY PRESS")
        if not self._transition(AppState.RECORDING):
            return
        try:
            self.audio.start()
        except AudioDeviceError as e:
            logger.error("Audio device error: %s", e)
            self._transition(AppState.IDLE)
            return

    def _on_hotkey_release(self):
        logger.debug("HOTKEY RELEASE")
        if not self._transition(AppState.TRANSCRIBING):
            return

        self.audio.stop()
        audio_data = self.audio.get_audio()
        logger.debug("Audio captured: %.2fs, %d samples", len(audio_data) / 16000, len(audio_data))

        if len(audio_data) == 0:
            logger.debug("No audio captured, skipping")
            self._transition(AppState.IDLE)
            self.audio.clear()
            return

        text = ""
        try:
            text = self.transcriber.transcribe(audio_data, self.config.word_replacements)
        except Exception as e:
            logger.error("Transcription failed: %s", e)

        logger.debug("Transcription result (%d chars): '%s'", len(text), text)
        self._transition(AppState.INJECTING)
        if text.strip():
            success = self.injector.inject(text.strip())
            if not success:
                logger.warning("Text injection failed (clipboard fallback used)")

        self._transition(AppState.IDLE)
        self.audio.clear()

    def _preload_model_background(self) -> bool:
        if self._preload_cancel.is_set():
            return False
        try:
            logger.debug("Preloading model in background (cpu/int8)...")
            if not self.transcriber.preload_or_verify():
                logger.error("Model preload failed — continuing anyway")
                return False
            return True
        except Exception as e:
            logger.error("Model preload error: %s", e)
            return False

    def _start_engine(self) -> None:
        if self._engine_started:
            return

        if not self.config.config_path().exists():
            self.config.save(str(self.config.config_path()))
            logger.info("Created default config at %s", self.config.config_path())

        self._recreate_hotkey()
        logger.info("VoiceOverlay ready. Press %s to dictate.", self.config.hotkey)
        self._hotkey.start()
        self._engine_started = True

    def _recreate_hotkey(self) -> None:
        if self._hotkey:
            try:
                self._hotkey.stop()
            except Exception:
                pass
        self._hotkey = create_hotkey_listener(
            hotkey=self.config.hotkey,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )

    def _apply_settings(self, settings: dict) -> None:
        old_config = deepcopy(self.config)

        for key in ("input_device", "model", "language", "hotkey", "auto_inject",
                     "launch_at_login", "show_config_window", "vad_filter",
                     "device", "compute_type", "block_size"):
            if key in settings:
                setattr(self.config, key, settings[key])

        try:
            self.config.save(str(self.config.config_path()))
        except PermissionError:
            logger.error("Cannot write config to %s — check file/directory permissions", self.config.config_path())

        autostart = create_autostart()
        if self.config.launch_at_login:
            autostart.enable()
        else:
            autostart.disable()

        model_changed = settings.get("model_changed", False)

        if model_changed:
            self._preload_cancel.set()
            self._preload_cancel = threading.Event()

            try:
                self.transcriber = TranscriptionEngine(
                    model_size=self.config.model,
                    language=self.config.language,
                    compute_type=self.config.compute_type,
                    device=self.config.device,
                    vad_filter=self.config.vad_filter,
                )
                if not self.transcriber.preload_or_verify():
                    raise RuntimeError("Model reload failed")
                logger.info("Model reloaded with new settings")
            except Exception as e:
                logger.error("Model reload failed: %s — reverting to previous config", e)
                self.config = old_config
                self.config.save(str(self.config.config_path()))
                self.transcriber = TranscriptionEngine(
                    model_size=self.config.model,
                    language=self.config.language,
                )
                return

        if not self._engine_started:
            self._start_engine()

    def _shutdown(self):
        logger.info("Shutting down...")
        self._shutdown_event.set()
        self._preload_cancel.set()
        if self._hotkey:
            self._hotkey.stop()
        self.audio.stop()

    def run(self):
        _validate_environment()
        if not acquire_lock():
            sys.exit(1)

        pyside6_available = True
        try:
            from PySide6 import QtCore
            QtCore  # noqa
        except ImportError:
            pyside6_available = False

        if not pyside6_available:
            logger.info("PySide6 not available — running headless")
            if not self.config.config_path().exists():
                self.config.save(str(self.config.config_path()))
            background_preload = threading.Thread(target=self._preload_model_background, daemon=True)
            background_preload.start()
            background_preload.join()
            self._start_engine()

            self._shutdown_event.wait()
            self._shutdown()
            return

        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)

        from voice_overlay.gui.theme import APP_STYLESHEET
        app.setStyleSheet(APP_STYLESHEET)

        show_window = self.config.show_config_window

        self._preload_cancel = threading.Event()
        preload_thread = threading.Thread(target=self._preload_model_background, daemon=True)
        preload_thread.start()

        from voice_overlay.gui.system_tray import SystemTray
        from voice_overlay.gui.config_window import ConfigWindow

        config_window = ConfigWindow(self.config, tray_available=SystemTray.isSystemTrayAvailable())
        tray = SystemTray(config_window)

        if show_window:
            config_window.show()

            def on_saved(settings: dict) -> None:
                self._apply_settings(settings)
                if tray.available:
                    config_window.hide()

            config_window.saved.connect(on_saved)
        else:
            logger.info("Skipping config window (show_config_window=False)")
            self._apply_settings({
                "model_changed": False,
                "input_device": self.config.input_device,
            })

            if not config_window.isVisible():
                config_window._on_minimize()

        def check_preload_and_start():
            if not self._engine_started and not preload_thread.is_alive():
                self._start_engine()
            elif not self._engine_started:
                QTimer.singleShot(500, check_preload_and_start)

        if not show_window:
            QTimer.singleShot(500, check_preload_and_start)

        # Periodic timer allows the Qt event loop to process Python signals
        # (SIGINT / Ctrl+C) which would otherwise be blocked in C++ code.
        _sigint_received = False

        def _handle_sigint(signum, frame):
            nonlocal _sigint_received
            _sigint_received = True

        import signal
        signal.signal(signal.SIGINT, _handle_sigint)

        _sigint_timer = QTimer()
        _sigint_timer.start(200)
        def _check_sigint():
            nonlocal _sigint_received
            if _sigint_received:
                app.quit()
        _sigint_timer.timeout.connect(_check_sigint)

        app.aboutToQuit.connect(self._shutdown)
        sys.exit(app.exec())


def _ensure_input_access() -> None:
    if sys.platform != "linux":
        logger.debug("Windows platform — elevation not required")
        return
    if os.geteuid() == 0:
        return
    accessible = 0
    blocked = 0
    for name in sorted(os.listdir("/dev/input")):
        if not name.startswith("event"):
            continue
        try:
            fd = os.open(f"/dev/input/{name}", os.O_RDONLY)
            os.close(fd)
            accessible += 1
            break
        except PermissionError:
            blocked += 1
        except OSError:
            continue

    if accessible == 0 and blocked > 0:
        print("Re-launching with pkexec for /dev/input and /dev/uinput access...")
        env_args = []
        for var in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE",
                    "DBUS_SESSION_BUS_ADDRESS", "HOME", "XAUTHORITY", "PATH", "VIRTUAL_ENV"):
            val = os.environ.get(var, "")
            if val:
                env_args.append(f"{var}={val}")
        cmd = ["pkexec", "env"] + env_args + [sys.executable] + sys.argv
        os.execvp("pkexec", cmd)


def main():
    parser = argparse.ArgumentParser(description="VoiceOverlay - Silent voice transcription")
    parser.add_argument("-v", "--debug", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(threadName)s] %(levelname)s %(name)s: %(message)s",
    )
    if args.debug:
        logger.debug("Verbose debug logging enabled")

    _ensure_input_access()
    app = VoiceOverlayApp()
    app.run()


if __name__ == "__main__":
    main()
