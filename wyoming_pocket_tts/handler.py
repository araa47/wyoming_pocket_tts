"""Wyoming event handler for Pocket TTS."""

import logging
from pathlib import Path

from pocket_tts import TTSModel
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler
from wyoming.tts import Synthesize

_LOGGER = logging.getLogger(__name__)

# Pocket TTS preset voices
PRESET_VOICES = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]


class PocketTTSEventHandler(AsyncEventHandler):
    """Handle Wyoming TTS events with Pocket TTS."""

    def __init__(
        self,
        wyoming_info: Info,
        cli_args,
        model: TTSModel,
        voice_states: dict,
        *args,
        **kwargs,
    ) -> None:
        """Initialize handler."""
        super().__init__(*args, **kwargs)
        self.wyoming_info = wyoming_info
        self.cli_args = cli_args
        self.model = model
        self.voice_states = voice_states

    def _load_preset_voice(self, voice_name: str):
        """Load a preset voice on-demand."""
        voice_urls = {
            "alba": "hf://kyutai/tts-voices/alba-mackenna/casual.wav",
            "marius": "hf://kyutai/tts-voices/voice-donations/Selfie.wav",
            "javert": "hf://kyutai/tts-voices/voice-donations/Butter.wav",
            "jean": "hf://kyutai/tts-voices/ears/p010/freeform_speech_01.wav",
            "fantine": "hf://kyutai/tts-voices/vctk/p244_023.wav",
            "cosette": "hf://kyutai/tts-voices/expresso/ex04-ex02_confused_001_channel1_499s.wav",
            "eponine": "hf://kyutai/tts-voices/vctk/p262_023.wav",
            "azelma": "hf://kyutai/tts-voices/vctk/p303_023.wav",
        }
        if voice_name in voice_urls:
            try:
                return self.model.get_state_for_audio_prompt(voice_urls[voice_name])
            except Exception as e:
                _LOGGER.error("Failed to load voice %s: %s", voice_name, e)
        return None

    async def handle_event(self, event: Event) -> bool:
        """Handle Wyoming events."""
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info.event())
            _LOGGER.debug("Sent info in response to describe")
            return True

        if Synthesize.is_type(event.type):
            synthesize = Synthesize.from_event(event)
            _LOGGER.debug("Synthesize request: text=%s, voice=%s", synthesize.text, synthesize.voice)

            # Determine which voice to use
            voice_name = self.cli_args.voice  # default
            if synthesize.voice and synthesize.voice.name:
                voice_name = synthesize.voice.name
            elif synthesize.voice and synthesize.voice.speaker:
                voice_name = synthesize.voice.speaker

            _LOGGER.info("Generating speech with voice: %s", voice_name)

            # Get voice state (preset or custom)
            voice_state = self.voice_states.get(voice_name)
            if voice_state is None:
                # Try to load preset voice on-demand
                if voice_name in PRESET_VOICES:
                    _LOGGER.info("Loading preset voice on-demand: %s", voice_name)
                    voice_state = self._load_preset_voice(voice_name)
                    if voice_state:
                        self.voice_states[voice_name] = voice_state
                else:
                    # Unknown voice - fall back to default
                    _LOGGER.warning("Voice '%s' not found, using default: %s", voice_name, self.cli_args.voice)
                    voice_name = self.cli_args.voice
                    voice_state = self.voice_states.get(voice_name)
                    # Load default voice on-demand if not already loaded
                    if voice_state is None and voice_name in PRESET_VOICES:
                        _LOGGER.info("Loading default voice on-demand: %s", voice_name)
                        voice_state = self._load_preset_voice(voice_name)
                        if voice_state:
                            self.voice_states[voice_name] = voice_state

            if voice_state is None:
                _LOGGER.error("No voice state available! Make sure voice files exist in %s", self.cli_args.voices_dir)
                return True

            # Generate audio
            try:
                audio_tensor = self.model.generate_audio(voice_state, synthesize.text)
                audio_bytes = (audio_tensor.numpy() * 32767).astype("int16").tobytes()

                # Send audio via Wyoming protocol
                sample_rate = self.model.sample_rate
                sample_width = 2  # 16-bit
                channels = 1  # mono

                await self.write_event(
                    AudioStart(
                        rate=sample_rate,
                        width=sample_width,
                        channels=channels,
                    ).event()
                )

                # Send audio in chunks (4096 samples per chunk)
                chunk_size = 4096 * sample_width * channels
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i : i + chunk_size]
                    await self.write_event(
                        AudioChunk(
                            audio=chunk,
                            rate=sample_rate,
                            width=sample_width,
                            channels=channels,
                        ).event()
                    )

                await self.write_event(AudioStop().event())
                _LOGGER.info("Audio generation complete")

            except Exception as e:
                _LOGGER.exception("Error generating audio: %s", e)

        return True


def get_wyoming_info(voices: list[str]) -> Info:
    """Create Wyoming info describing available TTS voices."""
    tts_voices = []

    kyutai_attribution = Attribution(
        name="Kyutai",
        url="https://kyutai.org/",
    )

    for voice in voices:
        tts_voices.append(
            TtsVoice(
                name=voice,
                attribution=kyutai_attribution,
                installed=True,
                description=f"Pocket TTS voice: {voice}",
                version=None,
                languages=["en"],  # Pocket TTS is English-only
            )
        )

    from . import __version__

    return Info(
        tts=[
            TtsProgram(
                name="pocket-tts",
                attribution=kyutai_attribution,
                installed=True,
                description="Pocket TTS - Fast CPU-based TTS with voice cloning",
                version=__version__,
                voices=tts_voices,
            )
        ]
    )


def load_custom_voices(voices_dir: str, model: TTSModel) -> dict:
    """Load custom voice samples from a directory."""
    voice_states = {}
    voices_path = Path(voices_dir)

    if not voices_path.exists():
        _LOGGER.warning("Voices directory does not exist: %s", voices_dir)
        return voice_states

    # Supported audio formats
    audio_extensions = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

    for audio_file in voices_path.iterdir():
        if audio_file.suffix.lower() in audio_extensions:
            voice_name = audio_file.stem
            _LOGGER.info("Loading custom voice: %s from %s", voice_name, audio_file)
            try:
                voice_states[voice_name] = model.get_state_for_audio_prompt(str(audio_file))
                _LOGGER.info("Successfully loaded voice: %s", voice_name)
            except Exception as e:
                _LOGGER.exception("Failed to load voice %s: %s", voice_name, e)

    return voice_states
