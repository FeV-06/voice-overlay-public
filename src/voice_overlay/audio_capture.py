from __future__ import annotations

import logging
import threading
import time
import numpy as np

logger = logging.getLogger(__name__)

try:
    import sounddevice as _sd
except ImportError:
    _sd = None


class AudioDeviceError(Exception):
    pass


def list_input_devices() -> list[dict]:
    if _sd is None:
        return []
    devices = _sd.query_devices()
    return [
        {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


def validate_microphone() -> bool:
    devices = list_input_devices()
    if not devices:
        return False
    return True


class AudioCapture:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, block_size: int = 16000):
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self._stream = None
        self._recording = False
        self._buffer: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._device_error: str | None = None

    def _audio_callback(self, indata, frames, time_info, status):
        if self._recording:
            chunk = indata[:, 0].copy().astype(np.float32)
            with self._lock:
                self._buffer.append(chunk)

    def start(self) -> None:
        if _sd is None:
            raise RuntimeError("sounddevice not installed")
        logger.debug("Starting audio capture (rate=%d, block=%d)", self.sample_rate, self.block_size)
        with self._lock:
            self._buffer.clear()
            self._device_error = None
        self._recording = True
        try:
            self._stream = _sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                blocksize=self.block_size,
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.debug("Audio stream started")
        except OSError as e:
            self._device_error = f"Microphone unavailable: {e}"
            self._recording = False
            raise AudioDeviceError(str(e)) from e

    def stop(self) -> None:
        logger.debug("Stopping audio capture (buffer chunks: %d)", len(self._buffer))
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        time.sleep(0.05)

    def is_recording(self) -> bool:
        return self._recording

    def get_audio(self) -> np.ndarray:
        with self._lock:
            if not self._buffer:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(list(self._buffer))
            logger.debug("get_audio: %d chunks, %.2fs, %d samples", len(self._buffer), len(audio) / self.sample_rate, len(audio))
            return audio

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def iter_chunks(self):
        import time
        last_index = 0
        while self._recording or last_index < len(self._buffer):
            with self._lock:
                current_buf = list(self._buffer)
            if len(current_buf) > last_index:
                for chunk in current_buf[last_index:]:
                    yield chunk
                last_index = len(current_buf)
            else:
                time.sleep(0.05)
