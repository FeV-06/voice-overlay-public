# VoiceOverlay

Real-time voice transcription overlay for Linux and Windows. Reads microphone input, transcribes via [faster-whisper](https://github.com/SYSTRAN/faster-whisper), injects text at the cursor — no browser, no cloud, no GUI required after first setup.

## Quick Install

### Linux

```bash
uv tool install "voice-overlay[linux]"
scripts/setup-linux.sh     # one-time permission setup
voice-overlay
```

### Windows

```powershell
uv tool install "voice-overlay[windows]"
scripts/setup-windows.ps1  # one-time dependency check
voice-overlay
```

On first run, a configuration window opens. Fill in your audio device and hotkey, click **Save & Start** — done.

## Linux Permissions

VoiceOverlay needs access to two device files to work without `sudo`:

| Device | Purpose | Group | Setup |
|---|---|---|---|
| `/dev/uinput` | Virtual keyboard — injects typed text at cursor | `uinput` | `sudo usermod -a -G uinput $USER` |
| `/dev/input/event*` | Global hotkey listener — capture hotkey even when window unfocused | `input` | `sudo usermod -a -G input $USER` |

A udev rule ensures `/dev/uinput` is group-writable:

```
KERNEL=="uinput", GROUP="uinput", MODE="0660"
```

### Automated setup

```bash
scripts/setup-linux.sh
```

This adds you to both groups, writes the udev rule, loads the `uinput` kernel module, and checks that the `evdev` Python package is installed. **Log out and back in** after it finishes.

### If the script doesn't work

If `pkexec` is installed, VoiceOverlay auto-relaunches through it when device access is missing — it will prompt for a password and work until the process ends. Config files saved under `pkexec` may be owned by root; this is handled gracefully (the app shows a warning and continues).

## Windows Requirements

VoiceOverlay uses standard Windows APIs — no special permissions or group membership are needed.

| Dependency | Why | How to get |
|---|---|---|
| Python 3.10+ | Runtime | [python.org](https://python.org) |
| Visual C++ Redistributable | faster-whisper native DLLs | [aka.ms/vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe) |

### Automated setup

```powershell
scripts/setup-windows.ps1
```

This checks Python/uv versions, installs `voice-overlay[windows]`, verifies the VC++ Redistributable, lists available microphones, and ensures the config directory exists.

## Configuration

All settings are stored in `~/.config/voice-overlay/config.json` (Linux) or `%APPDATA%\voice-overlay\config.json` (Windows):

- **Input device** — microphone to use
- **Model** — Whisper model size (tiny/base/small/medium/large)
- **Language** — source language (auto or specific)
- **Hotkey** — key combination to toggle recording (default: Ctrl+Shift+Space)
- **Auto-inject** — type at cursor (on) or copy to clipboard (off)
- **Compute** — device (CPU/GPU/Auto) and compute type (int8/float16 etc.)
- **VAD filter** — voice activity detection (filters silence)
- **Launch at login** — auto-start with desktop
- **Show config on startup** — skip the config window on next boot

## Scripts

| Script | Platform | Purpose |
|---|---|---|
| `scripts/setup-linux.sh` | Linux | Post-install permission setup (groups, udev, kernel module) |
| `scripts/setup-windows.ps1` | Windows | Post-install dependency check (VC++ redist, microphone, config dir) |
| `scripts/check_deps.sh` | Linux | Build-time dependency check (portaudio, Python version) |
| `scripts/check_deps.ps1` | Windows | Build-time dependency check |

## Development

```bash
git clone https://github.com/your-org/voice-overlay
cd voice-overlay
uv sync
uv run pytest
```

Tests: 77 tests across GUI, platform backends, config, transcription, and integration.

## License

MIT
