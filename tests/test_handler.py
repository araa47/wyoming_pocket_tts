"""Tests for wyoming_pocket_tts handler."""

from wyoming_pocket_tts.handler import PRESET_VOICES, get_wyoming_info


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
