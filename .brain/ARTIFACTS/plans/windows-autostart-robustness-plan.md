# Windows Autostart Robustness — Implementation Plan

## Overview
Improve Windows autostart reliability by making `WindowsAutostart._command()` prefer the global `voice-overlay` command (from `uv tool install` / `pipx`) when available on PATH, falling back to the venv-based `sys.executable -m voice_overlay` command.

## Files to Modify
- `src/voice_overlay/_platform/autostart.py` — `WindowsAutostart._command()` logic
- `tests/test_autostart.py` — add `_command()` unit tests for both paths

## Task Breakdown

### Task 1: Update `_command()` in WindowsAutostart
- Add `import shutil` at top of file
- `_command()` checks `shutil.which("voice-overlay")` first
  - If found → return `"voice-overlay"`
  - If not found → return `f'"{sys.executable}" -m voice_overlay'` (existing behavior, already path-quoted)

### Task 2: Update tests
- Add `test_windows_autostart_command_prefers_global()` — mock `shutil.which` to return a path, verify `_command()` returns `"voice-overlay"`
- Add `test_windows_autostart_command_fallback()` — mock `shutil.which` to return `None`, verify `_command()` returns the venv-based path with quoting
- Existing `test_windows_autostart_stub` stays unchanged (tests `enable()` which fails on Linux due to `winreg`)

### Task 3: Run full test suite
- `uv run pytest -v` — confirm all tests pass

## Dependency Graph
- Task 1 → Task 2 → Task 3

## Verification Criteria
- `WindowsAutostart()._command()` returns `"voice-overlay"` when `shutil.which("voice-overlay")` finds it
- `WindowsAutostart()._command()` returns quoted venv path when `shutil.which` returns `None`
- All 72+ tests pass
- No new external dependencies introduced
- `shutil` is stdlib — no import fragility
- Existing registry entries (old format with full Python path) continue to work — no migration needed

---

## Refinements (Plan-Refiner Pass)

### Structural Improvements

- **Task 1 — clarify return value strategy.** `shutil.which("voice-overlay")` returns an *absolute path* (e.g. `C:\Users\X\.local\bin\voice-overlay.exe`), not a bare command. Storing the bare `"voice-overlay"` in the Run key relies on that directory being on `PATH` at Windows logon — which is not guaranteed for pipx/uv tool shims. The plan should store the **resolved full path** from `shutil.which` rather than the bare command name. If `shutil.which` returns a value, `_command()` returns that resolved path directly. Fallback behavior (venv path) is unchanged.
- **Task 1 — specify import placement.** `import shutil` belongs in the existing stdlib import block, inserted between `import os` and `import sys` (alphabetical order), consistent with file conventions.
- **Task 2 — test naming alignment.** The test `test_windows_autostart_command_prefers_global()` should be renamed to `test_windows_autostart_command_uses_shutil_which_path()` to reflect that the return value is a resolved path, not the bare string `"voice-overlay"`.

### Dependency Fixes

- **Task 2 → Task 1 dependency.** The mock in `test_windows_autostart_command_prefers_global()` must return a full path (e.g. `"C:\\Users\\X\\.local\\bin\\voice-overlay.exe"`) to accurately simulate `shutil.which` behavior. The plan's current description implies mocking `shutil.which` to return `True`/a truthy value — update to specify a realistic resolved path.
- **Task 3 — explicit isolation requirement.** Tests must mock `shutil.which` to be deterministic regardless of whether the developer has `voice-overlay` installed on their system. If the mock is missing, the test result depends on ambient environment — this is a flakiness vector.

### Skill Enhancements

- **Testing-patterns (AAA).** Test structure in Task 2 already follows AAA implicitly. No change needed, but the plan should note that the "global found" test's Arrange step must set up `shutil.which` to return a realistic absolute path — not a bare name and not just a truthy value.
- **Clean-code (SRP).** `_command()` still does one thing (return a command string) after the change. The two-branch logic (resolved path vs fallback) is a clean decision tree. No structural decomposition needed.

### Risk Mitigations

- **Risk: global command path not on `PATH` at Windows logon.** Partially mitigated by storing the resolved absolute path (not bare command). If the tool's bin directory is removed between install and login, the entry will fail — but this is identical risk to the current venv path being deleted. Acceptable.
- **Risk: existing autostart entries orphaned.** Old entries in the registry use the full `"C:\Python\...\python.exe" -m voice_overlay` path. These remain valid and continue to work. The plan should NOT attempt migration — the next autostart write (user toggles setting) will overwrite with the new format. Document that old entries are left in place and still functional.
- **Risk: cross-platform side effect.** `LinuxAutostart` already uses `Exec=voice-overlay` (bare command) in its desktop file. This change makes `WindowsAutostart` consistent: both platforms now prefer the global tool install. If a user has neither global install nor venv, both platforms will fail symmetrically. This is an improvement in cross-platform consistency, not a regression.
- **Risk: test suite may not run on Windows CI.** The existing autostart tests are platform-gated (`@pytest.mark.skipif(not sys.platform == "win32")`). New `_command()` tests are unit-level and do NOT depend on `winreg` — they can run on any platform. The plan should note that these tests should NOT be platform-gated, enabling them to run in Linux CI as well.

