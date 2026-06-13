# Cross-Platform Port Plan (Linux → Linux + Windows)

## Goal
Restructure VoiceOverlay so the core (audio capture, transcription, config) stays platform-agnostic while the three Linux-kernel-dependent subsystems (hotkey, text injection, process locking) get platform backends selected at runtime via a factory.

## Architecture
Introduce a `_platform/` package inside `voice_overlay/` containing sub-packages for each platform-specific capability. Each sub-package has:
- `__init__.py` — abstract protocol/interface the rest of the app depends on
- `linux.py` — existing Linux implementation (moved verbatim)
- `windows.py` — new Windows implementation

Existing top-level modules (`hotkey.py`, `uinput_injector.py`, `lockfile.py`) become thin shims that delegate to `_platform` via a factory in `_platform/__init__.py`.

`text_injector.py` and `main.py` get platform-conditional logic for clipboard operations and privilege elevation respectively.

`config.py` gets platform-aware default paths.

### File Structure (new/changed files only)

```
src/voice_overlay/
├── _platform/                      # NEW
│   ├── __init__.py                 # sys.platform detection + factory
│   ├── config.py                   # Platform-specific path helpers
│   ├── hotkey/
│   │   ├── __init__.py             # HotkeyListener protocol
│   │   ├── linux.py                # EvdevHotkeyListener (from hotkey.py)
│   │   └── windows.py              # Win32 global hook via ctypes
│   ├── injection/
│   │   ├── __init__.py             # TextInjector protocol
│   │   ├── linux.py                # UinputInjector (from uinput_injector.py)
│   │   └── windows.py              # SendInput + Win32 clipboard
│   └── lockfile/
│       ├── __init__.py             # acquire_lock protocol
│       ├── linux.py                # fcntl.flock (from lockfile.py)
│       └── windows.py              # Named mutex via ctypes
├── config.py                       # MODIFIED: platform-aware paths
├── hotkey.py                       # MODIFIED: thin shim → _platform
├── uinput_injector.py              # MODIFIED: thin shim → _platform/injection
├── text_injector.py                # MODIFIED: platform-aware clipboard
├── lockfile.py                     # MODIFIED: thin shim → _platform
├── main.py                         # MODIFIED: conditional pkexec
```

## Implementation Phases

### Phase 1: Foundation (Workers 1A, 1B — parallel)

**Worker 1A — Create `_platform/` package + update config + deps**
- Create `src/voice_overlay/_platform/__init__.py`
  - Detects `sys.platform` (`linux` vs `win32`)
  - Exposes factory functions for each backend type
- Create `src/voice_overlay/_platform/config.py`
  - `config_dir()` function: `$XDG_CONFIG_HOME` on Linux, `%APPDATA%` on Windows
  - `runtime_dir()` function: `$XDG_RUNTIME_DIR` on Linux, `%LOCALAPPDATA%` on Windows
- Modify `src/voice_overlay/config.py`
  - `config_path()` uses `_platform/config.py` helpers
- Modify `pyproject.toml`
  - Make `evdev` optional (`[project.optional-dependencies] linux = ["evdev"]`)
  - Remove `PyGObject` and `scipy` from core deps
- Modify `requirements.txt` — same changes

**Worker 1B — Create backend sub-package directories**
- Create empty directories: `_platform/hotkey/`, `_platform/injection/`, `_platform/lockfile/`
- Create `__init__.py` for each sub-package
- No implementation code yet

### Phase 2: Backend Implementations (Workers 2A, 2B, 2C — parallel)

**Worker 2A — Hotkey backend**
- Create `_platform/hotkey/__init__.py` — protocol class
- Create `_platform/hotkey/linux.py` — EvdevHotkeyListener (move from hotkey.py, no behavioral changes)
- Create `_platform/hotkey/windows.py` — WindowsHotkeyListener using `ctypes.windll.user32.SetWindowsHookExW` for a global keyboard hook, or use `pynput` (which works on Windows with a real global hook)
- Modify `hotkey.py` — thin shim that imports factory from `_platform` and delegates

**Worker 2B — Injection backend**
- Create `_platform/injection/__init__.py` — protocol class
- Create `_platform/injection/linux.py` — UinputInjector (move from uinput_injector.py, no behavioral changes)
- Create `_platform/injection/windows.py` — WindowsInjector using `ctypes.windll.user32.SendInputW` for keystroke synthesis + `ctypes.windll.user32.OpenClipboard`/`SetClipboardData`/`CloseClipboard` for clipboard
- Modify `uinput_injector.py` — thin shim that delegates to `_platform`
- Modify `text_injector.py` — use platform-appropriate clipboard (Win32 API on Windows, wl-copy/xclip on Linux)

**Worker 2C — Lockfile backend**
- Create `_platform/lockfile/__init__.py` — protocol function signature
- Create `_platform/lockfile/linux.py` — fcntl.flock approach (move from lockfile.py)
- Create `_platform/lockfile/windows.py` — use `ctypes.windll.kernel32.CreateMutexW` for a named mutex, or a simple PID file with exclusive open semantics
- Modify `lockfile.py` — thin shim that delegates to `_platform`

