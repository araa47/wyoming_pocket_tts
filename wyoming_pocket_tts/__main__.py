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
    list_custom_voice_names,
    load_voice,
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
        default="",
        help=(
            "Comma-separated voice names to preload at startup, e.g. 'rocky' or "
            "'rocky,alba'. Empty preloads only the default --voice. 'all' preloads "
            "every preset and custom voice (most RAM). Non-preloaded voices load on "
            "demand on first use. Preloading fewer voices uses far less memory."
        ),
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

    # Discover custom voices present in the voices directory (names only, no load).
    custom_voice_names = list_custom_voice_names(args.voices_dir)
    if custom_voice_names:
        _LOGGER.info(
            "Found %d custom voice(s) in %s: %s",
            len(custom_voice_names),
            args.voices_dir,
            ", ".join(custom_voice_names),
        )

    # Decide which voices to preload. Each voice state is large, so preloading
    # everything wastes RAM and can OOM small hosts. Only the selected voices load
    # now; the rest load on demand on first use.
    preload_raw = (args.preload_voices or "").strip()
    if preload_raw.lower() == "all":
        to_preload = PRESET_VOICES + custom_voice_names
    elif preload_raw == "":
        to_preload = [args.voice]  # default: only the selected voice
    else:
        to_preload = [v.strip() for v in preload_raw.split(",") if v.strip()]
    # Always ensure the configured default voice is ready.
    if args.voice not in to_preload:
        to_preload.append(args.voice)

    voice_states: dict = {}
    for name in dict.fromkeys(to_preload):  # de-dup, preserve order
        state = load_voice(model, name, args.voices_dir)
        if state is not None:
            voice_states[name] = state
            _LOGGER.info("Preloaded voice: %s", name)
        else:
            _LOGGER.warning(
                "Could not preload voice '%s' (unknown name?); will try on demand",
                name,
            )

    # Advertise every available voice (presets + custom files present), even if not
    # preloaded, so they are all selectable from Home Assistant.
    available_voices = list(dict.fromkeys(PRESET_VOICES + custom_voice_names))
    _LOGGER.info(
        "Preloaded %d voice(s); %d available total",
        len(voice_states),
        len(available_voices),
    )

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