---

## Planner Feedback

- **Major Weakness Fixed:** No full-path return strategy — `shutil.which` returns an absolute path, not a bare command. Task 1 updated to store the resolved path.
- **Remaining Risks:** If the pipx/uv tool directory is deleted between install and Windows logon, autostart will fail. This is identical to existing risk with venv deletion — acceptable.
- **Suggested Focus for Next Iteration:** Consider adding a health check at app startup that validates the autostart registry entry still points to an existing executable, and auto-repairs it if not.

---

## Refinements (Plan-Refiner Pass 2)

### Architectural Improvements

- **Trade-off: resolved path vs bare command (formalized).** Two options for the `shutil.which` return value were evaluated. (A) Store the resolved absolute path: eliminates PATH dependency at boot time, survives environment differences between install and logon. (B) Store the bare command name: relies on PATH being identical at logon, which is fragile for pipx/uv tool shims. Decision: use resolved path (Option A). Rationale: lower boot-time failure surface, matches user expectation that a tool they installed globally will still be found after reboot.
- **Abstraction boundary: `_command()` is a template method hook.** The `PlatformAutostart` hierarchy already uses this pattern — `_command()` is the customization point that each subclass overrides. Adding the `shutil.which` check inside `WindowsAutostart._command()` respects this boundary. No need to pull the resolution logic into a shared helper or into the base class. However, note that `LinuxAutostart` hardcodes `Exec=voice-overlay` in its `DESKTOP_FILE_CONTENT` string and does NOT use `_command()` at all. This is a structural asymmetry: if Linux ever needs the same fallback behavior, it would require a separate refactor. Documented as out-of-scope for this change.
- **Single Responsibility: `WindowsAutostart` still owns one concern.** The class manages the Windows Registry Run key. `_command()` is a derived property of that concern. Adding `shutil.which` resolution does not violate SRP — the class is not gaining unrelated responsibilities.

### Deployment Reliability Improvements

- **Environment independence: PATH at logon differs from interactive PATH.** On Windows, the user's PATH environment variable is assembled from system-wide, user-level, and per-application entries. Tool shims installed by `pipx` or `uv tool install` typically live in `%USERPROFILE%\.local\bin` — this directory is added to PATH by the installer but may not be available in all contexts at boot time. Using the resolved absolute path (from Pass 1) eliminates this class of failure entirely.
- **Quoting for paths with spaces.** The resolved path from `shutil.which` may contain spaces (e.g. `C:\Users\My User\.local\bin\voice-overlay.exe`). The `_command()` return value must be quoted or escaped for the Windows registry REG_SZ value. Windows Run keys are parsed by `ShellExecuteEx`, which handles quoted paths correctly. The plan must ensure the resolved path is wrapped in quotes when returned, to match the existing fallback behavior `f'"{sys.executable}" -m voice_overlay'`.
- **Post-deployment verification strategy.** The change modifies what string is written to HKCU\Software\Microsoft\Windows\CurrentVersion\Run. Verification has two tiers: (A) unit-level — mock `shutil.which` and assert the output string format (covered by Task 2). (B) integration-level — the developer must manually verify on a Windows machine that the registry entry contains the correct resolved path after calling `enable()`. The plan should add a verification step: after implementing, run a Windows VM or CI job that calls `WindowsAutostart().enable()`, reads back the registry value, and confirms it matches the expected absolute path. This is not automatable in Linux CI but must be done at least once before merging.

### Testing Adequacy Improvements

- **Missing edge case: path with spaces.** Add a test case `test_windows_autostart_command_path_with_spaces()` that mocks `shutil.which` to return a path containing spaces (e.g. `C:\Users\Test User\.local\bin\voice-overlay.exe`), and verifies `_command()` returns a properly quoted string. The current test plan covers only a clean path scenario — the space case is a distinct failure mode.
- **Missing edge case: `shutil.which` returns path with forward slashes.** On Windows, `shutil.which` may return either forward or backslashes. The registry value should use backslashes. Add test case that mocks a forward-slash path and verifies the output uses backslashes (or passes through correctly for `ShellExecuteEx`). This is a low-probability issue but cheap to test.
- **Missing indirect coverage: `enable()` writes correct command.** The existing `test_windows_autostart_stub` tests `enable()` but skips on non-Windows platforms. Add a test that verifies `enable()` passes `_command()` to `winreg.SetValueEx` correctly, using a mocked registry. The mock should capture the value argument and assert it matches the expected command string. This ensures the `_command()` → `enable()` plumbing is tested without requiring actual registry access.
- **Testing isolation boundary.** All new `_command()` tests must be unit-level only — they import `WindowsAutostart` directly, mock `shutil.which` at the module level (`unittest.mock.patch("voice_overlay._platform.autostart.shutil.which", ...)`), and assert string output. They must NOT import `winreg` or touch the registry. This ensures they run on any platform in CI without decorators or skip marks.
- **Test count post-change.** The plan should cite the new expected test count. Current: "72+". After adding 4 new tests (resolved path, fallback, spaces, forward-slash) + 1 indirect `enable()` command capture test, expect 77+ passing tests.

