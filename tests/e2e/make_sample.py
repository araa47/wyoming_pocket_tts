#!/usr/bin/env python3
"""Generate a non-WAV custom voice sample for the E2E cloning test.

Writes a few seconds of synthetic audio in a non-WAV format (default OGG) so the
E2E exercises the soundfile decode path that broke in 1.4.4. The content need not
be real speech — the point is that the file loads, the cloning weights encode it,
and synthesis runs end to end.

Usage:
    make_sample.py /share/tts-voices/rocky.ogg
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "sample.ogg")
    out.parent.mkdir(parents=True, exist_ok=True)

    sample_rate = 24000
    seconds = 4.0
    t = np.linspace(0.0, seconds, int(sample_rate * seconds), endpoint=False)
    # A gentle chirp plus a harmonic, kept well below clipping.
    sweep = np.sin(2 * np.pi * (110 + 40 * t) * t)
    harmonic = 0.5 * np.sin(2 * np.pi * 220 * t)
    audio = (0.25 * (sweep + harmonic)).astype("float32")

    fmt = out.suffix.lstrip(".").upper() or "OGG"
    sf.write(str(out), audio, sample_rate, format=fmt)
    print(
        f"wrote {out} ({out.stat().st_size} bytes, {fmt}, {seconds}s @ {sample_rate}Hz)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
