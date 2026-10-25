import glob
import hashlib
import math
import os
import shutil
import subprocess
import sys
import traceback
import wave
import zipfile

import numpy as np

FAUST = "2.85.9"
FAUSTLIB_SHA = "78a72d4998dec43e20492ef9b78d1a785b3dc864"
DSP_SHA = "9afb3b32d5851ae554aaaf513f70dbdcf804257a29c79cc937f0b2f631f8ec8e"
NORM_SHA = "ba2529866947b904772704264fea894971ce3e2c3b0c6ff532de3c4b93288e78"
DATA = "/kaggle/input/datasets/heclgang/mc420-dawdreamer-gate-corpus"
W = "/tmp/resonode-audit"
LIBS = W + "/faust-libs"
BUILD = W + "/build"
NORM = W + "/norm"
OUT = W + "/out"
RESULTS = "/kaggle/working/results.txt"
SR = 48000
PRE = int(0.5 * SR)
TAIL = int(1.0 * SR)
IMP_AT = int(0.1 * SR)
IMP_LEN = int(12.0 * SR)
IMP_AMP = 0.05
VOCALS = ["vocal_female_vibrato", "vocal_male_baritone_scale", "vocal_melody_twinkle_CC0", "vocal_soprano_range_PD", "vocal_tenor_operatic_PD", "vocal_tenor_range_PD"]
FRACS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
DIALS = [
    ("position", 0.0, 1.0, "fx/resonode/position", "K"),
    ("tone", 200.0, 18000.0, "fx/resonode/tone", "M"),
    ("decay", 0.05, 8.0, "fx/resonode/decay", "K"),
    ("damping", 0.05, 1.0, "fx/resonode/damping", "K"),
    ("stretch", -0.5, 1.5, "fx/resonode/stretch", "K"),
    ("collision", 0.0, 1.0, "fx/resonode/collision", "K"),
    ("hardness", 0.0, 1.0, "fx/resonode/hardness", "K"),
    ("body", 0.0, 1.0, "fx/resonode/body", "K"),
]
TONES = [200.0, 600.0, 1800.0, 6000.0, 18000.0]
DECAYS = [0.05, 0.2, 1.2, 3.0, 6.0, 8.0]
SHAPES = ["string", "bell", "plate", "membrane", "bar"]
K_IN = [("fx/resonode/input", 0.0)]
M_IN = [("fx/resonode/input", 1.0)]
STUB = "void *set_curterm(void *t){return 0;} int setupterm(const char *t,int fd,int *e){if(e)*e=0;return -1;} int tigetnum(const char *c){return -1;} int del_curterm(void *t){return 0;}\n"


def log(*parts):
    print(" ".join(str(p) for p in parts), flush=True)


def pv(ok):
    return "PASS" if ok else "FAIL"


def sh(args, cwd=W):
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout, r.stderr


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest):
    rc, _, _ = sh(["curl", "-sfL", "--retry", "3", url, "-o", dest])
    if rc != 0:
        raise SystemExit("fetch failed: " + url)


def read_wav(path):
    with wave.open(path, "rb") as f:
        ch = f.getnchannels()
        raw = f.readframes(f.getnframes())
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch)[:, 0]
    return x


def write_impulse(path):
    data = np.zeros(IMP_LEN, dtype="<i2")
    data[IMP_AT] = int(round(IMP_AMP * 32767))
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(data.tobytes())


def verify_corpus(add):
    rc, o, e = sh([sys.executable, "-I", W + "/fetch_corpus.py", "--verify", DATA])
    add("META corpus_verify rc=%d %s" % (rc, (o.strip().splitlines() or [""])[-1]))
    if rc != 0:
        raise SystemExit("corpus verify failed: " + o[-800:] + e[-400:])
    wavs = sorted(glob.glob(os.path.join(DATA, "mc420", "*.wav")))
    if len(wavs) != 34:
        raise SystemExit("expected 34 corpus wavs, found %d" % len(wavs))
    return wavs


def ensure_node():
    p = shutil.which("node")
    if p is None:
        sh(["bash", "-c", "apt-get update -qq && apt-get install -y -qq nodejs >/dev/null 2>&1"])
        p = shutil.which("node")
    if p is None:
        raise SystemExit("node unavailable")
    return p


