"""Tests for wyoming_pocket_tts handler."""

import asyncio
from types import SimpleNamespace
from typing import cast

import torch
from pocket_tts import TTSModel
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.tts import Synthesize, SynthesizeVoice
from wyoming_pocket_tts.handler import (
    PRESET_VOICES,
    PocketTTSEventHandler,
    default_preset_for_language,
    get_wyoming_info,
    load_voice,
    normalize_language,
)


def test_preset_voices_not_empty():
    assert len(PRESET_VOICES) > 0


def test_preset_voices_contains_alba():
    assert "alba" in PRESET_VOICES


def test_get_wyoming_info_returns_info():
    info = get_wyoming_info(["alba", "marius"])
    assert info is not None
    assert len(info.tts) == 1
    assert info.tts[0].name == "pocket-tts"


def test_get_wyoming_info_voices():
    voices = ["alba", "marius", "custom_voice"]
    info = get_wyoming_info(voices)
    voice_names = [v.name for v in info.tts[0].voices]
    assert set(voice_names) == set(voices)


def test_get_wyoming_info_uses_configured_language():
    info = get_wyoming_info(["alba"], "spanish")
    assert info.tts[0].voices[0].languages == ["es"]


def test_normalize_language_accepts_short_codes():
    assert normalize_language("en") == "english"
    assert normalize_language("fr") == "french"
    assert normalize_language("fr_24l") == "french_24l"
    assert normalize_language("spanish_24l") == "spanish_24l"


def test_default_preset_for_language():
    assert default_preset_for_language("es") == "lola"
    assert default_preset_for_language("fr_24l") == "estelle"


def test_get_wyoming_info_empty_voices():
    info = get_wyoming_info([])
    assert len(info.tts[0].voices) == 0


class _FakeModel:
    """Minimal stand-in for TTSModel that streams a few fixed audio chunks."""

    sample_rate = 24000

    def __init__(self, num_chunks=3, chunk_samples=4):
        self._num_chunks = num_chunks
        self._chunk_samples = chunk_samples
        self.stream_calls = 0

    def generate_audio_stream(self, voice_state, text, **kwargs):
        self.stream_calls += 1
        for _ in range(self._num_chunks):
            # torch.Tensor of float samples in [-1, 1], like the real model yields.
            yield torch.full((self._chunk_samples,), 0.5, dtype=torch.float32)


class _RecordingHandler(PocketTTSEventHandler):
    """Handler whose write_event records events instead of touching a socket."""

    def __init__(self, model):
        # Bypass AsyncEventHandler.__init__ (needs a reader/writer); set only
        # what handle_event uses.
        self.wyoming_info = get_wyoming_info(["alba"])
        self.cli_args = SimpleNamespace(
            voice="alba",
            language="english",
            voices_dir="/nonexistent",
        )
        self.model = model
        self.voice_states = {"alba": object()}
        self.written = []

    async def write_event(self, event):
        self.written.append(event)


def _run(coro):
    return asyncio.run(coro)


def test_synthesize_streams_chunks_in_order():
    model = _FakeModel(num_chunks=3, chunk_samples=4)
    handler = _RecordingHandler(model)

    result = _run(handler.handle_event(Synthesize(text="hello there").event()))

    assert result is True
    assert model.stream_calls == 1
    # AudioStart, then one AudioChunk per streamed chunk, then AudioStop.
    assert AudioStart.is_type(handler.written[0].type)
    assert AudioStop.is_type(handler.written[-1].type)
    chunk_events = [e for e in handler.written if AudioChunk.is_type(e.type)]
    assert len(chunk_events) == 3
    # 4 float samples -> 4 * 2 bytes (16-bit) per chunk.
    for e in chunk_events:
        assert len(AudioChunk.from_event(e).audio) == 4 * 2


def test_empty_text_sends_clean_empty_response():
    model = _FakeModel()
    handler = _RecordingHandler(model)

    result = _run(handler.handle_event(Synthesize(text="   ").event()))

    assert result is True
    # No generation attempted, but HA still gets a valid start/stop framing.
    assert model.stream_calls == 0
    assert AudioStart.is_type(handler.written[0].type)
    assert AudioStop.is_type(handler.written[-1].type)
    assert not [e for e in handler.written if AudioChunk.is_type(e.type)]


def test_non_english_custom_voice_request_is_allowed():
    model = _FakeModel()
    handler = _RecordingHandler(model)
    handler.cli_args.language = "spanish"
    handler.voice_states = {"alba": object(), "custom_voice": object()}

    result = _run(
        handler.handle_event(
            Synthesize(text="hola", voice=SynthesizeVoice(name="custom_voice")).event()
        )
    )

    assert result is True
    assert model.stream_calls == 1


def test_custom_voice_requires_cloning_weights(tmp_path):
    voice_file = tmp_path / "rocky.ogg"
    voice_file.write_bytes(b"fake")

    class ModelWithoutCloning(_FakeModel):
        has_voice_cloning = False

        def get_state_for_audio_prompt(self, audio_conditioning):
            raise AssertionError("custom audio should not be loaded")

    model = cast(TTSModel, ModelWithoutCloning())
    assert load_voice(model, "rocky", str(tmp_path)) is None


def test_custom_default_falls_back_to_language_preset_when_unavailable():
    model = _FakeModel()
    handler = _RecordingHandler(model)
    handler.cli_args.voice = "rocky"
    handler.cli_args.language = "spanish"
    handler.voice_states = {"lola": object()}

    result = _run(handler.handle_event(Synthesize(text="hola").event()))

    assert result is True
    assert model.stream_calls == 1
