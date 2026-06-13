# Context: VoiceOverlay

## User Requirements (from brainstorming)
- Read microphone input
- Transcribe in real-time via faster-whisper
- Inject transcribed text wherever text cursor is present
- Linux Fedora device
- Push-to-talk activation (hold hotkey, release to inject)
- Floating overlay shows live transcription text and status
- English only, tiny model

## Architecture
Monolithic Python app with threaded components:
- GTK3 overlay window (always-on-top, borderless, semi-transparent)
- pynput global hotkey listener (default: Ctrl+Shift+V)
- sounddevice audio capture (16kHz, mono, float32)
- faster-whisper transcription engine (tiny model, int8, CPU)
- Text injector (ydotool/wtype for Wayland, xdotool for X11)

## Data Flow
1. Hotkey PRESS → start audio capture → show overlay
2. Audio chunk → faster-whisper → update overlay with interim text
3. Hotkey RELEASE → finalize transcription → inject text at cursor → hide overlay

## Plan Refinement Snapshot (2026-06-09)
- **Agent**: plan-refiner
- **Key Decisions**:
  - Added Task 0: System dependencies validation (GTK3, PortAudio OS packages)
  - Added Task 10: Incremental transcription wiring (AudioCapture.iter_chunks → TranscriptionEngine.transcribe_streaming → Overlay.update_interim_text → background thread in main)
  - Added AppState enum (IDLE → RECORDING → TRANSCRIBING → INJECTING) to prevent re-entrance bugs
  - All GTK calls from non-main threads must use GLib.idle_add (audited plan for violations)
  - Config bootstrap: save defaults on first run if config file missing
  - Added error display to overlay (red text, auto-dismiss) for mic/model failures
  - Added structured logging to all 7 modules
  - Fixed smoke test to be lightweight (imports only, no hardware)
  - TranscriptionEngine model download mocked in unit tests
  - Proper SIGINT/SIGTERM shutdown via GLib.idle_add
- **Remaining Risks**:
  - Wayland: pynput keyboard listener may require root/special permissions
  - ydotool requires ydotoold daemon running; fallback to wtype/clipboard with warning
  - Whisper model download (150MB) blocks first launch; overlay should show "Loading model..."
- **Notes for Next Agent**:
  - Implement tasks in order: Task 0 → Task 1 → Task 2 → ... → Task 10
  - Task 10 (incremental transcription) requires all modules complete first
  - Use clean-code, systematic-debugging, testing-patterns skills during implementation