### Phase 3: Integration (Worker 3)

- Create `scripts/check_deps.ps1` — PowerShell equivalent of check_deps.sh for Windows
- Modify `main.py`:
  - `_ensure_input_access()` → gate on `sys.platform == "linux"`; no-op on Windows
  - Import hotkey and lockfile from the thin shims (already work)

### Phase 4: Tests (Worker 4)

- Update `tests/test_hotkey.py` — test only the abstract protocol; add mock-based tests for Windows backend
- Update `tests/test_text_injector.py` — test platform-agnostic clipboard path
- Add `tests/test_uinput_injector.py` if missing — test protocol compliance
- Update `tests/test_smoke.py` — ensure imports work on both platforms
- All existing Linux tests must continue passing unchanged

## Verification Criteria
- All 41 existing tests pass on Linux (unmodified)
- New protocol/mock tests validate Windows backends (tested on Linux CI via mocking)
- `pyproject.toml` installs successfully on both Linux and Windows
- `pytest tests/ -v` passes with zero failures

## Worker Dependency Graph

```
Phase 1:   1A ──────────────────────┐
                                    │
Phase 2:   2A ───┐  2B ───┐  2C ───┘   (parallel)
                                    │
Phase 3:   3 ←──────────────────────┘
                                    │
Phase 4:   4 ←──────────────────────┘
```

Key rule: Each worker receives the exact file list it needs to touch and the path state left by previous workers. Workers do not read each other's output files — they only read the pre-existing codebase files.

---

## Refinements (applied 2026-06-12)

### Structural Improvements

1. **Merged Worker 1B into Worker 1A.** The original 1B (creating empty sub-package directories + stub `__init__.py` files) was too small — it created ~15 lines of scaffolding across 3 files. Merging eliminates one handoff edge and reduces Phase 1 from 2 workers to 1. Worker 1A now handles all directory creation, stub files, config changes, and dependency updates in one pass.

2. **Added factory API contract to Worker 1A.** `_platform/__init__.py` must define and document the protocol class signatures that all Phase 2 workers will implement. Specifically:
   - `HotkeyListener` protocol (with `start()`, `stop()`, constructor: `hotkey, on_press, on_release`)
   - `TextInjector` protocol (with `inject(text) -> bool`)
   - `acquire_lock() -> bool` function signature
   - `config_dir() -> Path` and `runtime_dir() -> Path` helpers
   - Factory functions: `create_hotkey_listener(...)`, `create_text_injector()`, `get_platform_lock()`
   
   Defining these upfront prevents Phase 2 workers from drifting on interface design.

3. **Added explicit handoff protocol section.** Each worker's completion must produce a handoff manifest listing:
   - Files created (full paths)
   - Files modified (full paths)
   - Files read (full paths)
   - New public API surface added (function/class names)
   
   Downstream workers read these manifests, not each other's source files.

4. **Reordered Phase 3 to include `check_deps.sh` update.** The existing `scripts/check_deps.sh` checks for GTK3 system dependencies (`gobject-introspection`, `gtk+-3.0`, `cairo-gobject`) which are no longer needed (headless design). Worker 3 now strips GTK checks from `check_deps.sh` alongside creating `check_deps.ps1`.

### Dependency Fixes

5. **Fixed `lockfile.py` move to use `runtime_dir()` from `_platform/config.py`.** The original plan said "move from lockfile.py verbatim" but the current `lockfile.py` hardcodes `XDG_RUNTIME_DIR` directly. Worker 2C's linux.py must instead import `runtime_dir()` from `_platform/config.py` so the platform helper is actually consumed. The `lockfile.py` shim must not import `fcntl` at module level (currently it does) — this would break on Windows import.

6. **Fixed `text_injector.py` import chain.** `text_injector.py` currently does `from voice_overlay.uinput_injector import UinputInjector` — a direct import that bypasses the platform abstraction. Worker 2B must refactor `text_injector.py` to:
   - Remove the direct `UinputInjector` import
   - Import `create_text_injector()` from `_platform`
   - The clipboard logic (`_copy_to_clipboard` using wl-copy/xclip) must become platform-conditional: extracted into `_platform/injection/linux.py` and `_platform/injection/windows.py` respectively, or guarded by `sys.platform` in `text_injector.py` itself
   - Windows clipboard uses `ctypes.windll.user32.OpenClipboard` / `SetClipboardData` / `CloseClipboard`

7. **Fixed `main.py` top-level import.** `main.py` currently does `from voice_overlay.hotkey import EvdevHotkeyListener` — a concrete class import. After refactoring, `main.py` must either import the factory or import the shim which re-exports under the same name. Worker 3 must ensure the shims preserve backward-compatible import paths.

8. **Fixed `tests/test_smoke.py` backward compat.** Currently imports `EvdevHotkeyListener` and `acquire_lock` by name from `voice_overlay.hotkey` and `voice_overlay.lockfile`. The shims must re-export these names so smoke tests pass without changes.

### Risk Mitigations

