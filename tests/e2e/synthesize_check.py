#!/usr/bin/env python3
"""End-to-end check against a running Wyoming Pocket TTS server.

Connects over the Wyoming protocol, verifies the server advertises the expected
custom voice, then requests synthesis with that voice and asserts a non-trivial
stream of PCM audio comes back. Used by the container E2E workflow to prove that
custom voice cloning (including non-WAV sample decoding, which broke in 1.4.4)
works end to end.

Usage:
    synthesize_check.py --host 127.0.0.1 --port 10200 --voice rocky
"""

import argparse
import asyncio
import sys

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.info import Describe, Info
from wyoming.tts import Synthesize, SynthesizeVoice


async def _run(host: str, port: int, voice: str, text: str) -> int:
    client = AsyncTcpClient(host, port)
    await client.connect()
    try:
        # --- describe: the voice must be advertised ---
        await client.write_event(Describe().event())
        event = await asyncio.wait_for(client.read_event(), timeout=30)
        assert event is not None and Info.is_type(
            event.type
        ), f"expected Info, got {event}"
        info = Info.from_event(event)
        assert info.tts, "no TTS programs advertised"
        advertised = [v.name for v in info.tts[0].voices]
        print(
            f"describe ok: program={info.tts[0].name} v{info.tts[0].version} voices={advertised}"
        )
        assert voice in advertised, f"voice {voice!r} not advertised (got {advertised})"

        # --- synthesize with the (cloned) voice ---
        await client.write_event(
            Synthesize(text=text, voice=SynthesizeVoice(name=voice)).event()
        )
        n_bytes = 0
        n_chunks = 0
        rate = None
        while True:
            event = await asyncio.wait_for(client.read_event(), timeout=180)
            assert event is not None, "connection closed before AudioStop"
            if AudioStart.is_type(event.type):
                rate = AudioStart.from_event(event).rate
            elif AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                n_bytes += len(chunk.audio)
                n_chunks += 1
            elif AudioStop.is_type(event.type):
                break

        seconds = n_bytes / 2 / (rate or 1)
        print(
            f"synthesize ok: voice={voice} chunks={n_chunks} bytes={n_bytes} "
            f"rate={rate}Hz (~{seconds:.1f}s audio)"
        )
        # A real clip is many KB. A fallback/empty response would be tiny.
        assert n_chunks > 0, "no audio chunks received"
        assert (
            n_bytes > 20000
        ), f"suspiciously little audio ({n_bytes} bytes) — clone may have failed"
    finally:
        await client.disconnect()

    print("E2E PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10200)
    parser.add_argument(
        "--voice", required=True, help="voice name that must be advertised"
    )
    parser.add_argument("--text", default="Hello from the end to end test.")
    args = parser.parse_args()
    return asyncio.run(_run(args.host, args.port, args.voice, args.text))


if __name__ == "__main__":
    sys.exit(main())
