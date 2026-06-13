# Config GUI & System Tray — Implementation Plan

## Overview
Add a PySide6 configuration window that appears on startup and a system tray icon for background operation. Users can customize transcription, audio, hotkey, and behavior settings through the window. Settings persist to `config.json`.

## Phase
M4 — Config GUI & System Tray

> **Note:** PROJECT.md currently reports M3. Must be updated to M4 when work begins.

## Dependencies
- Design spec: `docs/superpowers/specs/2026-06-13-config-gui-design.md`
- Existing: `config.py` (Config dataclass, `config_path()` static method, `_platform/config.py`), `main.py` (boot flow), `audio_capture.py` (incl. `list_input_devices()`)

---

## File Structure
```
src/voice_overlay/
  gui/                          ← NEW package
    __init__.py                 ← public API exports
    theme.py                    ← QSS stylesheet
    settings_widgets.py         ← HotkeyRecorder, ComputeSelector
    config_window.py            ← QMainWindow settings form
    system_tray.py              ← QSystemTrayIcon + context menu
    mic-icon.svg                ← tray icon resource
  _platform/
    autostart.py                ← NEW: PlatformAutostart interface
  main.py                       ← modified boot flow
  config.py                     ← extended fields
```

---

## Modularity & Boundaries

The GUI package must never import engine modules (transcription, audio_capture internals, text_injector). The only allowed imports from outside `gui/` are:
- `voice_overlay.config` — read/write settings
- `voice_overlay.audio_capture.list_input_devices` — populate device dropdown (utility, not engine)
- Qt bindings (PySide6)

The `ConfigWindow.saved(settings: dict)` signal is the sole communication channel from GUI → main. Main.py owns the engine lifecycle and responds to the signal. This boundary means:
- The GUI can be tested in isolation with a mock config file and no microphone or model
- The engine module can be swapped without touching any widget code

---

## Error Handling & Graceful Degradation

| Failure Mode | Behavior |
|---|---|
| PySide6 not installed and `show_config_window=True` | Log warning, fall back to headless mode, continue as today |
| PySide6 not installed and `show_config_window=False` | No change — app runs headlessly as before (no import error) |
| `config.json` corrupted (invalid JSON) | Catch `json.JSONDecodeError` in `from_file()`, log warning, return default Config |
| No audio input devices found | QComboBox shows only "Auto" option; app startup proceeds (mic check already exists at boot) |
| Model preload fails (no network, no GPU) | Preload error is logged; GUI still shows; user can retry with different settings. Previous behavior (fatal exit) is replaced — preload failure is non-fatal in the new flow |
| Model reload fails after Save (e.g. CUDA missing) | Catch error, revert to previous working model, do NOT save failing settings, show tray notification |
| Second instance launched | Lockfile guard checked before any GUI construction — exit immediately, no window flash |
| Save with invalid values (e.g., unknown model name) | ConfigWindow validates before emitting `saved` signal; show inline error label |
| Tray unavailable (Linux/Wayland without libappindicator) | Log warning. ConfigWindow close event closes+quits instead of hiding to tray. "Minimize to Tray" button hidden. Engine never starts if window is the only interaction path |

---

## Task Breakdown

### Task 1: Extend Config dataclass
**File:** `src/voice_overlay/config.py`
- Add new fields: `input_device`, `compute_type`, `device`, `vad_filter`, `auto_inject`, `launch_at_login`, `show_config_window`
- Extend `to_dict()` to include all new fields (currently only serializes old fields)
- Validate that new fields have sensible defaults matching the design spec
- Ensure `save()` and `load()` handle new fields without breaking existing configs
- `Config.config_path()` and `_platform/config.py` already handle cross-platform path resolution — no new method needed
- `from_file()` already strips unknown keys via `valid_fields` filter — verify backward compat path works
- Wrap `json.load()` in `from_file()` in try/except for `JSONDecodeError` → log warning + return defaults

