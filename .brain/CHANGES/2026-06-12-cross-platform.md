# Execution History — 2026-06-12 (Cross-Platform Port)

## Phase: M3 — Multi-Platform Architecture

### Overview
Restructured VoiceOverlay from a Linux-only app into a cross-platform codebase supporting Linux and Windows. The core (audio capture, transcription, config) was already cross-platform. The three Linux-kernel-dependent subsystems (hotkey, text injection, process locking) were extracted into platform backends under a new `_platform/` package with a factory pattern.

### Worker 1A: Platform Foundation
- Created `_platform/__init__.py` — factory with lazy imports, `PlatformBackendError`
- Created `_platform/config.py` — platform-aware `config_dir()` and `runtime_dir()` helpers
- Modified `config.py` — `config_path()` uses `_platform/config.py` helpers
- Modified `pyproject.toml` — removed `PyGObject` and `scipy`, made `evdev` optional (`[linux]` extras)
- Modified `requirements.txt` — cleaned up deps, added optional dep comments
- Created sub-package stubs: `_platform/hotkey/`, `_platform/injection/`, `_platform/lockfile/`

### Worker 2A: Hotkey Backend
- Created `_platform/hotkey/linux.py` — `LinuxEvdevHotkeyListener` (moved from `hotkey.py`, evdev-based)
- Created `_platform/hotkey/windows.py` — `WindowsHotkeyListener` (pynput-based, lazy ctypes imports)
- Modified `_platform/hotkey/__init__.py` — platform-appropriate re-export
- Modified `hotkey.py` — thin shim, backward-compatible `EvdevHotkeyListener` re-export

### Worker 2B: Injection Backend
- Created `_platform/injection/linux.py` — `UinputInjector` (moved from `uinput_injector.py` with `is_available()`)
- Created `_platform/injection/windows.py` — `WindowsInjector` (SendInput + Win32 clipboard with lazy ctypes)
- Modified `_platform/injection/__init__.py` — platform-appropriate re-export
- Modified `uinput_injector.py` — thin shim, backward-compatible re-export
- Modified `text_injector.py` — uses `create_text_injector()` factory, platform-aware clipboard

### Worker 2C: Lockfile Backend
- Created `_platform/lockfile/linux.py` — fcntl.flock with `runtime_dir()` from config helper
- Created `_platform/lockfile/windows.py` — PID file with O_EXCL + stale PID detection
- Modified `_platform/lockfile/__init__.py` — platform-appropriate re-export
- Modified `lockfile.py` — thin shim (no module-level `import fcntl`)

### Worker 3: Integration
- Modified `main.py` — `_ensure_input_access()` gated on `sys.platform == "linux"`, SIGTERM handler gated
- Modified `scripts/check_deps.sh` — removed GTK3 checks (gobject-introspection, gtk+-3.0, cairo-gobject)
- Created `scripts/check_deps.ps1` — Windows dependency verification script

### Worker 4: Test Updates
- Modified `tests/test_text_injector.py` — updated 4 tests to mock `create_text_injector()` factory instead of `UinputInjector`
- Modified `tests/test_config.py` — `test_default_config_path()` uses platform-agnostic assertion
- All 41 tests pass on Linux (41/41)

### Key Design Decisions
- Factory uses lazy imports (platform-specific imports inside function bodies, never at module top level)
- All backends include `is_available()` classmethod and `check_permissions()` method
- Backward-compatible re-exports in all shim modules (existing tests need zero changes)
- Windows backends use only `ctypes` (no `pywin32` dependency) for minimal dependency surface
- Config file format frozen — existing Linux users see zero config changes
- Windows hotkey uses `pynput` (works properly on Windows with real global hook)
- Windows injection uses SendInput with clipboard fallback

### Remaining / Deferred
- No Windows CI — Windows backend validated via mocking only on Linux CI
- macOS backend not in scope (`_platform/*/macos.py` would be straightforward to add)