def normalise(node, add):
    os.makedirs(NORM, exist_ok=True)
    rc, o, e = sh([node, W + "/normalise-corpus.mjs", "--src", os.path.join(DATA, "mc420"), "--out", NORM, "--rms", "0.1"])
    add("META normalise rc=%d %s" % (rc, (o.strip().splitlines() or [e[-300:]])[0]))
    if rc != 0:
        raise SystemExit("normalise failed: " + e[-500:])


def build_toolchain(add):
    lib = W + "/faust-lib"
    src = W + "/faust-src"
    fetch("https://github.com/grame-cncm/faust/releases/download/%s/libfaust-ubuntu-x86_64.zip" % FAUST, W + "/libfaust.zip")
    zipfile.ZipFile(W + "/libfaust.zip").extractall(lib)
    fetch("https://github.com/grame-cncm/faust/archive/refs/tags/%s.tar.gz" % FAUST, W + "/faust.tar.gz")
    os.makedirs(src, exist_ok=True)
    sh(["tar", "-xzf", W + "/faust.tar.gz", "-C", src, "--wildcards", "*/architecture/*"])
    fetch("https://github.com/grame-cncm/faustlibraries/archive/%s.tar.gz" % FAUSTLIB_SHA, W + "/faustlibs.tar.gz")
    os.makedirs(LIBS, exist_ok=True)
    sh(["tar", "-xzf", W + "/faustlibs.tar.gz", "-C", LIBS, "--strip-components=1"])
    sh(["bash", "-c", "(apt-get update -qq && apt-get install -y -qq libncurses-dev) >/dev/null 2>&1"])
    arch = src + "/faust-%s/architecture" % FAUST
    libfaust = lib + "/lib/libfaustwithllvm.a"
    with open(W + "/stub.c", "w") as f:
        f.write(STUB)
    sh(["gcc", "-O2", "-c", "stub.c", "-o", "stub.o"])
    recipes = [("plain", ["-O2", "-std=c++17"], False), ("abi0", ["-O2", "-std=c++17", "-D_GLIBCXX_USE_CXX11_ABI=0"], False), ("stub", ["-O2", "-std=c++17"], True)]
    for rname, cflags, stub in recipes:
        cmd = ["g++"] + cflags + ["-I", arch, "-I", lib, "faust_cli.cpp"] + (["stub.o"] if stub else [])
        cmd += [libfaust, "-lz", "-lpthread", "-ldl", "-lm"] + ([] if stub else ["-ltinfo"]) + ["-o", "faust_cli"]
        rc, o, e = sh(cmd)
        add("META faust_cli_link %s rc=%d" % (rname, rc))
        if rc == 0:
            return arch, rname
    raise SystemExit("faust_cli link failed")


def compile_dsp(arch, add):
    os.makedirs(BUILD, exist_ok=True)
    shutil.copy(W + "/resonode_synth.dsp", BUILD + "/resonode_synth.dsp")
    os.environ["FAUST_LIBRARY_DIR"] = LIBS
    rc, o, e = sh([W + "/faust_cli", "-lang", "cpp", "-vec", "-fun", "-dfs", "-vs", "32", "-nvi", "-ct", "0", "-I", LIBS, "resonode_synth.dsp", "-o", "dsp.cpp"], cwd=BUILD)
    add("META faust_cli_compile rc=%d %s" % (rc, (e or o)[-300:].replace("\n", " | ")))
    if rc != 0 or not os.path.isfile(BUILD + "/dsp.cpp"):
        raise SystemExit("faust_cli compile failed")
    add("META dsp_cpp_sha256 %s" % sha256(BUILD + "/dsp.cpp"))


def build_driver(arch, add):
    driver = open(W + "/render_cpp_driver.cpp").read()
    variants = [driver, "".join(l for l in driver.splitlines(keepends=True) if l.strip() != "#include <faust/dsp/dsp.h>")]
    err = ""
    for text in variants:
        with open(BUILD + "/render_cpp_driver.cpp", "w") as f:
            f.write(text)
        rc, o, e = sh(["g++", "-O3", "-std=c++17", "-I", arch, "render_cpp_driver.cpp", "-o", "render_cpp"], cwd=BUILD)
        err = e
        if rc == 0:
            add("META render_cpp_build ok flags=-O3 -std=c++17")
            return
    raise SystemExit("render_cpp did not build: " + err[-1500:])


def job(name, length, sets, inp="-", pre=0, events=()):
    return {"name": name, "len": int(length), "pre": int(pre), "in": inp, "sets": list(sets), "events": list(events)}


