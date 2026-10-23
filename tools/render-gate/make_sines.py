#!/usr/bin/env python3
"""Sine inputs for the pitch gate: 440, 1000 and 2093 Hz.

usage: make_sines.py <outdir>

3 s at 48 kHz, amplitude 0.3, 16-bit mono, matching the corpus sine
inputs. Prints each sha256 so a run can be checked against another.
"""
import hashlib
import math
import os
import struct
import sys
import wave

SR = 48000
N = 3 * SR
HZ = [440.0, 1000.0, 2093.0]


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    for hz in HZ:
        name = "sine_%g" % hz
        path = os.path.join(outdir, name + ".wav")
        w = wave.open(path, "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = b"".join(
            struct.pack("<h", round(0.3 * math.sin(2 * math.pi * hz * i / SR) * 32767))
            for i in range(N)
        )
        w.writeframes(frames)
        w.close()
        with open(path, "rb") as f:
            print("%s %s" % (hashlib.sha256(f.read()).hexdigest(), name))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: make_sines.py <outdir>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
