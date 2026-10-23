#!/usr/bin/env python3
"""Spectral peak of a wav, dependency free.

usage: peak.py [--n N] [--lo HZ] [--hi HZ] <wav> [<wav> ...]

Reads 16-bit PCM wavs, averages power across Hann windows at 50 percent
overlap, picks the peak bin in [--lo, --hi] and refines it by parabolic
interpolation on the log power. Prints the peak in Hz, the cents against
an optional --target, and the level of the first four harmonics below it,
so a fundamental can be told from a partial.

No numpy: a radix-2 FFT in pure Python. A 10 s 48 kHz file takes about
40 s on a Raspberry Pi class host.
"""
import argparse
import cmath
import math
import struct
import sys
import wave


def fft(a):
    m = len(a)
    j = 0
    for i in range(1, m):
        bit = m >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    ln = 2
    while ln <= m:
        ang = -2 * math.pi / ln
        wl = cmath.exp(1j * ang)
        half = ln // 2
        for i in range(0, m, ln):
            wv = 1 + 0j
            for k in range(i, i + half):
                u = a[k]
                v = a[k + half] * wv
                a[k] = u + v
                a[k + half] = u - v
                wv *= wl
        ln <<= 1
    return a


def peak_of(path, n=16384, lo_hz=100.0, hi_hz=2000.0):
    w = wave.open(path)
    sr = w.getframerate()
    frames = w.getnframes()
    if w.getsampwidth() != 2 or w.getnchannels() != 1:
        raise SystemExit("%s: need 16-bit mono" % path)
    x = [v / 32768.0 for v in struct.unpack("<%dh" % frames, w.readframes(frames))]
    if frames < n:
        raise SystemExit("%s: shorter than one window" % path)
    hann = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]
    power = [0.0] * (n // 2 + 1)
    windows = 0
    for start in range(0, frames - n + 1, n // 2):
        seg = [x[start + i] * hann[i] for i in range(n)]
        a = fft(seg)
        for k in range(n // 2 + 1):
            power[k] += a[k].real ** 2 + a[k].imag ** 2
        windows += 1
    lo = int(math.ceil(lo_hz * n / sr))
    hi = int(math.floor(hi_hz * n / sr))
    pk = max(range(lo, hi + 1), key=lambda k: power[k])
    a = math.log(power[pk - 1])
    b = math.log(power[pk])
    c = math.log(power[pk + 1])
    den = a - 2 * b + c
    delta = 0.0 if den == 0 else 0.5 * (a - c) / den
    hz = (pk + delta) * sr / n
    harmonics = []
    for h in range(2, 6):
        k = int(round(h * hz * n / sr))
        if 0 < k <= n // 2:
            harmonics.append((h, 10 * math.log10(power[k] / power[pk])))
    return hz, windows, frames / sr, 10 * math.log10(power[pk] / sum(power)), harmonics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav", nargs="+")
    ap.add_argument("--n", type=int, default=16384)
    ap.add_argument("--lo", type=float, default=100.0)
    ap.add_argument("--hi", type=float, default=2000.0)
    ap.add_argument("--target", type=float, default=None)
    args = ap.parse_args()
    for path in args.wav:
        hz, windows, dur, rel, harmonics = peak_of(path, args.n, args.lo, args.hi)
        line = "%s: peak %.4f Hz | windows %d | %.1fs | %+.2f dB" % (path, hz, windows, dur, rel)
        if args.target:
            line += " | vs %.2f: %+.1f c" % (args.target, 1200 * math.log2(hz / args.target))
        print(line)
        print("   harmonics rel dB: " + ", ".join("h%d %.1f" % h for h in harmonics))


if __name__ == "__main__":
    sys.exit(main())
