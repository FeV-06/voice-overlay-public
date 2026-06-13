# Project: VoiceOverlay

## Identity
- **Name**: VoiceOverlay
- **Description**: Headless real-time voice transcription for Linux and Windows. Reads microphone input, transcribes via faster-whisper, injects text at cursor. Ships with a PySide6 config GUI, system tray, and collapsible Advanced section.
- **Platform**: Linux (Fedora, Wayland + PipeWire), Windows 10/11
- **Language**: Python 3.10+
- **Package**: Available via `uv tool install` from local source; `voice-overlay` entry point resolves globally via `shutil.which`

## Current Phase
- **Phase**: Config GUI & System Tray — DONE
- **Current Objective**: Testing on Windows before release
- **Active Milestone**: M4 — Config GUI & System Tray (complete)
- **Last Verdict**: 77/77 tests passing. All GUI, autostart, transcription, config tests green.

## How It Works
1. On boot: load config → show config window → preload model in background (non-fatal if fails)
2. User customizes: audio device, model, language, hotkey, auto-inject, advanced settings (compute, VAD, block size)
3. On save ("Save & Start"): persist to config.json → reload model if settings changed → start engine
4. On close: hide to system tray (tray available) or show "Running" status + Quit button (no tray)
5. "Show configuration on startup" checkbox → window skipped on next boot
6. Quit from tray → actual exit

## Tech Stack
- **GUI**: PySide6 (Qt6) — single-page form with QScrollArea (vertical always-on, horizontal off)
- **Tray**: QSystemTrayIcon with context menu (Show Window, Pause/Resume placeholder, Quit). Always calls `show()` for Wayland StatusNotifierItem.
- **Config persistence**: Config dataclass (7 fields) → `~/.config/voice-overlay/config.json`
- **Model lifecycle**: Background preload on CPU defaults, reload on change, cancellable
- **Hotkey**: platform backends (evdev/pynput for Linux, pynput for Windows)
- **Injection**: uinput for Linux (Wayland/X11), SendInput for Windows, clipboard fallback

## GUI Layout
- **Audio**: QFormLayout — Input Device (combo), Model (combo), Language (combo)
- **Transcription**: QFormLayout — Word timestamps toggle (combo), Context prompt (edit)
- **Hotkey**: HotkeyRecorder (click to rebind, saves on release of all keys, QKeySequence for display)
- **Output**: QCheckBox "Auto-inject at cursor (off = copy to clipboard)" — centered
- **Behavior**: QCheckBox "Launch at login" — centered
- **Advanced** (CollapsibleSection ▶/▼): Show on startup check, VAD check, Compute selector (linked device/compute-type combos), Audio Block Size combo, Beta placeholder for word replacements

## Cross-Platform Details
- **`_platform/` abstract factory**: Hotkey (evdev/pynput), Injection (uinput/SendInput), Lockfile (fcntl/msvcrt), Autostart (desktop file/winreg)
- **Windows autostart**: Uses `winreg` (built-in). Command preference: (1) `shutil.which("voice-overlay")` → quoted resolved path, (2) fallback `f'"{sys.executable}" -m voice_overlay'`. Handles OSError.
- **Linux autostart**: Creates `~/.config/autostart/voice-overlay.desktop` with `Exec=voice-overlay`
- **GNOME Wayland tray**: No native system tray. Install `gnome-shell-extension-appindicator` for Background Apps support. No-tray fallback: "Hide to Background" button + "Running" label + Quit button.
- **Two UI paths**: Tray available → "Minimize to Tray", hide-on-save, restore from tray. No tray → "Hide to Background" + Quit + "Running" status.

## Key Bug Fixes This Session
- **Config save PermissionError**: `save()` wraps mkdir+write in try/except. Root cause: prior `pkexec` runs created `~/.config/voice-overlay/` as root.
- **Advanced section → collapsible**: New `CollapsibleSection` widget (▶/▼ toggle). Replaced broken `QGroupBox.setCheckable(True)`.
- **HotkeyRecorder border clipping**: Removed `min-height` from QLabel stylesheet. Increased padding 6px→8px.
- **Scrolling**: `QScrollArea` with no horizontal scrollbar, vertical scrollbar always on (prevents content width shift).
- **Centering**: Checkboxes centered with `Qt.AlignCenter`, form content centered via `scroll.setAlignment`.
- **Hotkey capitalize**: `str.capitalize()` was wrong for "ctrl+shift+space" (produced "Ctrl+shift+space"). Replaced with split+join pattern.
- **Hotkey save-on-release**: Uses `_recorded` (all keys pressed during session) + `_pressed` (currently held keys). Saves when ALL keys released AND a non-modifier key was pressed. Modifier-only release just resets listening.
- **Space displays as "Space"**: Uses `QKeySequence().toString(PortableText)` instead of raw `event.text()`.

## Next Steps
1. Test full workflow on Windows (hotkey, injection, autostart, tray)
2. Implement Pause/Resume system tray action (placeholder, disabled with "Coming soon")
3. Custom word replacements UI in Advanced section
4. Release to PyPI for `uv tool install voice-overlay` from registry
5. Handle edge cases: multi-monitor tray positioning, Qt platform plugin fallbacks on Windows

## Relevant Files
- `src/voice_overlay/gui/config_window.py` — QMainWindow with 6 sections, QScrollArea, CollapsibleSection, tray-aware footer
- `src/voice_overlay/gui/settings_widgets.py` — HotkeyRecorder, ComputeSelector, CollapsibleSection
- `src/voice_overlay/gui/system_tray.py` — QSystemTrayIcon + context menu
- `src/voice_overlay/gui/theme.py` — Dark QSS stylesheet
- `src/voice_overlay/_platform/autostart.py` — LinuxAutostart, WindowsAutostart, FallbackAutostart
- `src/voice_overlay/config.py` — Config dataclass, save/load with PermissionError handling
- `src/voice_overlay/main.py` — Deferred PySide6 imports, cancellable preload, tray integration
- `tests/test_gui.py` — 17 GUI tests
- `tests/test_autostart.py` — 13 autostart tests
- `docs/superpowers/specs/2026-06-13-config-gui-design.md` — Design spec

## Config Fields (7)
`input_device`, `compute_type`, `device`, `vad_filter`, `auto_inject`, `launch_at_login`, `show_config_window`

## Test Suite
- 77 tests total: original 41 + 16 GUI + 10 autostart + 5 smoke import + 4 autostart command + 1 close event
- Qt tests run with `QT_QPA_PLATFORM=offscreen`
- Pytest runs from venv-local binary (pytest added as dev dep)

## Last Updated
2026-06-13 (full session: config GUI, system tray, autostart robustness, hotkey UX fixes, scroll/centering)