### Risk Documentation

- **Risk: backward incompatibility for headless-to-GUI migration.** The existing `LinuxAutostart` desktop file uses `Exec=voice-overlay` (a bare command). If a Linux user has only installed via `pip install` (no `uv tool install`), `voice-overlay` won't be on PATH at GNOME autostart, and the .desktop file will silently fail — same failure mode that this Windows change mitigates. The plan should note that Linux has the same latent issue but it is out of scope. Cross-reference in a comment or future-task note.
- **Risk: `shutil.which` behavior differs on Windows vs Linux.** On Windows, `shutil.which` appends known executable extensions (`.exe`, `.bat`, `.cmd`) automatically. On Linux, it checks the `PATHEXT` equivalent via the executable bit. The resolved path on Windows will always include `.exe`. This is correct behavior — the registry Run key works with or without the extension — but the plan should note that the test mock must include the `.exe` suffix to be realistic. Mock value: `"C:\\Users\\Test\\.local\\bin\\voice-overlay.exe"`.

---

## Refinements (Plan-Refiner Pass 3 — Immediate Edge Cases)

### Execution-Phase Gotchas

- **Mock patch target must be the module-local reference, not the global.** Inside `autostart.py`, `import shutil` creates a local reference `voice_overlay._platform.autostart.shutil`. If tests patch `"shutil.which"` (global), the call inside `_command()` still resolves to the unpatched module-local `shutil.which`. The correct patch target is `"voice_overlay._platform.autostart.shutil.which"`. Any test that patches the wrong target will silently hit the real filesystem and become environment-dependent (fails when `voice-overlay` is installed, passes when it isn't — the exact flakiness the plan aims to avoid).

- **`shutil.which` can raise, not just return `None`.** On misconfigured systems — a directory in PATH with no read permission, a corrupted `PATHEXT` environment variable, or an interrupted system call — `shutil.which` can raise `OSError`. If `_command()` does not guard against this, the exception propagates through `enable()` and causes the entire autostart enable operation to fail. This is worse than the status quo (venv path always works). The `_command()` method must wrap the `shutil.which` call in a try/except `OSError` and fall through to the venv path on any exception, not just `None` return.

- **Plan inconsistency: original Task 1 wording is superseded by Pass 1 refinement.** Line 15 of the original plan reads `return "voice-overlay"`. Pass 1 (line 43) corrects this to "store the resolved full path from `shutil.which`". The implementer must follow the Pass 1 refinement, not the original line 15. The resolved path must be wrapped in quotes (to match the existing fallback quoting `f'"{sys.executable}" -m voice_overlay'`) so that paths with spaces are handled correctly by `ShellExecuteEx`.

### Test Structure Edge Cases

- **New `_command()` tests must be separate module-level functions, not grouped with `test_windows_autostart_stub`.** The existing `test_windows_autostart_stub` tests `enable()`, `disable()`, and `is_enabled()` — all of which stub out via `ImportError` and return `False`. The new tests test `_command()` directly, which should work on any platform without stubs. Mixing them into the same test function or adding them to a class that inherits platform assumptions would break the cross-platform CI guarantee. Each new test is standalone: `def test_windows_autostart_command_uses_shutil_which_path():`, `def test_windows_autostart_command_fallback():`, `def test_windows_autostart_command_path_with_spaces():`, etc.

- **All new tests must import `WindowsAutostart` only, not `winreg`.** The import block in the test file already imports `WindowsAutostart` directly (line 10). No additional imports needed. Each test creates `autostart = WindowsAutostart()`, patches `shutil.which` at the module level, calls `autostart._command()`, and asserts the string output. The tests must NOT import or reference `winreg` — that would break on non-Windows CI.

- **Existing `test_windows_autostart_stub` must NOT be modified.** It tests `enable()`/`disable()`/`is_enabled()` which all fail gracefully via `ImportError` on non-Windows. It will continue to pass unchanged. The implementer must not add `_command()` assertions to this test, as that would conflate the `_command()` unit test with the platform-gated stub test.