### Task 2: Add PySide6 dependency
**File:** `pyproject.toml`
- Add `pyside6 >= 6.5` to core dependencies
- This must happen before any GUI code is written so CI can resolve imports
- All PySide6 imports must be deferred (imported inside functions, not at module top level) in `main.py` so the app can still start headlessly when PySide6 is absent

### Task 3: Create tray icon resource
**File:** `src/voice_overlay/gui/mic-icon.svg`
- Simple microphone waveform SVG — single color, small (~32×32)
- Dark theme compatible (light/transparent background)
- Referenced by SystemTray icon

### Task 4: Create GUI package skeleton
**Files:** `src/voice_overlay/gui/__init__.py`, `src/voice_overlay/gui/theme.py`
- `__init__.py` — exports public API
- `theme.py` — QSS stylesheet string with dark-ish theme (professional developer tool aesthetic)
  - Colors: neutral backgrounds, high-contrast text, single accent color for CTAs
  - Styles for: QMainWindow, QComboBox, QPushButton, QCheckBox, QGroupBox, QLineEdit

### Task 5: Build settings widgets
**File:** `src/voice_overlay/gui/settings_widgets.py`

- `HotkeyRecorder` — QWidget that displays current hotkey, captures key combo on click
  - Click → enter listening mode → press combo → display new binding
  - Emits signal `hotkey_changed(str)` on completion
  - Edge case: Esc key during listening mode → cancel, restore previous binding
  - **Known limitation:** system-level hotkey conflicts cannot be detected from inside the app (OS consumes the key before Qt sees it). The recorder accepts any valid key combo. The implementation should reject obviously invalid bindings (single modifier keys, no key besides modifiers) but cannot detect reserved system combos
- `ComputeSelector` — QWidget with two linked QComboBoxes (Device + Compute Type)
  - When Device changes, filter Compute Type options:
    - "CPU" → show only int8, float32
    - "GPU" → show only float16, bfloat16, int8_float16, int8_bfloat16
    - "Auto" → show all
  - Emits signal `compute_changed(device: str, compute_type: str)`

### Task 6: Build ConfigWindow
**File:** `src/voice_overlay/gui/config_window.py`

- `ConfigWindow(QMainWindow)` — the main settings form
  - Fixed size ~540×580, centered on screen
  - Sections: Audio, Transcription, Hotkey, Output, Behavior, Advanced (collapsible)
  - Audio section: QComboBox populated from `list_input_devices()` (callable on init), plus "Auto" default
  - Transcription section: two QComboBoxes side by side — Model (tiny/base/small/medium/large-v3/distil-large-v3) and Language (en/de/fr/es etc.)
  - Hotkey section: HotkeyRecorder widget
  - Output section: QCheckBox for auto-inject
  - Behavior section: QCheckBox for launch at login (UI only — platform integration deferred)
  - Advanced section: QGroupBox collapsed by default containing:
    - "Don't show on startup" QCheckBox
    - VAD filter QCheckBox
    - ComputeSelector widget
    - Audio block size QComboBox (512/1024/2048/4096)
    - Label for custom word replacements (beta, not implemented)
  - Footer: "Minimize to Tray" QPushButton + "Save & Start" QPushButton (primary CTA)
    - If tray is unavailable, hide the "Minimize to Tray" button entirely and label the close action as "Exit"
  - Reads current config on init, writes on save
  - Emits signal `saved(settings: dict)` — includes `model_changed: bool` flag
  - **Close event behavior (critical):**
    - If tray is available: hide window to tray (do NOT close, do NOT start engine yet — engine start is gated on preload completion in boot flow)
    - If tray is unavailable: actually close + quit the app (no tray to hide to, so hiding would trap the user)
  - Validate save values before emitting signal (known model names, block_size power-of-two, hotkey non-empty) — show error label on failure

- **Optional: declarative settings structure (non-blocking)**
  - A data-driven form builder would reduce future maintenance but is not required for this phase. If time allows, define a settings descriptor list and iterate over it. If not, hardcode the layout — it can be refactored later.