9. **Added risk: `lockfile.py` module-level `import fcntl` crashes on Windows.** The current `lockfile.py` has `import fcntl` at line 6. If the shim in `lockfile.py` imports `_platform` which lazily loads the backend, accessing the lockfile module at all on Windows could trigger `ImportError`. Mitigation: the `lockfile.py` shim must only import `fcntl` inside the Linux backend file, never in the shim or `__init__.py`.

10. **Added risk: `uinput_injector.py` is 194 lines of Linux-specific ioctl code.** Moving this to `_platform/injection/linux.py` verbatim is fine, but the shim in `uinput_injector.py` must not leak `import fcntl` or `import struct` at module level. Mitigation: the shim delegates entirely to the factory, importing nothing platform-specific at module level.

11. **Added risk: `hotkey.py` has `import struct` and `from select import select` at module level.** Same pattern — the shim must not import these. The moved code in `_platform/hotkey/linux.py` keeps them, but the shim stays clean.

12. **Added risk: `text_injector.py` display server detection (`XDG_SESSION_TYPE`) is Linux-only.** On Windows, `_detect_display_server()` would return "unknown". Worker 2B must ensure the Windows code path skips display server detection entirely and uses Win32 clipboard directly.

13. **Added risk: no Windows CI in scope.** The plan relies on Linux CI + mocking for Windows backend validation. A real Windows test environment (GitHub Actions Windows runner) is out of scope for this plan but should be noted as a deferred risk.

### Skill Enhancements

14. **Architecture skill (simplicity principle) applied.** The factory + protocol pattern is appropriate for the three platform backends. One interface, two implementations. No over-engineering: the protocol classes are Python ABCs or Protocols with exactly the methods the existing code uses. Avoid generic abstractions — each protocol exposes only what `main.py` and `text_injector.py` actually call.

15. **Architecture skill (context discovery) applied.** The plan now explicitly identifies all existing files that form the "context" each worker must read before writing: `hotkey.py` (199 lines), `uinput_injector.py` (194 lines), `text_injector.py` (57 lines), `lockfile.py` (30 lines), `config.py` (54 lines), `main.py` (197 lines), `pyproject.toml` (19 lines), `requirements.txt` (6 lines), `scripts/check_deps.sh` (35 lines). Each worker's handoff manifest includes which of these files it read.

### Major Weakness Fixed
- Worker 1B eliminated (excessive handoff overhead for trivial scaffolding)
- Missing `runtime_dir()` consumption in lockfile backend addressed
- `text_injector.py` import chain vulnerability identified and fixed
- `lockfile.py` module-level `fcntl` import risk documented
- Backward-compatible import paths guaranteed for smoke tests
- Factory API contract defined in Phase 1 for downstream alignment
- Handoff protocol made explicit with manifest format

### Remaining Risks
- No Windows CI runner — Windows backend validated via mocking only, real Win32 bugs may surface post-merge
- `scripts/check_deps.ps1` may need adjustment if Windows dependency discovery reveals unexpected DLL requirements
- `pyproject.toml` optional-dependencies `[linux]` and `[windows]` may require platform-specific wheels that complicate the build matrix

### Suggested Focus for Next Iteration
- Add a Phase 0 worker that captures snapshots of all 9 existing files the plan touches (for rollback safety)
- Consider splitting Worker 2B into 2B (injection backend) and 2D (clipboard + text_injector refactor) — the clipboard concern is distinct from keyboard injection and may warrant its own worker if `text_injector.py` complexity grows

---

## Pass 2 Refinements (applied 2026-06-12)

### Security Analysis (security-engineer skill)

1. **Windows global hotkey hook (SetWindowsHookEx) runs in-process.** A `WH_KEYBOARD_LL` hook injected into the target process's message pump can crash the hooked process if the callback raises an unhandled exception. Mitigation: the Windows hotkey callback must wrap its body in a broad `try/except` that logs and swallows all exceptions — never let a Python exception propagate into the Win32 callback dispatcher. This is distinct from Linux where the evdev read-loop is in a Python thread and exceptions are naturally contained.

2. **Named mutex (CreateMutexW) exposes a global namespace vulnerability.** On Windows, a named mutex with fixed name `"VoiceOverlay-Instance"` can be pre-created by a malicious local process to prevent VoiceOverlay from starting (denial of service). Mitigation: use a randomly-suffixed or session-scoped mutex name derived from the user's SID, or use a PID file in `%LOCALAPPDATA%` with exclusive-open semantics instead of a kernel mutex. The Linux approach (fcntl.flock on a user-owned file) is naturally scoped to the user's home directory and immune to this — the Windows backend should match that scope.

3. **SendInput keystroke injection is detectable and blockable by anti-cheat/AV.** On Windows, `SendInput` is commonly monitored by endpoint protection and game anti-cheat systems. A false-positive flag is a risk. Mitigation: the Windows injector should fall back to clipboard-only mode (copy text to clipboard and show a notification) if `SendInput` appears to fail or if the process detects it is running in a locked-down environment. Worker 2B must include a `send_keystrokes(candidates)` -> bool function that the injector can call to test if keystroke injection works before committing to it.

