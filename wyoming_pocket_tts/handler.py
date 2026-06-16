"""Wyoming event handler for Pocket TTS."""

import logging
from pathlib import Path

import numpy as np
from pocket_tts import TTSModel
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler
from wyoming.tts import Synthesize

_LOGGER = logging.getLogger(__name__)


def peak_normalize(samples: "np.ndarray", target_db: float) -> "np.ndarray":
    """Scale ``samples`` so the loudest sample reaches ``target_db`` dBFS.

    Pure amplitude scaling by a single factor: it is lossless and never clips
    (the result peaks at exactly the target, which is <= 0 dBFS). Silent input
    is returned unchanged. ``target_db`` should be <= 0.
    """
    peak = float(np.max(np.abs(samples)))
    if peak <= 0.0:
        return samples
    target = 10.0 ** (target_db / 20.0)
    return samples * (target / peak)


# Pocket TTS preset voices
PRESET_VOICES = [
    "alba",
    "marius",
    "javert",
    "jean",
    "fantine",
    "cosette",
    "eponine",
    "azelma",
]

# Audio formats accepted for custom voice samples in the voices directory.
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}


def find_custom_voice_file(voices_dir: str, name: str) -> "Path | None":
    """Return the custom voice sample file for ``name`` in ``voices_dir``, if any."""
    voices_path = Path(voices_dir)
    if not voices_path.exists():
        return None
    for audio_file in voices_path.iterdir():
        if audio_file.suffix.lower() in AUDIO_EXTENSIONS and audio_file.stem == name:
            return audio_file
    return None


def list_custom_voice_names(voices_dir: str) -> list[str]:
    """List custom voice names (file stems) available in ``voices_dir`` (no loading)."""
    voices_path = Path(voices_dir)
    if not voices_path.exists():
        return []
    return [
        f.stem for f in voices_path.iterdir() if f.suffix.lower() in AUDIO_EXTENSIONS
    ]


def load_voice(model: TTSModel, name: str, voices_dir: str):
    """Load a single voice state by name (preset or custom file). Returns state or None.

    Each loaded voice holds a sizeable state in memory, so callers preload only the
    voices they need and rely on this for on-demand loading of the rest.
    """
    if name in PRESET_VOICES:
        try:
            # Preset voice name is passed directly (no HF auth required).
            return model.get_state_for_audio_prompt(name)  # type: ignore[arg-type]
        except Exception as e:
            _LOGGER.error("Failed to load preset voice %s: %s", name, e)
            return None
    custom_file = find_custom_voice_file(voices_dir, name)
    if custom_file is not None:
        try:
            return model.get_state_for_audio_prompt(str(custom_file))  # type: ignore[arg-type]
        except Exception as e:
            _LOGGER.error("Failed to load custom voice %s: %s", name, e)
    return None


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

    def _load_voice(self, voice_name: str):
        """Load a voice (preset or custom) on-demand."""
        return load_voice(self.model, voice_name, self.cli_args.voices_dir)

    async def handle_event(self, event: Event) -> bool:
        """Handle Wyoming events."""
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info.event())
            _LOGGER.debug("Sent info in response to describe")
            return True

        if Synthesize.is_type(event.type):
            synthesize = Synthesize.from_event(event)
            _LOGGER.debug(
                "Synthesize request: text=%s, voice=%s",
                synthesize.text,
                synthesize.voice,
            )

            # Determine which voice to use
            voice_name = self.cli_args.voice  # default
            if synthesize.voice and synthesize.voice.name:
                voice_name = synthesize.voice.name
            elif synthesize.voice and synthesize.voice.speaker:
                voice_name = synthesize.voice.speaker

            _LOGGER.info("Generating speech with voice: %s", voice_name)

            # Get voice state (preset or custom), loading on-demand if not preloaded.
            voice_state = self.voice_states.get(voice_name)
            if voice_state is None:
                _LOGGER.info("Loading voice on-demand: %s", voice_name)
                voice_state = self._load_voice(voice_name)
                if voice_state is not None:
                    self.voice_states[voice_name] = voice_state
                elif voice_name != self.cli_args.voice:
                    # Unknown voice - fall back to the configured default.
                    _LOGGER.warning(
                        "Voice '%s' not found, using default: %s",
                        voice_name,
                        self.cli_args.voice,
                    )
                    voice_name = self.cli_args.voice
                    voice_state = self.voice_states.get(voice_name)
                    if voice_state is None:
                        voice_state = self._load_voice(voice_name)
                        if voice_state is not None:
                            self.voice_states[voice_name] = voice_state

            if voice_state is None:
                _LOGGER.error(
                    "No voice state available! Make sure voice files exist in %s",
                    self.cli_args.voices_dir,
                )
                return True

            # Generate audio
            try:
                audio_tensor = self.model.generate_audio(voice_state, synthesize.text)  # type: ignore[arg-type]
                samples = audio_tensor.numpy()

                # Optional peak normalization. Pocket TTS output level tracks the
                # loudness of the voice prompt, so a quiet sample produces quiet
                # speech that sounds weak on a speaker even at full volume. This
                # scales the whole clip by a single factor so its loudest sample
                # just reaches the target ceiling -- lossless and never clipping,
                # so it raises volume without adding distortion.
                if getattr(self.cli_args, "normalize_volume", False):
                    samples = peak_normalize(samples, self.cli_args.normalize_target_db)

                audio_bytes = (samples * 32767).astype("int16").tobytes()

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
                voice_states[voice_name] = model.get_state_for_audio_prompt(
                    str(audio_file)  # type: ignore[arg-type]
                )
                _LOGGER.info("Successfully loaded voice: %s", voice_name)
            except Exception as e:
                _LOGGER.exception("Failed to load voice %s: %s", voice_name, e)

    return voice_states
