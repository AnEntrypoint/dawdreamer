import array
import math
import os
import struct
import sys

ENV_FLOOR = 1e-6
ENV_TAU_S = 0.003
HOLD_MS = 35.0
SETTLE_S = 1.0
ROW_CORPUS = 14
ROW_SINES = 3
F32 = struct.Struct("f")
COLS = "name group gain sr ch bits n rms scaled env task_ready ready ready_t hold nblocks voiced settle first5 last5 zero_t zero_after_ready traced"


def f32(v):
    return F32.unpack(F32.pack(v))[0]


def read_ch0(path):
    with open(path, "rb") as f:
        b = f.read()
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError("not RIFF/WAVE: " + path)
    fmt = None
    q = 12
    while q + 8 <= len(b):
        cid = b[q:q + 4]
        size = int.from_bytes(b[q + 4:q + 8], "little")
        body = q + 8
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", b[body:body + 16])
        if cid == b"data":
            if fmt is None:
                raise ValueError("data before fmt: " + path)
            break
        q = body + size + (size & 1)
    else:
        raise ValueError("no data chunk: " + path)
    channels, sr, bits = fmt[1], fmt[2], fmt[5]
    if bits != 16:
        raise ValueError("%s is %d-bit; the driver reads 16-bit only" % (path, bits))
    align = 2 * channels
    frames = min(size, len(b) - body) // align
    a = array.array("h")
    a.frombytes(b[body:body + frames * align])
    if sys.byteorder == "big":
        a.byteswap()
    return sr, channels, bits, a[0::channels]


def gate_ready(a, sr, gain):
    hold = int(HOLD_MS * 0.001 * sr)
    pole = math.exp(-1.0 / (sr * ENV_TAU_S))
    p = f32(pole)
    c = f32(1.0 - pole)
    g = f32(gain)
    floor = f32(ENV_FLOOR)
    k = 1.0 / 32768.0
    env = 0.0
    run = 0
    first = None
    for i, v in enumerate(a):
        x = f32(v * k * g)
        env = f32(f32(c * f32(x * x)) + f32(p * env))
        run = min(hold, run + 1) if env > floor else 0
        if run >= hold and first is None:
            first = i
    return first, hold


def read_trace(path):
    if not os.path.isfile(path):
        return None
    rows = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) == 2:
                rows.append((float(p[0]), float(p[1])))
    return rows


def analyse_one(group, name, gain, wav, trace_path):
    sr, channels, bits, a = read_ch0(wav)
    n = len(a)
    rms = math.sqrt(math.fsum((v / 32768.0) ** 2 for v in a) / n)
    scaled = gain * rms
    env = scaled * scaled
    first, hold = gate_ready(a, sr, gain)
    ready_t = None if first is None else (first + 1) / sr
    rec = {"group": group, "name": name, "gain": gain, "sr": sr, "ch": channels, "bits": bits, "n": n,
           "rms": rms, "scaled": scaled, "env": env, "task_ready": env > ENV_FLOOR,
           "ready": first is not None, "ready_t": ready_t, "hold": hold}
    rows = read_trace(trace_path)
    if rows is None:
        rec.update(nblocks=0, voiced=0, settle=None, first5=[], last5=[], zero_t=None,
                   zero_after_ready=None, traced=False)
        return rec
    settled = sorted(h for t, h in rows if t >= SETTLE_S - 1e-9 and h > 0)
    zeros = [t for t, h in rows if h == 0.0]
    after = [t for t, h in rows if h == 0.0 and ready_t is not None and t >= ready_t]
    rec.update(nblocks=len(rows), voiced=len(settled),
               settle=settled[len(settled) >> 1] if settled else None,
               first5=[h for _, h in rows[:5]], last5=[h for _, h in rows[-5:]],
               zero_t=zeros[0] if zeros else None,
               zero_after_ready=after[0] if after else None, traced=True)
    return rec


def fmt(x, spec="%.4f"):
    return "-" if x is None else spec % x


def line(r):
    return "\t".join([
        "FILE", r["group"], r["name"], repr(r["gain"]), str(r["sr"]), str(r["ch"]), str(r["bits"]), str(r["n"]),
        "%.6f" % r["rms"], "%.6f" % r["scaled"], "%.3e" % r["env"], "Y" if r["task_ready"] else "N",
        "Y" if r["ready"] else "N", fmt(r["ready_t"]), str(r["hold"]), str(r["nblocks"]), str(r["voiced"]),
        fmt(r["settle"]), ",".join("%.4f" % h for h in r["first5"]), ",".join("%.4f" % h for h in r["last5"]),
        fmt(r["zero_t"]), fmt(r["zero_after_ready"]), "Y" if r["traced"] else "N",
    ])


def summary(recs):
    out = []
    for g in ("corpus", "sine"):
        rs = [r for r in recs if r["group"] == g]
        out.append("SUMMARY %s inputs=%d shipped_ready=%d task_rms_ready=%d voiced_ge1=%d" % (
            g, len(rs), sum(r["ready"] for r in rs), sum(r["task_ready"] for r in rs),
            sum(1 for r in rs if r["voiced"] > 0)))
    out.append("SUMMARY total inputs=%d shipped_ready=%d row_claim=%d (%d corpus + %d sines)" % (
        len(recs), sum(r["ready"] for r in recs), ROW_CORPUS + ROW_SINES, ROW_CORPUS, ROW_SINES))
    for r in recs:
        if r["ready"] and r["voiced"] == 0:
            out.append("UNVOICED %s %s rms=%.6f ready_t=%.4f zero_t=%s zero_after_ready=%s" % (
                r["group"], r["name"], r["rms"], r["ready_t"], fmt(r["zero_t"]), fmt(r["zero_after_ready"])))
    return out


def run(out_path, trace_dir, groups, meta):
    recs = []
    for group, gain, prefix, wavs in groups:
        for wav in wavs:
            base = os.path.basename(wav)[:-4]
            recs.append(analyse_one(group, base, gain, wav, os.path.join(trace_dir, "%s_%s.txt" % (prefix, base))))
    lines = list(meta) + ["COLS " + COLS] + [line(r) for r in recs] + summary(recs)
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    for ln in lines:
        print(ln)
    return recs