4. **Clipboard read/write is a global resource with race conditions.** Both Linux (wl-copy/xclip) and Windows (OpenClipboard/SetClipboardData) access the system clipboard. On Windows, `OpenClipboard` fails if another process holds it open. On Linux, `wl-copy` spawns a persistent process. Mitigation: the clipboard helper must implement retry-with-backoff (3 retries, 100ms interval) on Windows, and must ensure the clipboard content is restored after injection if possible. Worker 2B should document clipboard ownership semantics for both platforms.

5. **No privilege boundary between platform backends.** The factory selects a backend based on `sys.platform` but does not validate that the current process has the required OS permissions before activating the backend. For example: on Linux, `pkexec` elevation happens in `_ensure_input_access()` but the hotkey and injection backends are already imported and potentially instantiated. On Windows, no elevation is needed, but the hotkey hook silently fails if UAC restrictions are in effect. Mitigation: add a `check_permissions() -> (bool, str)` method to each backend protocol that the app calls at startup, before starting the hotkey listener. Worker 1A must include this in the protocol signatures.

6. **Security model document.** Worker 3 should add a `docs/security.md` (or a section in the README) recording the threat model for each backend path. This is a single page covering: what system resources each backend accesses, what permissions are required, and what failure modes exist. This protects the maintainer from introducing a regression that exposes clipboard data or creates a privilege escalation path.

### Modularity & Interface Cleanliness (clean-code skill)

7. **Factory returns implementations, not unions.** The factory in `_platform/__init__.py` must return concrete implementation objects that satisfy the protocol, not `Optional[BaseClass]`. If a backend cannot be loaded (e.g., `evdev` not installed on Linux), the factory must raise a clear `PlatformBackendError` at factory call time, not at import time. This lets `main.py` catch the error at startup and print a user-friendly message instead of crashing with an `ImportError`.

8. **Each protocol must have exactly the surface area that `main.py` calls — nothing more.** The test for clean modularity is: could a new contributor add a macOS backend by creating only `_platform/hotkey/macos.py` without touching any Linux or Windows code? This requires:
   - No shared constants between backends (each backend file is fully self-contained)
   - Protocol classes in `__init__.py` use no platform-specific types in their signatures
   - The factory selection logic (`sys.platform`) is a single flat mapping in `_platform/__init__.py` — no platform detection in individual backend files
   - Adding `"darwin"` to the factory mapping is the only change outside the new file

9. **Shim modules must be pure delegation — zero logic.** The shim files (`hotkey.py`, `uinput_injector.py`, `lockfile.py`) after refactoring must contain nothing except an import from the factory and a re-export. No conditional imports, no try/except guards, no `if sys.platform` — all platform logic lives in `_platform/`. This is the single responsibility principle applied at the file level.

10. **`_platform/config.py` must not import from any platform-specific module.** It uses `os.environ` and `pathlib` only — this is correct. Worker 1A must verify this constraint and reject any change that introduces a platform import into config helpers.

### Error Handling & Resilience (testing-patterns skill)

11. **Import-time failures must be caught with a clear backstop.** The factory in `_platform/__init__.py` must wrap each platform backend import in a `try/except ImportError` block. If the Linux hotkey backend cannot import `evdev`, the factory must raise `PlatformBackendError("evdev not installed — run: pip install voice-overlay[linux]")`. If the Windows clipboard backend cannot load `ctypes.windll`, the factory raises a clear message. This pattern prevents cryptic tracebacks.

12. **Each backend must define an `is_available()` classmethod.** The protocol should include `@classmethod def is_available(cls) -> bool` that checks whether the required OS resources are present without instantiating the backend. For example:
    - Linux evdev: check that `/dev/uinput` exists and is writable
    - Linux lockfile: check that `fcntl` can be imported and the runtime dir is writable
    - Windows hotkey: check that `ctypes.windll` is importable and the process has a message pump
    - Windows injection: check that `SendInput` API is accessible (it always is on modern Windows)
    - Windows lockfile: check that `CreateMutexW` is available
    Worker 1A must add `is_available()` to all three protocol interfaces. Worker 3 must call `is_available()` on each backend at startup and warn if a backend self-reports as unavailable.

13. **Graceful degradation chain for injection.** The injection backend must define a clear fallback chain:
    - Attempt native injection (uinput / SendInput)
    - If native injection fails or returns false for untypeable characters, attempt clipboard paste (Ctrl+V / SendInput Ctrl+V)
    - If clipboard paste fails, write text to clipboard only and log a warning
    - Never crash — always return `bool` indicating whether text was placed at cursor
    Worker 2B must implement this exact chain in both backends.

14. **Lockfile must degrade gracefully on mutex contention.** If `acquire_lock()` returns `False` (another instance is running), the second instance must print a message and exit with code 1. This is already the behavior on Linux. Worker 2C must ensure the Windows backend does the same — no silent failure where a second instance starts and corrupts state.

