# Context: Cross-Platform Port Plan

## Snapshot
- **Date**: 2026-06-12
- **Phase**: Plan refinement completed
- **Plan file**: `.brain/ARTIFACTS/plans/cross-platform-port-plan.md`
- **Refiner**: plan-refiner subagent

## Decisions Made
1. Worker 1B merged into Worker 1A (excessive handoff overhead for trivial scaffolding)
2. Factory API contract (protocol signatures) must be defined in `_platform/__init__.py` before Phase 2 workers begin
3. `lockfile.py` linux backend must use `_platform/config.runtime_dir()` instead of hardcoded `XDG_RUNTIME_DIR`
4. `text_injector.py` must stop directly importing `UinputInjector` — use factory from `_platform` instead
5. `check_deps.sh` must have GTK checks stripped (headless design no longer needs them)
6. Each worker produces a handoff manifest (files created/modified/read + new API surface) for downstream workers
7. Shim modules (`hotkey.py`, `lockfile.py`, `uinput_injector.py`) must re-export original names for test backward compatibility
8. Pass 2 decisions:
   - Windows hotkey callback must never let Python exception propagate into Win32 callback dispatcher
   - Named mutex should use session-scoped name derived from user SID, not fixed app name
   - Each backend protocol must include `is_available()` classmethod and `check_permissions()` method
   - Factory must raise `PlatformBackendError` (never raw ImportError) for missing backends
   - Config file format must stay identical — existing Linux users see zero config change
   - Signal handlers must be gated: `SIGTERM` on Linux only, `SIGBREAK` on Windows
   - Windows hotkey thread requires `PeekMessageW` loop or `pynput` for message pump
   - Security threat model document must be created in Worker 3
9. Pass 3 decisions (import audit + edge cases):
   - Full import audit: `lockfile.py` `import fcntl` and `uinput_injector.py` `import fcntl` are unconditional `ModuleNotFoundError` crashes on Windows — shims must never replicate these
   - `ctypes.windll` does not exist on Linux — all Windows backend files must be lazily imported inside factory functions, never at module level
   - `_platform/__init__.py` factory must use lazy imports (inside each factory function, not top-level) to avoid importing Linux backends on Windows and vice versa
   - `from select import select` works on Windows but only supports sockets, not file descriptors — harmless since `_find_keyboards()` fails first, but the Windows backend must not use `select`
   - `os.geteuid()` returns 0 on Windows (emulates root) — Worker 3 must use `if sys.platform != "linux": return` instead of `if os.geteuid() == 0: return`
   - `test_default_config_path()` asserts `.config/voice-overlay/config.json` — **will fail on Windows** after refactoring. Worker 4 must update to platform-agnostic assertion or gate the test
   - Windows backend tests on Linux CI must patch `ctypes.windll` before any backend module import
   - Factory must use `importlib.import_module()` or inline imports inside function body — never `from _platform.*.windows import ...` at top level

## Files Analyzed
- `src/voice_overlay/config.py` — 54 lines, needs `_platform/config.py` helpers for platform-aware paths
- `src/voice_overlay/hotkey.py` — 199 lines, has module-level `import struct` and `from select import select` (risk for shim)
- `src/voice_overlay/uinput_injector.py` — 194 lines, has module-level `import fcntl` and `import struct` (risk for shim)
- `src/voice_overlay/text_injector.py` — 57 lines, directly imports `UinputInjector` (must be refactored)
- `src/voice_overlay/lockfile.py` — 30 lines, has module-level `import fcntl` (crash risk on Windows)
- `src/voice_overlay/main.py` — 197 lines, imports concrete classes by name (shims must preserve exports)
- `pyproject.toml` — 19 lines, `evdev`, `PyGObject`, `scipy` deps need restructuring
- `requirements.txt` — 6 lines, mirrors pyproject.toml deps
- `scripts/check_deps.sh` — 35 lines, checks GTK deps that are no longer needed

## Risks Identified
- Module-level `import fcntl` in `lockfile.py` and `uinput_injector.py` will crash on Windows import
- `text_injector.py` display server detection (`XDG_SESSION_TYPE`) is Linux-only
- No Windows CI — Windows backend validated via mocking only
- `scripts/check_deps.ps1` may need adjustment post-merge
- `test_default_config_path()` will fail on Windows after refactoring (hardcodes `.config/` path)
- Windows backend tests on Linux CI require `@patch('ctypes.windll')` before any import
- Factory `_platform/__init__.py` must use lazy imports — any top-level platform-specific import crashes on the other OS
- `os.geteuid()` returns 0 on Windows (emulates root) — the `_ensure_input_access()` guard must use `sys.platform` instead

## Notes for Next Agent
- Handoff manifests are the contract between workers — enforce them
- Phase 2 workers (2A, 2B, 2C) are fully independent and can run in any order after Phase 1
- Phase 3 must wait for all Phase 2 workers to complete (modifies `main.py` which depends on all shims)
- Phase 4 must run last (tests the integrated system)
- Backward-compatible import paths in shims are critical for zero-test-change requirement
- **Pass 2 critical notes:**
  - Worker 1A now adds `is_available()`, `check_permissions()`, and `PlatformBackendError` to the protocol definitions
  - Worker 2C must use session-scoped mutex name on Windows (not fixed `"VoiceOverlay-Instance"`)
  - Worker 2A Windows thread must include `PeekMessageW` pump for SetWindowsHookEx to fire
  - Worker 3 must gate `SIGTERM` behind `sys.platform != 'win32'` and add `SIGBREAK` handler on Windows
  - Worker 3 must create `docs/security.md` with threat model for all three backend paths
  - Worker 4 must add mock-based error-path tests: factory import failure, is_available(), fallback chain, lockfile contention
  - Config file format is frozen — do not add/remove/reorder config.json keys
- **Pass 3 critical notes (import safety + edge cases):**
  - Worker 1A `_platform/__init__.py` factory MUST use lazy imports (inside function body), NEVER `from _platform.*.windows import ...` at top level
  - Worker 2A/2B/2C must ensure moved Linux backend code keeps `fcntl`, `struct`, `select`, `evdev` imports INSIDE the backend file, never in `__init__.py` or the shim
  - Worker 3 must replace `if os.geteuid() == 0: return` with `if sys.platform != "linux": return` in `_ensure_input_access()`
  - Worker 4 must update `test_default_config_path()` to platform-agnostic assertion (e.g., `endswith("voice-overlay/config.json")` without the `.config/` prefix)
  - Worker 4 Windows backend tests must use `@patch('ctypes.windll')` before any import — document this pattern
  - After each Worker 2 phase, verify `python -c "from voice_overlay.lockfile import acquire_lock"` on Linux still works
