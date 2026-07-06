"""Regression guard for custom-voice sample decoding.

v1.4.4 dropped the ``soundfile`` dependency believing it unused. Nothing in this
project imports it directly, but ``pocket_tts.data.audio`` imports it lazily to
read non-WAV (mp3/ogg/flac) voice samples, so custom voice cloning from those
formats silently broke ("soundfile is required to read non-WAV audio files").

These tests fail fast if soundfile ever goes missing again. They need neither a
model download nor a Hugging Face token, so they run in the normal test job on
every PR. Full cloning + synthesis is exercised separately by the container E2E
job (``.github/workflows/job-e2e.yml``), which needs the gated model weights.
"""

import numpy as np
import pytest


def _write_tone(path, fmt: str, sample_rate: int = 24000, seconds: float = 1.0) -> None:
    """Write a short sine tone to ``path`` in ``fmt`` using soundfile."""
    import soundfile as sf

    t = np.linspace(0.0, seconds, int(sample_rate * seconds), endpoint=False)
    tone = (0.3 * np.sin(2 * np.pi * 220.0 * t)).astype("float32")
    sf.write(str(path), tone, sample_rate, format=fmt)


def test_soundfile_is_installed():
    """The exact dependency removed in 1.4.4 must stay installed."""
    import soundfile  # noqa: F401


@pytest.mark.parametrize("ext,fmt", [("ogg", "OGG"), ("flac", "FLAC"), ("wav", "WAV")])
def test_pocket_tts_reads_voice_sample_formats(tmp_path, ext, fmt):
    """pocket_tts must decode the audio formats we accept as custom voices.

    This is the exact code path (``audio_read``) that ``get_state_for_audio_prompt``
    runs when loading a custom voice file, so it guards the 1.4.4 break directly.
    """
    from pocket_tts.data.audio import audio_read

    sample = tmp_path / f"voice.{ext}"
    _write_tone(sample, fmt)

    wav, sample_rate = audio_read(str(sample))

    assert sample_rate == 24000
    # ~1s of audio decoded to samples, not an empty/garbage read.
    assert wav.shape[-1] > 10000
