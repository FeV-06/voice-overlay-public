# VoiceOverlay Tasks — Final State

## Completed ✅

### Task 1: Project scaffolding
- [x] pyproject.toml, requirements.txt, __init__.py
- [x] Directory structure
- [x] git init

### Task 2: Config module
- [x] Config dataclass (hotkey, model, language, block_size, overlay properties)
- [x] JSON load/save to platform-aware config path
- [x] 6 tests pass

### Task 3: Audio capture
- [x] sounddevice InputStream at 16kHz
- [x] Thread-safe buffer with threading.Lock
- [x] 6 tests pass

### Task 4: Transcription engine
- [x] faster-whisper wrapper (small model, English, int8, CPU)
- [x] Model preload at startup
- [x] 6 tests pass

### Task 5: Text injection
- [x] uinput virtual keyboard via /dev/uinput (Linux)
- [x] SendInput + clipboard injection (Windows)
- [x] Character-to-keycode mapping with shift combos
- [x] Clipboard fallback for untypeable chars
- [x] 4 tests pass

### Task 6: Hotkey listener
- [x] evdev global key detection from /dev/input/event* (Linux)
- [x] pynput global hook (Windows)
- [x] 200ms hold gate for spurious release filtering
- [x] Primary-key tracking (release only on Space)
- [x] 2 tests pass

### Task 7: GTK Overlay UI
- [x] ~~Built, then removed~~ — headless approach chosen
- [x] Focus-stealing issue unresolvable on Mutter Wayland

### Task 8: Main entry point
- [x] Headless VoiceOverlayApp
- [x] AppState state machine (IDLE → RECORDING → TRANSCRIBING → INJECTING)
- [x] pkexec auto-elevation with full env passthrough (Linux)
- [x] Signal handling for clean shutdown (SIGTERM gate)
- [x] PID singleton lock (fcntl on Linux, PID file on Windows)

### Task 9: Integration test
- [x] Smoke tests for all modules
- [x] 41 tests total, all pass

### Task 10: Incremental transcription
- [x] ~~Removed with overlay~~ — no visual output in headless mode

### M3: Cross-Platform Architecture
- [x] `_platform/` package with factory pattern
- [x] `_platform/config.py` — platform-aware path helpers
- [x] `_platform/hotkey/linux.py` — LinuxEvdevHotkeyListener (evdev)
- [x] `_platform/hotkey/windows.py` — WindowsHotkeyListener (pynput)
- [x] `_platform/injection/linux.py` — UinputInjector (uinput)
- [x] `_platform/injection/windows.py` — WindowsInjector (SendInput + clipboard)
- [x] `_platform/lockfile/linux.py` — fcntl.flock lock
- [x] `_platform/lockfile/windows.py` — PID file with O_EXCL
- [x] `pyproject.toml` — evdev optional dep
- [x] `scripts/check_deps.sh` — GTK checks stripped
- [x] `scripts/check_deps.ps1` — Windows dependency checker
- [x] `main.py` — platform-gated pkexec + SIGTERM
- [x] Existing 41 tests all pass unchanged
- [x] All platform-specific imports are lazily loaded (safe cross-platform import)

## Deferred
- macOS backend — not requested
- Visual feedback (system notification on injection)
- Toggle mode alternative (tap to start, tap to stop)
- Config hot-reloading
- Onboarding sequence
- Windows CI setup (GitHub Actions runner)