### Task 7: Build SystemTray
**File:** `src/voice_overlay/gui/system_tray.py`

- `SystemTray(QSystemTrayIcon)` — tray icon + context menu
  - Context menu: "Show Window", "Pause/Resume" (placeholder — **disabled/grayed out** with tooltip "Coming soon", NOT clickable-but-no-op), separator, "Quit"
  - Single-click tray icon → toggle window visibility
  - App icon: load `mic-icon.svg`
  - On "Quit" → actually exit the app (QApplication.quit())
  - **Tray availability check:**
    - Call `QSystemTrayIcon.isSystemTrayAvailable()` during construction
    - If unavailable: log warning. The SystemTray object is still created but never shown. ConfigWindow is notified at construction time so it can adjust close behavior (close+quit instead of hide-to-tray)
  - If the tray icon is available but disappears at runtime (D-Bus restart, `snapd` issue), the Qt tray icon goes silent. Handle `QSystemTrayIcon.MessageClicked` and context menu activation gracefully — a destroyed tray should not crash the app

### Task 8: Define PlatformAutostart interface
**File:** `src/voice_overlay/_platform/autostart.py` (NEW)
- Interface with three operations: `enable()`, `disable()`, `is_enabled()`
- **Linux backend:** write/remove `~/.config/autostart/voice-overlay.desktop` with `X-GNOME-Autostart-enabled=true`
- **Windows backend:** stub returning `False` — deferred to later phase
- **Fallback (unsupported platform):** stub that logs a warning and is a no-op
- Imported by main.py, wired to the `launch_at_login` config value

### Task 9: Modify main.py boot flow
**File:** `src/voice_overlay/main.py`

- New boot sequence:
  1. Validate environment + acquire lockfile (before any GUI work — no window flash)
  2. Load config — handle corrupted JSON with fallback to defaults
  3. Lazy-import PySide6. If unavailable and `show_config_window=True`, log warning and set `show_config_window=False`. If unavailable and `show_config_window=False`, run old headless flow unchanged
  4. Create QApplication (use `QApplication.instance()` for idempotency)
  5. Start cancellable background model preload (CPU/int8 defaults in daemon thread)
     - Preload failure is NON-FATAL — log error, let the GUI show. User can change settings and retry via Save
     - Preload must be cancellable: the thread checks a `threading.Event` periodically; if the user saves with different model settings, the event is set and a new preload starts
  6. If `show_config_window` → create & show ConfigWindow. Check tray availability and pass it to ConfigWindow for close-behavior decisions
  7. On "Save & Start": validate → save config → cancel current preload if running → if model changed, reload WhisperModel with new settings → if reload fails (e.g. CUDA missing), catch error, revert to previous working model, do NOT save failing settings, notify via tray / log → wire PlatformAutostart → start engine (including hotkey listener) → hide window to tray
  8. On "Minimize to Tray" (or X close, tray available): do NOT save config. Start engine ONLY after model preload completes (do not block the UI — the engine starts asynchronously once the preload thread finishes). Hide window to tray
  9. On X close (tray unavailable): close+quit the app
  10. On subsequent boot with `show_config_window=False` → skip window, go straight to tray (but cancel preload and reload if config-saved model differs from defaults)
  11. Connect ConfigWindow.saved signal to model reload + preload-cancel + engine-start logic
  12. On quit from tray → cancel preload → shut down engine → destroy QApplication → exit
  13. **Signal handling:** QApplication's event loop handles SIGINT internally on all platforms. Remove the old manual `signal.signal(signal.SIGINT, ...)` setup — it conflicts with Qt's event loop. On Windows, Ctrl+C is handled by the event loop natively

- **Hotkey listener lifecycle:** The hotkey listener must NOT start until the config window is dismissed (Save & Start / Minimize to Tray / X close). If it started earlier, the user could trigger recording while configuring settings, which is nonsensical. The hotkey listener starts as part of "start engine" in steps 7 and 8
- QApplication event loop replaces the current `_shutdown_event.wait()` blocking pattern
- All PySide6 imports in main.py are deferred (inside functions, not at module level) to support headless fallback

