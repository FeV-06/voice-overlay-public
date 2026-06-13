# 2026-06-13 — Windows Autostart Robustness

## Change
- `WindowsAutostart._command()` now checks `shutil.which("voice-overlay")` first
- Falls back to `sys.executable -m voice_overlay` (quoted) when not found
- Added 4 new tests covering: PATH found, fallback, OSError recovery, path-with-spaces quoting
- `shutil.which` mock patched at module-local target to avoid CI flakiness

## Files
- `src/voice_overlay/_platform/autostart.py` — `_command()` logic
- `tests/test_autostart.py` — 4 new test functions

## Tests
- 76/76 pass (was 72)
