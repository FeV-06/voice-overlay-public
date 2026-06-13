from __future__ import annotations

import time
import numpy as np
from voice_overlay.audio_capture import AudioCapture


def test_audio_capture_default_parameters():
    cap = AudioCapture()
    assert cap.sample_rate == 16000
    assert cap.channels == 1
    assert cap.block_size == 16000


def test_audio_capture_custom_parameters():
    cap = AudioCapture(sample_rate=8000, block_size=8000)
    assert cap.sample_rate == 8000
    assert cap.block_size == 8000


def test_start_stop_cycles():
    cap = AudioCapture(block_size=4000)
    cap.start()
    assert cap.is_recording()
    cap.stop()
    assert not cap.is_recording()
    cap.start()
    assert cap.is_recording()
    cap.stop()


def test_recording_produces_audio():
    cap = AudioCapture(block_size=4000)
    cap.start()
    time.sleep(0.5)
    cap.stop()
    audio = cap.get_audio()
    assert isinstance(audio, np.ndarray)
    assert audio.dtype == np.float32
    assert len(audio) > 0
    assert audio.ndim == 1


def test_clear_resets_buffer():
    cap = AudioCapture(block_size=4000)
    cap.start()
    time.sleep(0.2)
    cap.stop()
    cap.clear()
    audio = cap.get_audio()
    assert len(audio) == 0


def test_buffer_clears_on_new_recording():
    cap = AudioCapture(block_size=4000)
    cap.start()
    time.sleep(0.5)
    cap.stop()
    first_len = len(cap.get_audio())
    assert first_len > 0
    cap.start()
    time.sleep(0.5)
    cap.stop()
    second_len = len(cap.get_audio())
    assert second_len > 0