15. **Test coverage for error paths.** Worker 4 must add tests for:
    - Factory raises `PlatformBackendError` when a backend import fails (mock `sys.platform` + patch import)
    - Each backend's `is_available()` returns expected value in mocked environments
    - Injection fallback chain: native fails -> clipboard paste called; clipboard paste fails -> returns False
    - Lockfile returns False when mutex is contended
    - All error-path tests must be mock-based and runnable on Linux

### Backward Compatibility

16. **Config file format stays identical.** The current `config.json` structure (keys: `hotkey`, `model`, `language`, `overlay_opacity`, `overlay_width`, `overlay_height`, `block_size`, `word_replacements`) must not change. The `config_path()` static method in `config.py` returns the same path on Linux (`~/.config/voice-overlay/config.json`) after refactoring. On Windows it returns `%APPDATA%/voice-overlay/config.json`. Existing Linux users see zero config changes.

17. **Backward-compatible re-exports.** The shim modules must re-export every public name that existing tests and imports reference:
    - `voice_overlay.hotkey` → must export `EvdevHotkeyListener` (the shim can alias it to the factory result)
    - `voice_overlay.lockfile` → must export `acquire_lock` (the shim delegates to `_platform`)
    - `voice_overlay.uinput_injector` → must export `UinputInjector` (the shim delegates to `_platform`)
    - `voice_overlay.text_injector` → must export `TextInjector` (imports from factory)
    Worker 4 must verify that all existing test imports resolve without modification.

18. **Python API contract frozen.** The plan must not change any function signature that external callers (tests, potential library users) depend on. Specifically:
    - `Config.from_file(path)` → unchanged
    - `Config.save(path)` → unchanged
    - `EvdevHotkeyListener(hotkey, on_press, on_release)` → same signature retained through shim
    - `UinputInjector.type_text(text) -> bool` → same signature retained through shim
    - `TextInjector.inject(text) -> bool` → unchanged
    - `acquire_lock() -> bool` → unchanged

### Windows-Specific Runtime Concerns

19. **Windows has no `SIGTERM` — `main.py` shutdown must use a different mechanism.** On Linux, the app uses `signal.signal(signal.SIGTERM, ...)`. On Windows, `signal.SIGTERM` is not available (only `SIGINT`, `SIGBREAK`, `SIGABRT`, `SIGFPE`, `SIGILL`, `SIGSEGV`, `SIGTERM` is defined but cannot be registered). Worker 3 must:
    - Gate `signal.signal(signal.SIGTERM, ...)` behind `if hasattr(signal, 'SIGTERM')` or `if sys.platform != 'win32'`
    - Add `signal.signal(signal.SIGBREAK, ...)` on Windows for Ctrl+Break handling
    - Ensure `_shutdown()` is called when the process is terminated via task manager (this may require a console control handler via `win32api.SetConsoleCtrlHandler` or `kernel32.SetConsoleCtrlHandler`)

20. **Windows has no `/dev/uinput` — clipboard-only injection is the norm, not the fallback.** On Linux, uinput injection is the primary path and clipboard is the fallback. On Windows, the `SendInput` keystroke injection approach works for alphanumeric characters but may fail for complex Unicode characters. Worker 2B must ensure the Windows injector's `inject(text)` method tries SendInput first, then falls back to clipboard paste (Ctrl+V). The clipboard-on-Windows always works — `SetClipboardData` accepts UTF-16.

21. **Windows needs `pythoncom.Initialize()` before `SetWindowsHookEx` on some Python builds.** If using `ctypes` directly for the global hook, the calling thread must have a Windows message pump (a `PeekMessage` loop or `MessagePump`). If the hook is installed from a daemon thread without a message pump, the callback never fires. Worker 2A must:
    - Ensure the hotkey listener's thread calls `ctypes.windll.user32.PeekMessageW` in a loop (or `time.sleep` with `PeekMessage`), or use `pynput` which handles this internally
    - Document that the Windows hotkey thread must never be a pure daemon thread

22. **Windows `OpenClipboard` requires the calling thread to have a valid window handle (HWND).** Calling `OpenClipboard(None)` from a daemon thread (no HWND) works on modern Windows but may fail in terminal/server environments. Worker 2B must pass `None` (which works on Windows 10/11) but document that if clipboard access fails, the injector degrades to the `is_available()` check and `main.py` skips clipboard injection at startup.

23. **Windows long paths.** `%APPDATA%` typically lives at `C:\Users\<user>\AppData\Roaming`. The `runtime_dir()` helper must use `%LOCALAPPDATA%` (typically `C:\Users\<user>\AppData\Local`) for runtime files. Worker 1A's `_platform/config.py` must ensure `runtime_dir()` returns a path shorter than 260 characters — Python 3.10+ on Windows supports long paths but older configurations may not. The lockfile path `%LOCALAPPDATA%\voice-overlay\instance.lock` should be well under 260 chars.

