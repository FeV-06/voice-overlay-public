from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


_SYMBOLS = {
    "forward slash": "/",
    "slash": "/",
    "backslash": "\\",
    "dot": ".",
    "period": ".",
    "colon": ":",
    "semicolon": ";",
    "comma": ",",
    "underscore": "_",
    "dash": "-",
    "hyphen": "-",
    "tilde": "~",
    "star": "*",
    "asterisk": "*",
    "plus": "+",
    "equals": "=",
    "pipe": "|",
    "ampersand": "&",
    "at sign": "@",
    "hash": "#",
    "percent": "%",
    "question mark": "?",
    "exclamation mark": "!",
    "open parenthesis": "(",
    "close parenthesis": ")",
    "open bracket": "[",
    "close bracket": "]",
    "open brace": "{",
    "close brace": "}",
}

_SYMBOL_PATTERN = re.compile(
    "|".join(
        rf"\b{re.escape(k)}\b" for k in sorted(_SYMBOLS, key=len, reverse=True)
    ),
    re.IGNORECASE,
)

_PATH_CHARS = set("/\\:@_~=+?#%")
_PROTOCOLS = {"http", "https", "ftp", "sftp", "file", "smb", "ws", "wss"}
_PATH_STOP = {
    "and", "or", "but", "for", "with", "from", "the",
    "is", "are", "was", "were", "has", "have", "had",
    "please", "thank", "thanks", "this", "that",
}


def _merge_spelled_words(text: str) -> str:
    tokens = text.split()
    result = []
    i = 0
    while i < len(tokens):
        if len(tokens[i]) == 1 and tokens[i].isalpha():
            run = [tokens[i]]
            j = i + 1
            while j < len(tokens) and len(tokens[j]) == 1 and tokens[j].isalpha():
                run.append(tokens[j])
                j += 1
            if len(run) > 2:
                result.append("".join(run))
                i = j
                continue
        result.append(tokens[i])
        i += 1
    return " ".join(result)


def _replace_spoken_punctuation(text: str, extra: dict[str, str] | None = None) -> tuple[str, bool]:
    original = text

    def _replace(m):
        return _SYMBOLS[m.group(0).lower()]

    text = _SYMBOL_PATTERN.sub(_replace, text)

    if extra:
        for word, replacement in extra.items():
            pattern = rf"\b{re.escape(word)}\b"
            text = re.sub(pattern, replacement, text)

    text = _merge_spelled_words(text)

    tokens = text.split()
    result = []
    in_path = False

    for token in tokens:
        has_path_char = any(ch in token for ch in _PATH_CHARS)
        starts_with_path = token and token[0] in "/.~\\@"
        is_stop = token.lower().strip(".,!?;:") in _PATH_STOP

        if has_path_char or starts_with_path:
            if in_path:
                result[-1] += token
            elif token.startswith(":") and result and result[-1].lower() in _PROTOCOLS:
                result[-1] += token
                in_path = True
            else:
                result.append(token)
                in_path = True
        elif is_stop:
            result.append(token)
            in_path = False
        elif in_path:
            result[-1] += token
        else:
            result.append(token)
            in_path = False

    result_text = " ".join(result)
    changed = result_text != original
    return result_text, changed


class TranscriptionError(Exception):
    pass


class TranscriptionEngine:
    def __init__(
        self,
        model_size: str = "tiny",
        language: str = "en",
        compute_type: str = "int8",
        device: str = "cpu",
        vad_filter: bool = True,
        context_max_chars: int = 200,
    ):
        self.model_size = model_size
        self.language = language
        self.compute_type = compute_type
        self.vad_filter = vad_filter
        self.device = device
        self.context_max_chars = context_max_chars
        self._model = None
        self._context_buffer: list[str] = []

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )

    def preload_or_verify(self) -> bool:
        try:
            os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
            start = time.monotonic()
            self._load_model()
            elapsed = time.monotonic() - start
            logger.info("Model '%s' loaded in %.1fs", self.model_size, elapsed)
            return True
        except (OSError, ConnectionError, RuntimeError) as e:
            logger.error("Model download failed: %s", e)
            return False

    def reset_context(self):
        self._context_buffer.clear()

    def _build_context_prompt(self) -> str | None:
        if not self._context_buffer:
            return None
        context = " ".join(self._context_buffer)
        if len(context) > self.context_max_chars:
            context = context[-self.context_max_chars:]
        return context

    def _update_context(self, text: str):
        if text.strip():
            self._context_buffer.append(text.strip())
            total = sum(len(t) for t in self._context_buffer)
            while self._context_buffer and total > self.context_max_chars * 3:
                old = self._context_buffer.pop(0)
                total -= len(old)

    @property
    def is_model_cached(self) -> bool:
        cache_dir = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface/hub"))
        model_dir = Path(cache_dir) / f"models--Systran--faster-whisper-{self.model_size}"
        return model_dir.exists() and any(model_dir.glob("snapshots/*/model.bin"))

    def _run_transcribe(self, audio: np.ndarray, initial_prompt: str | None = None) -> str:
        kwargs = {
            "language": self.language,
            "vad_filter": self.vad_filter,
            "beam_size": 1,
            "best_of": 1,
        }
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        segments, _ = self._model.transcribe(audio, **kwargs)
        return " ".join(segment.text.strip() for segment in segments)

    def transcribe(self, audio: np.ndarray, extra_replacements: dict[str, str] | None = None) -> str:
        if len(audio) == 0:
            return ""
        start = time.monotonic()
        self._load_model()

        context = self._build_context_prompt()
        if context:
            logger.debug("transcribe: using context prompt (%d chars)", len(context))

        text = self._run_transcribe(audio, initial_prompt=context)
        elapsed = time.monotonic() - start
        logger.debug("transcribe: %.2fs audio -> '%s' (%.2fs)", len(audio) / 16000, text, elapsed)

        text, changed = _replace_spoken_punctuation(text, extra_replacements)

        if changed:
            logger.debug("Spoken punctuation replaced: '%s'", text)

        self._update_context(text)
        return text

    def transcribe_with_segments(self, audio: np.ndarray) -> list[dict]:
        if len(audio) == 0:
            return []
        self._load_model()
        segments, _ = self._model.transcribe(
            audio,
            language=self.language,
            vad_filter=self.vad_filter,
            beam_size=1,
            best_of=1,
        )
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
            for seg in segments
        ]

    def transcribe_streaming(self, audio_chunk: np.ndarray, previous_context: str = "") -> str:
        if len(audio_chunk) == 0:
            return previous_context
        self._load_model()
        try:
            segments, _ = self._model.transcribe(
                audio_chunk,
                language=self.language,
                initial_prompt=previous_context[-100:] if previous_context else "",
                vad_filter=self.vad_filter,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=True,
            )
            text = " ".join(segment.text.strip() for segment in segments)
            return text if text else previous_context
        except Exception:
            return previous_context
