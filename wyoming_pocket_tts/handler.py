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
    "giovanni",
    "lola",
    "juergen",
    "rafael",
    "estelle",
    "anna",
    "azelma",
    "bill_boerst",
    "caro_davy",
    "charles",
    "cosette",
    "eponine",
    "eve",
    "fantine",
    "george",
    "jane",
    "jean",
    "javert",
    "marius",
    "mary",
    "michael",
    "paul",
    "peter_yearsley",
    "stuart_bell",
    "vera",
]

PRESET_VOICE_LANGUAGES: dict[str, str] = {
    "alba": "english",
    "giovanni": "italian",
    "lola": "spanish",
    "juergen": "german",
    "rafael": "portuguese",
    "estelle": "french",
    "anna": "english",
    "azelma": "english",
    "bill_boerst": "english",
    "caro_davy": "english",
    "charles": "english",
    "cosette": "english",
    "eponine": "english",
    "eve": "english",
    "fantine": "english",
    "george": "english",
    "jane": "english",
    "jean": "english",
    "javert": "english",
    "marius": "english",
    "mary": "english",
    "michael": "english",
    "paul": "english",
    "peter_yearsley": "english",
    "stuart_bell": "english",
    "vera": "english",
}

DEFAULT_PRESET_BY_LANGUAGE: dict[str, str] = {
    "english": "alba",
    "french": "estelle",
    "french_24l": "estelle",
    "german": "juergen",
    "german_24l": "juergen",
    "portuguese": "rafael",
    "portuguese_24l": "rafael",
    "italian": "giovanni",
    "italian_24l": "giovanni",
    "spanish": "lola",
    "spanish_24l": "lola",
}


def preset_voices_for_language(language: "str | None") -> list[str]:
    """Return preset voices that match the selected Pocket TTS language."""
    normalized_language = normalize_language(language)
    base_language = normalized_language.removesuffix("_24l")
    return [
        voice
        for voice in PRESET_VOICES
        if PRESET_VOICE_LANGUAGES.get(voice) == base_language
    ]


def default_preset_for_language(language: "str | None") -> str:
    """Return Pocket TTS's default preset voice for the selected language."""
    return DEFAULT_PRESET_BY_LANGUAGE.get(normalize_language(language), "alba")


# Audio formats accepted for custom voice samples in the voices directory.
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "english",
    "english": "english",
    "fr": "french",
    "french": "french",
    "fr_24l": "french_24l",
    "french_24l": "french_24l",
    "de": "german",
    "german": "german",
    "de_24l": "german_24l",
    "german_24l": "german_24l",
    "pt": "portuguese",
    "portuguese": "portuguese",
    "pt_24l": "portuguese_24l",
    "portuguese_24l": "portuguese_24l",
    "it": "italian",
    "italian": "italian",
    "it_24l": "italian_24l",
    "italian_24l": "italian_24l",
    "es": "spanish",
    "spanish": "spanish",
    "es_24l": "spanish_24l",
    "spanish_24l": "spanish_24l",
}

WYOMING_LANGUAGE_CODES: dict[str, str] = {
    "english": "en",
    "french": "fr",
    "french_24l": "fr",
    "german": "de",
    "german_24l": "de",
    "portuguese": "pt",
    "portuguese_24l": "pt",
    "italian": "it",
    "italian_24l": "it",
    "spanish": "es",
    "spanish_24l": "es",
}

DEFAULT_LANGUAGE = "en"


def normalize_language(language: "str | None") -> str:
    """Return the Pocket TTS language name for a user-supplied language value."""
    if not language:
        return SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE]
    normalized = language.strip().lower().replace("-", "_")
    return SUPPORTED_LANGUAGES.get(normalized, normalized)


def wyoming_language_code(language: str) -> str:
    """Return the Wyoming/Home Assistant language code for a Pocket TTS language."""
    return WYOMING_LANGUAGE_CODES.get(normalize_language(language), DEFAULT_LANGUAGE)


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


def plan_voices(
    configured: list[str],
    custom_voice_names: list[str],
    language: "str | None",
) -> tuple[list[str], list[str], str]:
    """Decide which voices to preload, which to advertise, and the default.

    Returns ``(to_preload, to_advertise, default_voice)``.

    When ``configured`` is non-empty the add-on operates in the simple, explicit
    mode the config UI promotes: exactly those voices are preloaded (fast first
    response) and they are the only ones advertised to Home Assistant. The first
    one is the default used when a request does not name a voice.

    When ``configured`` is empty we keep the original behaviour: advertise every
    built-in preset plus any custom files (loaded on demand), preloading only the
    default preset for the language.
    """
    fallback = default_preset_for_language(language)

    # De-dup while preserving order.
    configured = list(dict.fromkeys(v.strip() for v in configured if v.strip()))

    if configured:
        return configured, configured, configured[0]

    advertise = list(dict.fromkeys(PRESET_VOICES + custom_voice_names))
    return [fallback], advertise, fallback


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
        if getattr(model, "has_voice_cloning", True) is False:
            _LOGGER.warning(
                "Custom voice '%s' requires Pocket TTS voice cloning weights, but "
                "the loaded language model does not have them available. Accept the "
                "Kyutai Pocket TTS model terms and configure HF_TOKEN, or use a preset voice.",
                name,
            )
            return None
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

    def _resolve_voice_name(self, synthesize: Synthesize) -> str:
        voice_name = self.cli_args.voice
        if synthesize.voice and synthesize.voice.name:
            voice_name = synthesize.voice.name
        elif synthesize.voice and synthesize.voice.speaker:
            voice_name = synthesize.voice.speaker

        return voice_name

    def _fallback_voice_name(self) -> str:
        if self.cli_args.voice in PRESET_VOICES:
            return self.cli_args.voice
        return default_preset_for_language(self.cli_args.language)

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

            voice_name = self._resolve_voice_name(synthesize)

            _LOGGER.info(
                "Generating speech with voice: %s, language: %s",
                voice_name,
                self.cli_args.language,
            )

            # Get voice state (preset or custom), loading on-demand if not preloaded.
            voice_state = self.voice_states.get(voice_name)
            if voice_state is None:
                _LOGGER.info("Loading voice on-demand: %s", voice_name)
                voice_state = self._load_voice(voice_name)
                if voice_state is not None:
                    self.voice_states[voice_name] = voice_state
                else:
                    fallback_voice = self._fallback_voice_name()
                    if voice_name != fallback_voice:
                        _LOGGER.warning(
                            "Voice '%s' not found or unavailable, using fallback preset: %s",
                            voice_name,
                            fallback_voice,
                        )
                        voice_name = fallback_voice
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


def get_wyoming_info(voices: list[str], language: str = DEFAULT_LANGUAGE) -> Info:
    """Create Wyoming info describing available TTS voices."""
    tts_voices = []
    language_code = wyoming_language_code(language)

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
                languages=[language_code],
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