def key(note, gate):
    return [("fx/resonodevoice0/note", float(note)), ("fx/resonodevoice0/gate", float(gate)), ("fx/resonodevoice0/vel", 1.0)]


def write_jobs(path, jobs):
    with open(path, "w") as f:
        for j in jobs:
            f.write("job %s\nlen %d\npre %d\nin %s\n" % (j["name"], j["len"], j["pre"], j["in"]))
            for p, v in j["sets"]:
                f.write("set 0 %s %.9g\n" % (p, v))
            for fr, p, v in j["events"]:
                f.write("set %d %s %.9g\n" % (fr, p, v))


def run_jobs(jobfile, outdir, add, label):
    os.makedirs(outdir, exist_ok=True)
    rc, o, e = sh([BUILD + "/render_cpp", "--ctl", jobfile, outdir], cwd=BUILD)
    add("META ctl %s rc=%d" % (label, rc))
    if rc != 0:
        raise SystemExit("ctl render failed rc=%d: %s" % (rc, e[-6000:]))


def fo(name, d):
    return np.fromfile(os.path.join(d, name + ".f32"), dtype=np.float32).astype(np.float64)


def frames(x, n=2048, hop=512):
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    idx = np.arange(0, len(x) - n + 1, hop)
    return np.stack([x[i:i + n] for i in idx]) * np.hanning(n)


def db_spec(x):
    return 10.0 * np.log10(np.abs(np.fft.rfft(frames(x), axis=1)) ** 2 + 1e-10)


def lsd(a, b):
    m = min(len(a), len(b))
    A = db_spec(a[:m])
    B = db_spec(b[:m])
    return float(np.mean(np.sqrt(np.mean((A - B) ** 2, axis=1))))


def centroid(x, warm=0.2):
    seg = x[int(warm * SR):]
    if len(seg) < 256:
        seg = x
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1.0 / SR)
    return float(np.sum(f * spec ** 2) / (np.sum(spec ** 2) + 1e-20))


def settled_peak(x, t0=0.3, t1=1.2):
    seg = x[int(t0 * SR):int(t1 * SR)]
    seg = seg * np.hanning(len(seg))
    N = 1 << 18
    mag = np.abs(np.fft.rfft(seg, n=N))
    freqs = np.fft.rfftfreq(N, 1.0 / SR)
    band = np.where((freqs >= 20.0) & (freqs <= 6000.0))[0]
    k = band[int(np.argmax(mag[band]))]
    a = math.log(mag[k - 1] + 1e-30)
    b = math.log(mag[k] + 1e-30)
    c = math.log(mag[k + 1] + 1e-30)
    den = a - 2.0 * b + c
    delta = 0.5 * (a - c) / den if den != 0 else 0.0
    return float(freqs[k] + delta * (freqs[1] - freqs[0]))


def rt60(h, start):
    x = h[start:]
    e = np.cumsum((x * x)[::-1])[::-1]
    if e[0] <= 0:
        return float("nan")
    edb = 10.0 * np.log10(e / e[0] + 1e-30)
    t = np.arange(len(x)) / SR
    sel = (edb <= -5.0) & (edb >= -35.0)
    if np.count_nonzero(sel) < 20:
        return float("nan")
    slope = np.polyfit(t[sel], edb[sel], 1)[0]
    return float(-60.0 / slope)


def env_rms(x, win):
    return np.sqrt(np.convolve(x * x, np.ones(win) / win, mode="same"))


def pearson(a, b):
    a = a - a.mean()
    b = b - b.mean()
    den = math.sqrt(float(np.sum(a * a)) * float(np.sum(b * b)))
    return float(np.sum(a * b) / den) if den > 0 else float("nan")


def frame_centroids(x):
    mag2 = np.abs(np.fft.rfft(frames(x), axis=1)) ** 2
    f = np.fft.rfftfreq(2048, 1.0 / SR)
    tot = mag2.sum(axis=1)
    return (mag2 * f).sum(axis=1) / np.maximum(tot, 1e-30), tot


def onset(x, win=240, frac=0.1):
    e = env_rms(x, win)
    return int(np.argmax(e >= frac * e.max()))


def ltas(x):
    return np.mean(10.0 * np.log10(np.abs(np.fft.rfft(frames(x), axis=1)) ** 2 + 1e-10), axis=0)


def ltas_dist(a, b):
    return float(np.sqrt(np.mean((ltas(a) - ltas(b)) ** 2)))


def band_db(x, lo=2000.0, hi=8000.0):
    p = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return 10.0 * np.log10(float(p[(f >= lo) & (f <= hi)].sum()) + 1e-30)


