"""Tests for wyoming_pocket_tts handler."""

import numpy as np
from wyoming_pocket_tts.handler import (
    PRESET_VOICES,
    get_wyoming_info,
    peak_normalize,
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


def test_get_wyoming_info_empty_voices():
    info = get_wyoming_info([])
    assert len(info.tts[0].voices) == 0


def test_peak_normalize_reaches_target_without_clipping():
    quiet = np.array([0.05, -0.1, 0.08, -0.03], dtype=np.float32)
    out = peak_normalize(quiet, -1.0)
    peak = float(np.max(np.abs(out)))
    expected = 10.0 ** (-1.0 / 20.0)
    assert peak == np.float32(expected) or abs(peak - expected) < 1e-6
    assert peak < 1.0  # never clips


def test_peak_normalize_is_pure_scaling():
    # Every non-zero sample is multiplied by the same factor -> lossless.
    sig = np.array([0.05, -0.1, 0.08, -0.03], dtype=np.float64)
    out = peak_normalize(sig, -3.0)
    ratios = out[sig != 0] / sig[sig != 0]
    assert np.allclose(ratios, ratios[0])


def test_peak_normalize_silent_input_unchanged():
    silent = np.zeros(8, dtype=np.float32)
    out = peak_normalize(silent, -1.0)
    assert np.array_equal(out, silent)