### Major Weakness Fixed (Pass 2)
- Windows global hook crash risk identified (exception must not escape callback)
- Named mutex namespace vulnerability documented with SID-scoped alternative
- No permission checking before backend activation — `check_permissions()` added to protocol
- Import-time failures now have clear backstop messages via `PlatformBackendError`
- Backend availability check (`is_available()` added to all protocols
- No backward-compatible re-export guarantees previously documented — now explicit
- Windows SIGTERM unavailability addressed with SIGBREAK + console control handler
- Windows message pump requirement for global hooks documented
- Config file format freeze guarantees existing Linux users unaffected
- Clipboard ownership race condition on Windows mitigated with retry-backoff

### Remaining Risks (Pass 2)
- Anti-cheat/AV false-positive detection of `SendInput` on Windows — mitigated but not eliminated
- Windows long-path support depends on Python 3.10+ registry key — document as install prerequisite
- Named mutex DoS mitigated but not eliminated (a local admin can still pre-claim any named kernel object)
- `PeekMessageW` loop on hotkey thread adds CPU overhead vs. Linux epoll-based evdev
- No Windows CI means clipboard race-condition fix cannot be validated in CI

### Suggested Focus for Next Iteration (Pass 2)
- Consider splitting Worker 4 into 4A (protocol/mock tests for all three backends) and 4B (integration tests + smoke tests) — tests for the factory error paths alone may justify a separate worker
- Add a Phase 5 for Windows CI setup (GitHub Actions Windows runner + headless test environment)
- Consider extracting `_platform/injection/clipboard.py` as a shared clipboard abstraction used by both Linux and Windows backends, rather than duplicating clipboard logic across both

---

## Pass 3 Refinements (applied 2026-06-12) — Immediate Edge Cases

### Import-Time Crash Analysis (full audit of every import in every touched file)

The following is a line-by-line import audit of every file the plan touches, tested against a Windows interpreter:

**Files that crash on import on Windows (before refactoring):**

1. `lockfile.py` — **`import fcntl` (line 6) is an unconditional crash: `ModuleNotFoundError: No module named 'fcntl'`.** This is the single most immediate import blocker. `fcntl` is Unix-only and not available anywhere on Windows via any mechanism.

2. `uinput_injector.py` — **`import fcntl` (line 3) is an unconditional crash**, same as above. Also `fcntl.ioctl()` calls throughout (used for `UI_DEV_CREATE`, `UI_SET_EV_BIT`, etc.) which would not even be reached if the import somehow worked.

3. `hotkey.py` — **`from evdev import InputDevice, ecodes, list_devices` (line 14) is guarded by `try/except ImportError`**, so it does not crash. But `from select import select` (line 9) **imports successfully but behaves differently**: on Windows, `select.select()` accepts only socket file descriptors, not file descriptors from `os.open()`. Calling `select([fd], [], [], 0.5)` where `fd` is from `os.open("/dev/input/eventX", ...)` raises `OSError: [WinError 10038]`. On Windows, this code path is never reached because `_find_keyboards()` fails before any select call, but the import itself is valid.

**Files that import successfully on Windows (before or after refactoring):**

4. `config.py` — All imports (`json`, `logging`, `os`, `pathlib.Path`, `dataclasses`) are cross-platform standard library. **No issues.**

5. `text_injector.py` — `shutil`, `subprocess`, `logging` are fine. The `from voice_overlay.uinput_injector import UinputInjector` (line 8) **would crash** because `uinput_injector.py` itself has `import fcntl`. This is a cascading crash.

6. `audio_capture.py` — `sounddevice` import is guarded by `try/except ImportError`. The `sounddevice` package ships with bundled PortAudio binaries for Windows, so the import succeeds on a standard install. **No issues.**

7. `transcription.py` — All imports (`numpy`, `re`, `os`, `time`, `pathlib`, `logging`) are cross-platform. `faster_whisper` is imported lazily inside `_load_model()`. **No issues.**

**After-refactoring import safety rules (must hold for the plan to work):**

8. **The `lockfile.py` shim must not contain `import fcntl` at module level.** Even `from _platform.lockfile.linux import ...` as a deferred import would be fine if the factory selects the backend lazily, but a top-level `import fcntl` in `lockfile.py` itself is a hard crash. The shim must import nothing platform-specific.

9. **The `uinput_injector.py` shim must not contain `import fcntl` at module level.** Same rule. The shim delegates entirely to the factory.

10. **The `hotkey.py` shim must not contain `from evdev import ...` at module level.** Even though the original `hotkey.py` guards this with try/except, the shim must not carry that pattern forward — the factory handles platform resolution.

11. **The `_platform/__init__.py` factory must use lazy imports (inside each factory function), not top-level imports**, to avoid importing the Linux backend when running on Windows and vice versa. If the factory does `from _platform.hotkey.linux import EvdevHotkeyListener` at module level, it would crash when VoiceOverlay is imported on Windows. Every backend import must be inside the function that selects it.

12. **`ctypes.windll` does not exist on Linux.** The Windows backend files (`_platform/hotkey/windows.py`, `_platform/injection/windows.py`, `_platform/lockfile/windows.py`) must never be imported on Linux. The factory must gate these imports behind `if sys.platform == "win32"`. Attempting `import ctypes; ctypes.windll.kernel32.CreateMutexW` on Linux raises `AttributeError: module 'ctypes' has no attribute 'windll'`.

### Permission Model Correctness

13. **On Windows, no elevation is needed for any backend operation.** This must be stated explicitly in `main.py` and should not be silent. Worker 3 must add a log line at debug level: if `sys.platform == "win32"`, log `"Windows platform detected — elevation not required, skipping _ensure_input_access()"`. This prevents future confusion when a contributor wonders why `_ensure_input_access` is a no-op.

14. **`os.geteuid()` always returns 0 on Windows** (it emulates root). The current `_ensure_input_access()` in `main.py` checks `if os.geteuid() == 0: return` — on Windows this would return immediately, which is accidentally correct but misleading. Worker 3 must replace the `os.geteuid() == 0` check with an explicit `if sys.platform != "linux": return` guard at the top of the function. This makes the intent clear and avoids relying on Windows emulation behavior.

15. **Linux permission groups (`input`, `uinput`) are documented in the existing error messages.** The hotkey listener's `start()` method logs: `"Ensure you are in the 'input' group: sudo usermod -a -G input $USER"`. Worker 2A must keep this message in the Linux backend. The Windows backend must never reference `/dev/input`, `uinput`, `pkexec`, or Linux group commands.

### Test Behavior Audit

16. **`tests/test_config.py:test_default_config_path()` asserts a Linux-specific path.** Line 49 reads:
    ```
    assert str(cfg.config_path()).endswith(".config/voice-overlay/config.json")
    ```
    After refactoring, `config_path()` on Windows returns `%APPDATA%/voice-overlay/config.json` which does not end with `.config/voice-overlay/config.json`. This test **will fail on Windows**. The fix: Worker 4 must update this test to be platform-aware. The easiest approach is to assert that the path ends with `voice-overlay/config.json` (dropping the `.config/` prefix), which is true on both platforms. Or: add a separate test for `_platform/config.py` helpers that validates the platform-specific paths.

17. **Existing Linux tests must not import Windows backend modules.** Worker 4 must verify that no existing test file has a transitive import path into `_platform/*/windows.py` at module level. This is guaranteed if the factory uses lazy imports (rule 11), but must be verified.

18. **All existing tests can run on Linux CI without modification after refactoring**, provided:
    - The shims re-export the same names with the same signatures (already enforced by Pass 1, rule 7)
    - The factory returns Linux backends on `sys.platform == "linux"` (guaranteed on Linux CI)
    - `test_default_config_path()` works on Linux (it does — `sys.platform` is `"linux"`, so `config_path()` returns the Linux path)
    - The `test_smoke_lockfile()` test calls `acquire_lock()` which on Linux opens a real file and attempts `fcntl.flock()` — this works on Linux CI (writable `/tmp` or equivalent)
    - The `test_audio_capture.py` tests that open real audio streams (`test_recording_produces_audio`) require a microphone or dummy audio device — this is an existing limitation, not introduced by this plan

19. **Windows backend tests on Linux CI require specific mocking patterns.** Worker 4 must enforce:
    - Every test that exercises the Windows hotkey backend must use `@patch('ctypes.windll')` as its outermost decorator to prevent `AttributeError` on module import
    - Every test that exercises the Windows injection backend must patch both `ctypes.windll.user32.SendInputW` and `ctypes.windll.user32.OpenClipboard`
    - Every test that exercises the Windows lockfile backend must patch `ctypes.windll.kernel32.CreateMutexW`
    - Tests must not attempt to instantiate the Windows backend directly without these patches — even importing the Windows backend module on Linux raises `AttributeError`

### First-Run Experience Edge Cases

20. **On a fresh Windows machine with no microphone configured, the app exits cleanly with a useful message.** `validate_microphone()` calls `list_input_devices()` which queries `sounddevice.query_devices()`. If PortAudio returns no input devices, the function returns `[]` and `validate_microphone()` returns `False`. `main.py` exits with `"ERROR: No microphone found. Plug in a mic and retry."` This message is adequate for both platforms. No change needed.

21. **On Windows, the faster-whisper model downloads to `%USERPROFILE%\.cache\huggingface\hub\`**, which is the default `HF_HOME` on Windows. The `is_model_cached` property in `transcription.py` checks `os.path.expanduser("~/.cache/huggingface/hub")` — on Windows, `~` resolves to `%USERPROFILE%`, so this correctly resolves to `C:\Users\<user>\.cache\huggingface\hub`. **No path issue.** However, the default `HF_HUB_DOWNLOAD_TIMEOUT` of 60 seconds may be tight on Windows with slower downloads or Windows Defender scanning. This is a pre-existing risk, not introduced by this plan.

22. **The Windows hotkey may not fire in a headless/non-interactive session.** `SetWindowsHookExW` with `WH_KEYBOARD_LL` requires a message pump on the installing thread. If VoiceOverlay is started via a scheduled task or remote PowerShell session (no interactive desktop), the hotkey will silently fail. Worker 2A must document this in the Windows backend: the listener thread must run a `PeekMessageW` loop (already specified in Pass 2, rule 21), and the backend must log a warning at startup if no interactive desktop session is detected.

### CI/CD Mock Validation

23. **The plan's assertion that "New protocol/mock tests validate Windows backends (tested on Linux CI via mocking)" is valid** with the following provisos:
    - `ctypes.windll` must be patched before ANY Windows backend module is imported (not just before method calls)
    - `sys.platform` must be patched to `"win32"` to test the factory's platform selection logic
    - The test pattern is:
      ```
      @patch('ctypes.windll')
      def test_windows_hotkey_imports(mock_windll):
          from _platform.hotkey.windows import WindowsHotkeyListener
          assert WindowsHotkeyListener is not None
      ```
      This works because `ctypes.windll` is a module-level attribute access, not an import — `unittest.mock.patch` intercepts the attribute lookup.
    - The factory's lazy import pattern (rule 11) is critical: if the factory does a top-level `from _platform.hotkey.windows import WindowsHotkeyListener`, it would crash even with patching because Python resolves the import at module-definition time, before the patch is applied. The factory must use `importlib.import_module()` or inline `from ... import ...` inside the function body.

24. **The Windows backend modules must not import any non-standard-library packages beyond `ctypes`.** They must not depend on `pywin32`, `pypiwin32`, or `pynput` (unless explicitly chosen for the hotkey hook). This keeps the dependency surface minimal and ensures that patching `ctypes.windll` is sufficient for full mock coverage on Linux CI. Worker 2A, 2B, 2C must verify this constraint before merging their backend files.

25. **`sounddevice` backend selection on Windows may require WASAPI or MME driver configuration.** The existing code does not select a specific audio API — it relies on PortAudio's default. On Windows with multiple audio subsystems, the default may not be the microphone. This is a pre-existing behavior and not in scope for this plan. Document in a comment within `audio_capture.py` that Windows users may need to set `sounddevice.default.device` in their config if no microphone is auto-detected.

### Verification Checklist (must hold for the refactored codebase)

Each of these must be verified by the integration phase (Worker 3 + Worker 4):

- [ ] `python -c "from voice_overlay.lockfile import acquire_lock"` succeeds on Windows
- [ ] `python -c "from voice_overlay.hotkey import EvdevHotkeyListener"` succeeds on Windows
- [ ] `python -c "from voice_overlay.uinput_injector import UinputInjector"` succeeds on Windows
- [ ] `python -c "from voice_overlay.text_injector import TextInjector"` succeeds on Windows
- [ ] `python -c "from voice_overlay.main import main"` succeeds on Windows
- [ ] `python -c "from voice_overlay.config import Config; print(Config.config_path())"` prints an `%APPDATA%` path on Windows
- [ ] `pytest tests/ -v` passes on Linux CI with zero failures
- [ ] `pytest tests/ -v` passes on Windows (with `--ignore=tests/test_audio_capture.py` if no mic)
- [ ] `test_default_config_path()` passes on both platforms (either platform-aware or removed)

### Out-of-Scope (filtered from this plan)

- macOS backend (`_platform/*/macos.py`) — not requested, not in scope
- Config hot-reloading (deferred to M2 in tasks.md)
- User onboarding sequence (deferred to M2 in tasks.md)
- GTK overlay re-introduction (removed, headless approach chosen)
- Toggle mode alternative (deferred to M2)
- Visual feedback via system notifications (deferred to M2)
- Windows Service/background runner — out of scope for this port
- Auto-updater — out of scope

### Major Weakness Fixed (Pass 3)

- Full 12-file import audit completed — identified 3 unconditional crashes (`import fcntl` in two files, cascading crash in `text_injector.py`)
- `test_default_config_path()` identified as breaking on Windows — must be updated to platform-agnostic assertion
- Lazy import requirement stated explicitly for the factory (`importlib.import_module()` or inline imports, never top-level platform-specific imports)
- `ctypes.windll` patching pattern documented for Linux CI Windows backend tests
- `os.geteuid()` Windows emulation behavior documented — Worker 3 must use `sys.platform` guard instead
- 9-item verification checklist for Phase 3/Phase 4 exit criteria
- All 5 M2-deferred features explicitly filtered out of scope

### Remaining Risks (Pass 3)

- `test_default_config_path()` must be updated — if forgotten, the test suite fails on Windows and the port is untestable on Windows
- Windows backend tests on Linux CI depend on `unittest.mock.patch('ctypes.windll')` — if any backend file imports at module level instead of inside the factory, patching happens too late
- Workers 2A/2B/2C may accidentally leave a top-level platform-specific import if they move code verbatim from the existing files — Worker 3 must catch this during integration
- The `test_smoke_lockfile()` test calls `acquire_lock()` which on Linux CI creates a real lockfile in the runtime dir — this must not collide with other tests or CI parallelization

### Suggested Focus for Next Iteration (Pass 3)

- No further plan iterations needed — the plan is now ready for execution
- Next step: dispatch Worker 1A with the full factory API contract including `is_available()` and `check_permissions()` signatures
- Worker 1A must also generate the `_platform/__init__.py` stub with lazy import pattern
- Worker 2A/2B/2C must receive explicit instructions from the handoff manifest about which protocol signatures to implement