def plan(vlen):
    vocal = {v: NORM + "/" + v + ".wav" for v in VOCALS}
    female = VOCALS[0]
    Lf = PRE + vlen[female]
    jobs = []
    for dn, lo, hi, path, mode in DIALS:
        inp = vocal[female] if mode == "M" else "-"
        base = (M_IN if mode == "M" else K_IN) + key(60, 1)
        for i, fr in enumerate(FRACS):
            b = lo + fr * (hi - lo)
            s = b + 0.01 * (hi - lo)
            jobs.append(job("p2_%s_%d_a" % (dn, i), 2.0 * SR, base + [(path, b)], inp=inp))
            jobs.append(job("p2_%s_%d_b" % (dn, i), 2.0 * SR, base + [(path, s)], inp=inp))
    jobs.append(job("f1_tone200_K", 1.5 * SR, K_IN + key(60, 1) + [("fx/resonode/tone", 200.0)]))
    jobs.append(job("f1_tone18000_K", 1.5 * SR, K_IN + key(60, 1) + [("fx/resonode/tone", 18000.0)]))
    jobs.append(job("f2_hard0_M", 2.0 * SR, M_IN + key(60, 1) + [("fx/resonode/hardness", 0.0)], inp=vocal[female]))
    jobs.append(job("f2_hard1_M", 2.0 * SR, M_IN + key(60, 1) + [("fx/resonode/hardness", 1.0)], inp=vocal[female]))
    for n in range(36, 97):
        jobs.append(job("p3_n%d" % n, 1.2 * SR, K_IN + key(n, 1)))
    imp = W + "/impulse.wav"
    for i, d in enumerate(DECAYS):
        jobs.append(job("r1_%d" % i, IMP_LEN, M_IN + key(60, 1) + [("fx/resonode/decay", d)], inp=imp))
    for s in SHAPES:
        weights = [("fx/resonode/shape/" + t, 1.0 if t == s else 0.0) for t in SHAPES]
        jobs.append(job("r2_%s" % s, 1.5 * SR, K_IN + key(60, 1) + weights))
    for vi, v in enumerate(VOCALS):
        for ti, t in enumerate(TONES):
            jobs.append(job("r3_%d_%d" % (vi, ti), PRE + vlen[v], M_IN + key(60, 1) + [("fx/resonode/tone", t)], inp=vocal[v], pre=PRE))
    for vi, v in enumerate(VOCALS):
        jobs.append(job("m_%d" % vi, PRE + vlen[v] + TAIL, M_IN + key(60, 1), inp=vocal[v], pre=PRE))
    jobs.append(job("s_m0_decay005", Lf + TAIL, M_IN + key(60, 1) + [("fx/resonode/decay", 0.05)], inp=vocal[female], pre=PRE))
    jobs.append(job("m4_key", Lf + TAIL, K_IN + key(60, 1)))
    jobs.append(job("g1_nokey", Lf + TAIL, M_IN + key(60, 0), inp=vocal[female], pre=PRE))
    p1 = [
        job("p1_key", 1.5 * SR, K_IN + key(60, 1), events=[(int(0.8 * SR), "fx/resonodevoice0/note", 72.0)]),
        job("p1_mouth", Lf + TAIL, M_IN + key(60, 1), inp=vocal[female], pre=PRE),
    ]
    return jobs, p1


