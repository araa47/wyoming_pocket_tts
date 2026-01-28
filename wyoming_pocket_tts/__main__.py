#!/usr/bin/env python3
"""Wyoming server for Pocket TTS."""

import argparse
import asyncio
import logging
import os
from functools import partial

from pocket_tts import TTSModel
from wyoming.server import AsyncServer

from . import __version__
from .handler import (
    PRESET_VOICES,
    PocketTTSEventHandler,
    get_wyoming_info,
    load_custom_voices,
)

_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Run the Wyoming Pocket TTS server."""
    parser = argparse.ArgumentParser(description="Wyoming server for Pocket TTS")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=10200,
        help="Port to bind to (default: 10200)",
    )
    parser.add_argument(
        "--voice",
        default="alba",
        help="Default voice to use (default: alba)",
    )
    parser.add_argument(
        "--voices-dir",
        default="/share/tts-voices",
        help="Directory containing custom voice samples (default: /share/tts-voices)",
    )
    parser.add_argument(
        "--preload-voices",
        action="store_true",
        help="Preload all preset voices at startup (slower startup, faster first request)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set HF token from environment if available
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        _LOGGER.info("Using HuggingFace token from environment")
        os.environ["HF_TOKEN"] = hf_token

    _LOGGER.info("Starting Wyoming Pocket TTS server v%s", __version__)
    _LOGGER.info("Loading Pocket TTS model...")

    # Load model
    model = TTSModel.load_model()
    _LOGGER.info("Model loaded successfully (sample rate: %d Hz)", model.sample_rate)

    # Load custom voices from directory
    voice_states = load_custom_voices(args.voices_dir, model)
    _LOGGER.info("Loaded %d custom voice(s) from %s", len(voice_states), args.voices_dir)

    # Optionally preload preset voices
    if args.preload_voices:
        _LOGGER.info("Preloading preset voices...")
        for voice in PRESET_VOICES:
            if voice not in voice_states:
                try:
                    # Use preset voice name directly (no HF auth required)
                    voice_states[voice] = model.get_state_for_audio_prompt(voice)
                    _LOGGER.info("Preloaded voice: %s", voice)
                except Exception as e:
                    _LOGGER.warning("Failed to preload voice %s: %s", voice, e)

    # Load default voice if not already loaded
    if args.voice not in voice_states:
        _LOGGER.info("Loading default voice: %s", args.voice)
        if args.voice in PRESET_VOICES:
            # Use preset voice name directly (no HF auth required)
            voice_states[args.voice] = model.get_state_for_audio_prompt(args.voice)
        else:
            # Assume it's a preset voice
            _LOGGER.warning("Default voice %s not found, will load on first request", args.voice)

    # Build list of available voices
    available_voices = list(set(PRESET_VOICES + list(voice_states.keys())))
    _LOGGER.info("Available voices: %s", ", ".join(available_voices))

    # Create Wyoming info
    wyoming_info = get_wyoming_info(available_voices)

    # Start server
    server = AsyncServer.from_uri(f"tcp://{args.host}:{args.port}")
    _LOGGER.info("Server listening on %s:%d", args.host, args.port)

    await server.run(
        partial(
            PocketTTSEventHandler,
            wyoming_info,
            args,
            model,
            voice_states,
        )
    )


def run() -> None:
    """Entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
