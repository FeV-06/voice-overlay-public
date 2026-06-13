# Execution History — 2026-06-09

## Phase 1: Initial Prototype with GTK Overlay
- Built full app with GTK3 floating overlay, pynput hotkey, ydotool/xdotool injection
- Model load spam bug fixed (GLib.idle_add returning True caused infinite loop)
- Overlay auto-hide removed, model download moved to background thread

## Phase 2: Hotkey Evolution (pynput → evdev)
- pynput failed on Wayland — only captured events within the launch terminal
- Switched to evdev (`/dev/input/event*`) for global hotkey detection
- Added primary-key tracking (release only fires on Space, not modifiers)
- Added 200ms hold gate to filter pynput/Wayland spurious release events
- Removed pynput dependency, added evdev dependency

## Phase 3: Text Injection Evolution (ydotool → uinput)
- ydotool/wtype/xdotool not installed on system
- Built uinput_injector.py — creates virtual keyboard at `/dev/uinput`
- Character-to-keystroke mapping with shift combos for symbols
- `fcntl.ioctl` fix (os.ioctl doesn't exist)
- `UI_DEV_SETUP` ioctl fix (replaced malformed `os.write` of uinput struct)

## Phase 4: Focus Battle
- GTK overlay stole keyboard focus → uinput typed into overlay, not target
- Tried: set_accept_focus(False), set_focus_on_map(False), NOTIFICATION, DOCK hints
- Tried: gtk-layer-shell (failed — GNOME Mutter rejects layer-shell from root session)
- Tried: Alt+Esc focus restore via uinput (doesn't work on GNOME Wayland)
- Tried: override-redirect window (still got focus on Mutter)
- **Solution**: Removed overlay entirely — headless app

## Phase 5: Audio Fix
- pkexec root session couldn't access PipeWire → invalid sample rate errors
- Root cause: when overlay was removed, XDG_RUNTIME_DIR was stripped from pkexec env vars
- Fix: restored all 9 env vars through pkexec (DISPLAY, WAYLAND_DISPLAY, XDG_RUNTIME_DIR, XDG_SESSION_TYPE, DBUS_SESSION_BUS_ADDRESS, HOME, XAUTHORITY, PATH, VIRTUAL_ENV)

## Phase 6: Model Upgrade
- Default model upgraded from tiny (~75MB) to small (~466MB) for accuracy

## Files Created
```
src/voice_overlay/__init__.py
src/voice_overlay/main.py              # Headless app entry point
src/voice_overlay/config.py            # Config dataclass + JSON persistence
src/voice_overlay/audio_capture.py     # sounddevice mic capture
src/voice_overlay/transcription.py     # faster-whisper wrapper
src/voice_overlay/hotkey.py            # evdev global key listener
src/voice_overlay/text_injector.py     # Injection orchestrator
src/voice_overlay/uinput_injector.py   # /dev/uinput virtual keyboard
src/voice_overlay/lockfile.py          # PID singleton lock
scripts/check_deps.sh
pyproject.toml
requirements.txt
.gitignore
tests/test_config.py
tests/test_audio_capture.py
tests/test_transcription.py
tests/test_hotkey.py
tests/test_text_injector.py
tests/test_smoke.py
```

## Files Removed
```
src/voice_overlay/overlay_ui.py        # GTK overlay (removed — focus issues)
tests/test_overlay_ui.py               # Overlay tests (removed)
```

## Test Status
- 29 tests passed, 0 failures

## Key Lessons
1. pynput cannot do global hotkeys on Wayland — use evdev
2. ydotool/wtype are rarely installed — uinput is universal
3. GTK windows always steal focus on Mutter Wayland — go headless
4. pkexec strips env vars — pass them explicitly, especially XDG_RUNTIME_DIR for PipeWire
5. os.ioctl doesn't exist — use fcntl.ioctl
6. uinput requires UI_DEV_SETUP ioctl, not raw struct write