def analyse(add, vlen):
    main = OUT + "/main"
    p1a = OUT + "/p1a"
    p1b = OUT + "/p1b"
    names_p1 = ["p1_key", "p1_mouth"]
    same = sum(1 for n in names_p1 if sha256(p1a + "/" + n + ".f32") == sha256(p1b + "/" + n + ".f32"))
    add("CRIT P1 determinism identical=%d/%d threshold=all verdict=%s" % (same, len(names_p1), pv(same == len(names_p1))))

    dials_pass = 0
    for dn, lo, hi, path, mode in DIALS:
        vals = [lsd(fo("p2_%s_%d_a" % (dn, i), main), fo("p2_%s_%d_b" % (dn, i), main)) for i in range(len(FRACS))]
        med = float(np.median(vals))
        mx = float(max(vals))
        ok = med <= 1.5 and mx <= 6.0
        dials_pass += int(ok)
        add("P2 dial=%s mode=%s median_lsd_db=%.4f max_lsd_db=%.4f verdict=%s" % (dn, mode, med, mx, pv(ok)))
    add("CRIT P2 dial-smoothness dials_pass=%d/%d threshold=median<=1.5,max<=6 verdict=%s" % (dials_pass, len(DIALS), pv(dials_pass == len(DIALS))))

    cents = []
    octave = 0
    for n in range(36, 97):
        f = settled_peak(fo("p3_n%d" % n, main))
        c = 1200.0 * math.log2(f / (440.0 * 2.0 ** ((n - 69) / 12.0)))
        cents.append(c)
        if abs(c) >= 600.0:
            octave += 1
    med = float(np.median(np.abs(cents)))
    ok_p3 = med <= 10.0 and octave == 0
    add("P3 note-cents " + " ".join("%d:%.1f" % (36 + i, c) for i, c in enumerate(cents)))
    add("CRIT P3 note-tracking median_abs_cents=%.3f octave_errors=%d worst_abs_cents=%.2f threshold=median<=10,octaves=0 verdict=%s" % (med, octave, float(max(abs(c) for c in cents)), pv(ok_p3)))

    rts = []
    for i, d in enumerate(DECAYS):
        h = fo("r1_%d" % i, main)
        rts.append(rt60(h, IMP_AT))
        add("R1 decay=%.2f rt60_s=%.4f peak=%.4f" % (d, rts[-1], float(np.max(np.abs(h)))))
    ok = rts[0] <= 0.2 and rts[-1] >= 6.0
    add("CRIT R1 decay-range rt60_min_dial=%.4f rt60_max_dial=%.4f threshold=<=0.2,>=6.0 verdict=%s" % (rts[0], rts[-1], pv(ok)))

    cs = {s: centroid(fo("r2_%s" % s, main)) for s in SHAPES}
    ratio = max(cs.values()) / min(cs.values())
    ok = ratio >= 2.0
    add("R2 centroids_hz " + " ".join("%s=%.1f" % (s, cs[s]) for s in SHAPES))
    add("CRIT R2 timbre-span max_over_min=%.3f threshold=>=2 verdict=%s" % (ratio, pv(ok)))

    spreads = []
    for vi, v in enumerate(VOCALS):
        bands = [band_db(fo("r3_%d_%d" % (vi, ti), main)[PRE:]) for ti in range(len(TONES))]
        spreads.append(max(bands) - min(bands))
        add("R3 vocal=%s band_2to8k_db " % v + " ".join("%.1f" % b for b in bands))
    med = float(np.median(spreads))
    ok = med >= 20.0
    add("CRIT R3 brightness-span median_spread_db=%.2f threshold=>=20 verdict=%s" % (med, pv(ok)))

    r1s, r2s, lats = [], [], []
    for vi, v in enumerate(VOCALS):
        L = PRE + vlen[v]
        x_in = np.concatenate([np.zeros(PRE), read_wav(NORM + "/" + v + ".wav")])
        out = fo("m_%d" % vi, main)
        r1 = pearson(env_rms(x_in, 960)[PRE:L], env_rms(out, 960)[PRE:L])
        cin, pin = frame_centroids(x_in)
        cout, _ = frame_centroids(out[:L])
        mask = pin >= 1e-4 * pin.max()
        r2 = pearson(cin[mask], cout[mask])
        lat = (onset(out) - onset(x_in)) * 1000.0 / SR
        r1s.append(r1)
        r2s.append(r2)
        lats.append(lat)
        add("M vocal=%s env_r=%.4f centroid_r=%.4f latency_ms=%.2f peak=%.4f" % (v, r1, r2, lat, float(np.max(np.abs(out)))))
    ok1 = float(np.median(r1s)) >= 0.8
    add("CRIT M1 envelope-follow median_r=%.4f min_r=%.4f threshold=>=0.8 verdict=%s" % (float(np.median(r1s)), float(min(r1s)), pv(ok1)))
    ok2 = float(np.median(r2s)) >= 0.5
    add("CRIT M2 spectral-follow median_r=%.4f min_r=%.4f threshold=>=0.5 verdict=%s" % (float(np.median(r2s)), float(min(r2s)), pv(ok2)))
    ok3 = float(np.median(np.abs(lats))) <= 10.0
    add("CRIT M3 latency median_abs_ms=%.2f signed_ms=%s threshold=<=10 verdict=%s" % (float(np.median(np.abs(lats))), ",".join("%.2f" % x for x in lats), pv(ok3)))

    Lf = PRE + vlen[VOCALS[0]]
    Lm = PRE + vlen[VOCALS[1]]
    o_f = fo("m_0", main)[PRE:Lf]
    o_m = fo("m_1", main)[PRE:Lm]
    o_k = fo("m4_key", main)[PRE:Lf]
    da = ltas_dist(o_f, o_m)
    db = ltas_dist(o_f, o_k)
    ok4 = da >= 1.0 and db >= 1.0
    add("CRIT M4 keys-with-mouth ltas_female_vs_male_db=%.3f ltas_female_vs_nokey_db=%.3f threshold=both>=1 verdict=%s" % (da, db, pv(ok4)))

    s_r = pearson(env_rms(np.concatenate([np.zeros(PRE), read_wav(NORM + "/" + VOCALS[0] + ".wav")]), 960)[PRE:Lf], env_rms(fo("s_m0_decay005", main), 960)[PRE:Lf])
    add("S1 sensitivity vocal=%s decay=0.05 env_r=%.4f (not a criterion)" % (VOCALS[0], s_r))

    g1 = fo("g1_nokey", main)
    g1p = float(np.max(np.abs(g1)))
    gk = float(np.max(np.abs(fo("m_0", main))))
    add("G1 key-free mouth: nokey_peak=%.3e keyed_peak=%.4f gap_confirmed=%s" % (g1p, gk, str(g1p < 1e-6)))
    add("G2 mouth pitch as pitch or timbre: no test; no pitch estimator on the input in the DSP (freqGlide uses the note only)")

    f1 = lsd(fo("f1_tone200_K", main), fo("f1_tone18000_K", main))
    add("F1 tone-inert-without-mouth K lsd_200_vs_18000_db=%.4f inert=%s" % (f1, str(f1 < 0.01)))
    f2 = lsd(fo("f2_hard0_M", main), fo("f2_hard1_M", main))
    add("F2 hardness-inert-with-mouth M lsd_hard0_vs_1_db=%.4f inert=%s" % (f2, str(f2 < 0.01)))

    verdicts = [same == len(names_p1), dials_pass == len(DIALS), ok_p3, rts[0] <= 0.2 and rts[-1] >= 6.0, ratio >= 2.0, float(np.median(spreads)) >= 20.0, ok1, ok2, ok3, ok4]
    add("SUMMARY criteria_pass=%d/%d" % (sum(1 for v in verdicts if v), len(verdicts)))


