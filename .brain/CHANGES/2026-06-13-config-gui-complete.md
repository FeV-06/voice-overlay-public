# 2026-06-13 — Config GUI Complete + Hotkey UX Fixes

## Summary
Finished the config GUI & system tray milestone. All 77 tests pass. Features: PySide6 config window with 6 sections, collapsible Advanced, system tray with Wayland support, Windows autostart robustness, hotkey save-on-release, QScrollArea centering.

## Changes

### Config GUI (`src/voice_overlay/gui/`)
- **config_window.py**: QMainWindow with Audio, Transcription, Hotkey, Output, Behavior, Advanced sections. QScrollArea with vertical scrollbar always-on (prevents content shift). CollapsibleSection for Advanced. Tray-aware footer (Minimize to Tray / Hide to Background + Quit).
- **settings_widgets.py**: HotkeyRecorder (click-to-rebind, saves on release of all keys, live combo display, QKeySequence for proper "Space" naming), ComputeSelector (linked device/compute-type), CollapsibleSection (▶/▼ toggle).
- **system_tray.py**: QSystemTrayIcon with context menu. Always calls show() for Wayland StatusNotifierItem.
- **theme.py**: Dark QSS stylesheet.

### Cross-platform (`src/voice_overlay/_platform/`)
- **autostart.py**: LinuxAutostart (desktop file), WindowsAutostart (winreg), FallbackAutostart. Windows uses `shutil.which("voice-overlay")` preference, quoted path fallback.

### Core changes
- **config.py**: PermissionError handling in save(). 7 config fields.
- **main.py**: Deferred PySide6 imports, cancellable background preload, tray integration, PermissionError recovery.

### Bug fixes
- Config save PermissionError — root cause: pkexec-created dir. Fix: try/except with descriptive error.
- Advanced section: CollapsibleSection replaced broken QGroupBox.setCheckable.
- HotkeyRecorder: border clipping fixed (removed min-height), save-on-release (separate _recorded/_pressed lists), modifier-only release resets listening, Space displays as "Space".
- Scroll centering: removed max-width wrapper, scrollbar always-on prevents content width shift.

### Tests
- test_gui.py: 17 tests (window creation, tray paths, validation, hotkey, close event).
- test_autostart.py: 13 tests (Linux/Windows/Fallback, shutil.which resolution, OSError fallback, path spaces).
- 77 total, all passing.

## Known Issues
- Pause/Resume tray action is placeholder (disabled, "Coming soon" tooltip).
- Custom word replacements has beta placeholder label.
- Package not yet on PyPI.