### Task 10: Tests
**Files:** `tests/test_config.py` (update), `tests/test_gui.py` (new)

- Test new Config fields serialization/deserialization
- Test Config backward compatibility (loading old configs with missing new fields → defaults applied)
- Test `to_dict()` includes all new fields
- Test corrupted config.json falls back to defaults (JSONDecodeError path)
- Test hotkey recorder signal emission and Esc-cancel behavior
- Test hotkey recorder rejects purely-modifier combos
- Test compute selector filtering behavior
- Test that model reload flag is correctly computed
- Test GUI does not import engine modules (enforce boundary — import check or linter rule)
- Test headless fallback when PySide6 unavailable (mock import error)
- Test PlatformAutostart interface stubs return correct values
- Test that ConfigWindow close event adapts to tray availability (hide vs quit)

---

## Dependency Graph
```
Task 1 (Config ext) ──> Task 6 (ConfigWindow), Task 8 (Autostart), Task 10 (Tests)
Task 1 ──> Task 9 (main.py), Task 5 (Widgets)
Task 2 (PySide6 dep) ──> Task 4 (Skeleton), Task 5 (Widgets), Task 6 (ConfigWindow), Task 7 (Tray)
Task 3 (Icon) ──> Task 7 (Tray)
Task 4 (Skeleton) ──> Task 6 (ConfigWindow), Task 7 (Tray)
Task 5 (Widgets) ──> Task 6 (ConfigWindow)
Task 6 (ConfigWindow) ──> Task 9 (main.py)
Task 7 (Tray) ──> Task 9 (main.py)
Task 8 (Autostart) ──> Task 9 (main.py)
Task 10 (Tests) ──> Task 1, Task 5, Task 6, Task 8
```

**Recommended implementation order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

---

## Immediate Edge Cases (M4 Scope)

### 1. User closes window immediately without clicking Save or Minimize
X close (tray available) → window hides to tray. Engine starts asynchronously once the background model preload finishes. The user never explicitly started, but the app becomes operational in the background. This is intentional: the window is a configuration surface, not a launcher. If tray is unavailable, X close exits the app.

### 2. User tries to record while the config window is open
The hotkey listener is NOT started until the config window is dismissed (Save & Start / Minimize to Tray / X close). The user cannot accidentally trigger recording while in the settings screen. This is enforced by the boot flow ordering in Task 9.

### 3. Tray icon creation fails (Linux/Wayland)
`QSystemTrayIcon.isSystemTrayAvailable()` is checked at construction time. If false:
- ConfigWindow hides the "Minimize to Tray" button
- X close event closes+quits instead of hiding to tray
- The app operates in windowed mode only

### 4. Hotkey rebind conflicts with existing system hotkey
System-level hotkey conflicts cannot be detected from inside the application (the OS intercepts them before Qt sees the key event). The HotkeyRecorder accepts any valid combo and displays it. It should reject obviously invalid entries (e.g., lone modifier keys), but system conflict detection is not possible without platform-specific hooks, which are out of scope for M4.

### 5. User switches from CPU to GPU but CUDA isn't installed
The model reload in boot flow step 7 will fail. The error is caught, the previous model is kept, failing settings are NOT persisted to config.json, and a notification is shown via the tray (or logged if tray unavailable). The ConfigWindow remains open and shows the error.

### 6. Pause/Resume is a placeholder
The menu item is disabled/grayed out with a tooltip "Coming soon" — it is NOT clickable-but-no-op. This avoids user frustration and makes the unimplemented state explicit.

### 7. Model download fails during preload
Preload failure is non-fatal. The error is logged, the GUI still shows, and the user can change model settings and retry via Save & Start. This replaces the old behavior which called `sys.exit()` on preload failure.