def run(add):
    add("META resonode-audit faust=%s libfaust-ubuntu-x86_64 faustlibraries=%s flags=-vec -fun -dfs -vs 32 -nvi -ct 0 g++=-O3" % (FAUST, FAUSTLIB_SHA))
    if sha256(W + "/resonode_synth.dsp") != DSP_SHA:
        raise SystemExit("dsp sha mismatch")
    add("META dsp_sha256 %s match" % DSP_SHA)
    if sha256(W + "/normalise-corpus.mjs") != NORM_SHA:
        raise SystemExit("normaliser sha mismatch")
    add("META normaliser_sha256 %s match" % NORM_SHA)
    verify_corpus(add)
    node = ensure_node()
    normalise(node, add)
    vlen = {v: len(read_wav(NORM + "/" + v + ".wav")) for v in VOCALS}
    for v in VOCALS:
        add("META vocal %s frames %d sha256 %s" % (v, vlen[v], sha256(NORM + "/" + v + ".wav")))
    arch, recipe = build_toolchain(add)
    add("META faust_cli_recipe %s" % recipe)
    compile_dsp(arch, add)
    build_driver(arch, add)
    write_impulse(W + "/impulse.wav")
    jobs, p1 = plan(vlen)
    write_jobs(W + "/p1.txt", p1)
    write_jobs(W + "/main.txt", jobs)
    add("META jobs main=%d p1=%d" % (len(jobs), len(p1)))
    run_jobs(W + "/p1.txt", OUT + "/p1a", add, "p1a")
    run_jobs(W + "/p1.txt", OUT + "/p1b", add, "p1b")
    run_jobs(W + "/main.txt", OUT + "/main", add, "main")
    analyse(add, vlen)


def main():
    R = []

    def add(line):
        R.append(line)
        log(line)

    try:
        run(add)
    except BaseException as ex:
        add("FAILED %s" % ex)
        add(traceback.format_exc()[-1500:])
    finally:
        os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
        with open(RESULTS, "w") as f:
            f.write("\n".join(R) + "\n")
        shutil.rmtree(W, ignore_errors=True)


main()
