"""Wyoming event handler for Pocket TTS."""

import asyncio
import logging
from pathlib import Path

from pocket_tts import TTSModel
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler
from wyoming.tts import Synthesize

_LOGGER = logging.getLogger(__name__)

# Process-wide lock serializing generation on the shared TTS model. Pocket TTS's
# streaming generator is not thread-safe on a shared model instance, so concurrent
# requests (e.g. multiple satellites) must take turns. Created lazily on the
# running loop the first time it is needed.
_GENERATION_LOCK: "asyncio.Lock | None" = None


def _generation_lock() -> "asyncio.Lock":
    """Return the process-wide generation lock, creating it on first use."""
    global _GENERATION_LOCK
    if _GENERATION_LOCK is None:
        _GENERATION_LOCK = asyncio.Lock()
    return _GENERATION_LOCK


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

    async def _iter_audio_chunks(self, voice_state, text: str):
        """Yield 16-bit PCM byte chunks from Pocket TTS as they are generated.

        ``generate_audio_stream`` is a blocking generator, so each step is pumped
        in a worker thread. That keeps the event loop free to write the previous
        chunk to the socket while the next one is being decoded, and lets Home
        Assistant start playback after the first chunk instead of waiting for the
        whole clip.
        """
        stream = self.model.generate_audio_stream(voice_state, text)

        def next_chunk_bytes() -> "bytes | None":
            # Pull and convert one chunk; runs in a worker thread. Returns None
            # when the generator is exhausted. chunk is a torch.Tensor of float
            # samples in [-1, 1] -> 16-bit PCM bytes.
            chunk = next(stream, None)
            if chunk is None:
                return None
            return (chunk.numpy() * 32767).astype("int16").tobytes()

        while True:
            audio_bytes = await asyncio.to_thread(next_chunk_bytes)
            if audio_bytes is None:
                break
            yield audio_bytes

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

            text = (synthesize.text or "").strip()
            sample_rate = self.model.sample_rate
            sample_width = 2  # 16-bit
            channels = 1  # mono

            if not text:
                # Nothing to say: still send a well-formed (empty) audio response
                # so Home Assistant's pipeline completes cleanly.
                await self.write_event(
                    AudioStart(
                        rate=sample_rate, width=sample_width, channels=channels
                    ).event()
                )
                await self.write_event(AudioStop().event())
                return True

            # Stream audio as it is produced, so Home Assistant can begin playback
            # while the rest is still being synthesized. Pocket TTS runs at ~real
            # time on CPU, so buffering the whole clip first delayed all audio by
            # its full duration and could trip HA's TTS timeout on long replies.
            try:
                async with _generation_lock():
                    await self.write_event(
                        AudioStart(
                            rate=sample_rate, width=sample_width, channels=channels
                        ).event()
                    )
                    chunk_count = 0
                    async for audio_bytes in self._iter_audio_chunks(voice_state, text):
                        await self.write_event(
                            AudioChunk(
                                audio=audio_bytes,
                                rate=sample_rate,
                                width=sample_width,
                                channels=channels,
                            ).event()
                        )
                        chunk_count += 1
                    await self.write_event(AudioStop().event())
                _LOGGER.info("Streamed %d audio chunk(s)", chunk_count)

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