### 8. Cross-platform signal handling
The QApplication event loop handles SIGINT internally on all platforms including Windows. The old manual `signal.signal(signal.SIGINT, ...)` setup is removed — it conflicts with Qt's event loop. This simplifies the signal path and eliminates a cross-platform divergence.

---

## Key Design Decisions / Trade-offs

- **Model preload is cancellable.** The daemon thread checks a `threading.Event`; saving new model settings cancels the stale preload mid-flight. Avoids wasteful double-load.
- **Hotkey listener deferred until after window dismiss.** Prevents recording during configuration — a UX requirement, not just an optimization.
- **Engine start on X close is async (gated on preload).** The UI never blocks. If the user closes the window immediately, the engine starts silently once preload finishes.
- **Tray availability changes ConfigWindow behavior.** No tray → no minimize button → X close exits. This prevents the user from being trapped with a hidden window and no way to show it.
- **Model reload failure reverts silently.** CUDA-not-installed is the most common case. The app falls back to the previous working model rather than crashing or leaving the user with a non-functional engine.
- **Deferred PySide6 imports** in main.py keep the app runnable headlessly. Users who don't need the GUI never pay the import cost.
- **Save-time validation** prevents corrupt config from reaching disk. Validation is in ConfigWindow, not Config, because validation rules are UI concerns (known value lists, display labels). Config is a passive data bag.
- **GUI never imports engine.** This is enforced by convention and checked in tests.

---

## Verification Criteria
- [ ] `config.json` correctly persists all new fields (read → modify → save → read → verify)
- [ ] Loading an old config file (missing new fields) falls back to defaults without error
- [ ] Corrupted config.json (invalid JSON) falls back to defaults with a logged warning
- [ ] `to_dict()` output includes all new fields
- [ ] ConfigWindow shows on startup, hides to tray on close (tray available) — engine starts async after preload
- [ ] ConfigWindow close exits the app (tray unavailable) — no hidden-but-inaccessible window
- [ ] "Minimize to Tray" button hidden when tray unavailable
- [ ] "Minimize to Tray" button hides window without saving config (tray available)
- [ ] "Save & Start" saves config, starts engine, hides to tray
- [ ] "Save & Start" with invalid values (unknown model, bad block_size) shows error, does not save
- [ ] "Don't show on startup" checkbox causes window to be skipped on next boot
- [ ] HotkeyRecorder captures key combos correctly and emits signal; Esc cancels
- [ ] HotkeyRecorder rejects lone modifier keys as invalid binds
- [ ] ComputeSelector filters compute types when device changes (CPU/GPU/Auto)
- [ ] Audio device QComboBox populated from system devices (not empty, not hardcoded)
- [ ] Model reloads when model/device/compute_type changes; stale preload is cancelled
- [ ] Model is NOT reloaded when unrelated settings change
- [ ] Model preload failure is non-fatal (GUI still shows, no crash)
- [ ] Model reload failure (CUDA missing) falls back to previous settings, does not save
- [ ] Hotkey listener does NOT start while ConfigWindow is open
- [ ] System tray shows icon with working context menu (Show Window, Pause/Resume placeholder disabled, Quit)
- [ ] Single-click tray icon toggles window visibility
- [ ] Quit from tray actually exits the process
- [ ] Pause/Resume menu item is disabled with tooltip "Coming soon" (not clickable-but-no-op)
- [ ] Config path resolution works cross-platform (Linux ~/.config, Windows %APPDATA%)
- [ ] Headless mode works when PySide6 is missing (deferred imports, no crash)
- [ ] Lockfile guard runs before any GUI construction (no window flash on second instance)
- [ ] PlatformAutostart interface exists with Linux/.desktop backend; Windows stub returns False
- [ ] GUI package does not import `transcription`, `text_injector`, or engine-internal modules
- [ ] Old manual `signal.signal(signal.SIGINT)` removed — QApplication event loop handles it
- [ ] All existing tests continue to pass
