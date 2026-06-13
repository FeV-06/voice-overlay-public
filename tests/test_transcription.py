from __future__ import annotations

import numpy as np
from unittest.mock import patch, MagicMock
from voice_overlay.transcription import TranscriptionEngine


def test_engine_init_defaults():
    engine = TranscriptionEngine()
    assert engine.model_size == "tiny"
    assert engine.language == "en"
    assert engine.compute_type == "int8"


def test_transcribe_empty_audio_returns_empty():
    engine = TranscriptionEngine(model_size="tiny")
    audio = np.array([], dtype=np.float32)
    text = engine.transcribe(audio)
    assert text.strip() == ""


def test_transcribe_silence():
    engine = TranscriptionEngine(model_size="tiny")
    audio = np.zeros(16000, dtype=np.float32)

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], None)
    engine._model = mock_model

    text = engine.transcribe(audio)
    assert isinstance(text, str)
    assert text.strip() == ""


def test_transcribe_returns_segments():
    engine = TranscriptionEngine(model_size="tiny")
    audio = np.zeros(16000 * 3, dtype=np.float32)

    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 1.0
    mock_segment.text = "hello world"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], None)
    engine._model = mock_model

    segments = engine.transcribe_with_segments(audio)
    assert isinstance(segments, list)
    assert len(segments) == 1
    assert segments[0]["text"] == "hello world"


def test_vad_filter_enabled_by_default():
    engine = TranscriptionEngine()
    assert engine.vad_filter is True


def test_is_model_cached():
    engine = TranscriptionEngine()
    result = engine.is_model_cached
    assert isinstance(result, bool)


def test_replace_spoken_punctuation_slash():
    from voice_overlay.transcription import _replace_spoken_punctuation
    text, changed = _replace_spoken_punctuation("slash home slash web dot config")
    assert text == "/home/web.config"
    assert changed is True


def test_replace_spoken_punctuation_path():
    from voice_overlay.transcription import _replace_spoken_punctuation
    text, changed = _replace_spoken_punctuation("cd slash etc slash nginx")
    assert text == "cd /etc/nginx"
    assert changed is True


def test_replace_spoken_punctuation_no_match():
    from voice_overlay.transcription import _replace_spoken_punctuation
    text, changed = _replace_spoken_punctuation("hello world")
    assert text == "hello world"
    assert changed is False


def test_replace_spoken_punctuation_underscore():
    from voice_overlay.transcription import _replace_spoken_punctuation
    text, changed = _replace_spoken_punctuation("my underscore var")
    assert text == "my _var"
    assert changed is True


def test_replace_spoken_punctuation_colon():
    from voice_overlay.transcription import _replace_spoken_punctuation
    text, changed = _replace_spoken_punctuation("path colon slash usr")
    assert text == "path :/usr"
    assert changed is True


def test_replace_spoken_punctuation_multiple():
    from voice_overlay.transcription import _replace_spoken_punctuation
    text, changed = _replace_spoken_punctuation("slash home slash user dot local slash bin")
    assert text == "/home/user.local/bin"
    assert changed is True


def test_replace_spoken_punctuation_merges_spelled_words():
    from voice_overlay.transcription import _replace_spoken_punctuation
    text, changed = _replace_spoken_punctuation("h t t p s colon slash slash")
    assert text == "https://"
    assert changed is True


def test_replace_spoken_punctuation_stop_word_breaks_path():
    from voice_overlay.transcription import _replace_spoken_punctuation
    text, changed = _replace_spoken_punctuation("open slash var slash log for the log file")
    assert text == "open /var/log for the log file"
    assert changed is True


def test_context_buffer_starts_empty():
    engine = TranscriptionEngine()
    assert engine._build_context_prompt() is None


def test_context_buffer_accumulates():
    engine = TranscriptionEngine(model_size="tiny")
    mock_segment = MagicMock()
    mock_segment.text = "test"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], None)
    engine._model = mock_model

    engine.transcribe(np.zeros(16000, dtype=np.float32))
    engine.transcribe(np.zeros(16000, dtype=np.float32))
    assert len(engine._context_buffer) == 2


def test_reset_context_clears_buffer():
    engine = TranscriptionEngine(model_size="tiny")
    engine._context_buffer = ["hello", "world"]
    engine.reset_context()
    assert len(engine._context_buffer) == 0


def test_context_prompt_is_passed():
    engine = TranscriptionEngine(model_size="tiny")
    mock_segment = MagicMock()
    mock_segment.text = "result"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], None)
    engine._model = mock_model
    engine._context_buffer = ["previous text"]

    engine.transcribe(np.zeros(16000, dtype=np.float32))
    call_kwargs = mock_model.transcribe.call_args[1]
    assert "initial_prompt" in call_kwargs
    assert call_kwargs["initial_prompt"] == "previous text"
