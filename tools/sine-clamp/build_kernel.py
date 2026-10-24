import hashlib
import json
import os
import sys

import variants

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SLUG = "heclgang/sine-clamp-witness"
MC_HEAD = "b563a62a871bf8cfabbc7510da7ee2ffebc7386d"
SHIPPED_SHA = "cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0"
NORMALISE_SHA = "ba2529866947b904772704264fea894971ce3e2c3b0c6ff532de3c4b93288e78"
DOCKER = "gcr.io/kaggle-images/python@sha256:17b2fc7f27c25c6c2fd4230ec8e66097ab2b89fc88e1e4d6f338b72e1ee0bc3e"

TEMPLATE = r'''
import os, sys, json, math, subprocess, hashlib, time, random, struct, wave, shutil
SRC = __SRC__
DSP = __DSP__
SHIPPED_SHA = __SHIPPED_SHA__
NORM_SHA = __NORM_SHA__
MC_HEAD = __MC_HEAD__
W = "/kaggle/working/sine-clamp"
DATA = "/kaggle/input/datasets/heclgang/mc420-dawdreamer-gate-corpus"
FAUST = "2.85.9"
FAUSTLIB_SHA = "78a72d4998dec43e20492ef9b78d1a785b3dc864"
NAMES = ["S", "A1", "A2", "A3", "B1", "B2", "B3", "C1"]
TAUS = ["0.01", "0.02"]
SR = 48000
SETTLE_S = 1.0
STUB = "void*set_curterm(void*t){return 0;} int setupterm(const char*t,int fd,int*e){if(e)*e=0;return -1;} int tigetnum(const char*c){return -1;} int del_curterm(void*t){return 0;}"
os.makedirs(W, exist_ok=True)
RES = open("/kaggle/working/results.txt", "w")


def emit(*fields):
    line = "\t".join(str(f) for f in fields)
    print(line, flush=True)
    RES.write(line + "\n")
    RES.flush()


def sh(cmd, timeout=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=W, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def last_line(out, err):
    lines = (out.strip() or err.strip()).splitlines()
    return lines[-1] if lines else ""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_wav(path, samples):
    w = wave.open(path, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(b"".join(struct.pack("<h", v) for v in samples))
    w.close()


def load_rows(path):
    rows = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) == 2:
                rows.append((float(p[0]), float(p[1])))
    return rows


def settle_value(rows):
    settled = [(t, h) for t, h in rows if t >= SETTLE_S - 1e-9]
    nonzero = sorted(h for t, h in settled if h > 0)
    value = nonzero[len(nonzero) >> 1] if nonzero else None
    return value, len(rows), len(settled), len(nonzero)


def lag_constant(value):
    if value is None or value <= 0:
        return None
    lag = int(round(SR / value))
    if 2 <= lag <= 3200 and abs(SR / lag - value) < 1e-4:
        return lag
    return None


emit("META", "mc_head", MC_HEAD)
if hashlib.sha256(DSP["S_0.01"].encode()).hexdigest() != SHIPPED_SHA:
    raise SystemExit("shipped DSP sha mismatch")
emit("META", "shipped_sha256", SHIPPED_SHA, "match")
for name, text in SRC.items():
    with open(os.path.join(W, name), "w") as f:
        f.write(text)
    emit("META", "src_sha256", name, sha256(os.path.join(W, name)))
if sha256(os.path.join(W, "normalise-corpus.mjs")) != NORM_SHA:
    raise SystemExit("normaliser sha mismatch")
emit("META", "normaliser_sha256", NORM_SHA, "match")
os.makedirs(os.path.join(W, "dsp"), exist_ok=True)
for key, text in DSP.items():
    path = os.path.join(W, "dsp", key + ".dsp")
    with open(path, "w") as f:
        f.write(text)
    emit("META", "dsp_sha256", key, sha256(path))

rc, out, err = sh("python3 -I %s/fetch_corpus.py --verify %s" % (W, DATA))
emit("META", "corpus_verify_rc", rc, last_line(out, err))
if rc != 0:
    raise SystemExit("corpus verify failed")

rc, out, err = sh("node %s/normalise-corpus.mjs --out %s/scaled --src %s/mc420 --rms 0.1 --floor 1e-6" % (W, W, DATA))
emit("META", "normalise_rc", rc, last_line(out, err))
if rc != 0:
    raise SystemExit("normalise failed")

INP = os.path.join(W, "inputs")
os.makedirs(INP, exist_ok=True)
for f in sorted(os.listdir(os.path.join(W, "scaled"))):
    if f.endswith(".wav"):
        shutil.copy(os.path.join(W, "scaled", f), os.path.join(INP, f))
for f in sorted(os.listdir(os.path.join(DATA, "sines"))):
    if f.endswith(".wav"):
        shutil.copy(os.path.join(DATA, "sines", f), os.path.join(INP, f))
N = 8 * SR
write_wav(os.path.join(INP, "silence.wav"), [0] * N)
rng = random.Random(20261024)
write_wav(os.path.join(INP, "white_noise.wav"), [int(round(max(-0.9, min(0.9, rng.gauss(0.0, 0.1))) * 32767)) for _ in range(N)])
WAVS = sorted(f for f in os.listdir(INP) if f.endswith(".wav"))
for f in WAVS:
    emit("META", "input_sha256", f[:-4], sha256(os.path.join(INP, f)))

sh("(apt-get update -qq && apt-get install -y -qq libncurses-dev) >/dev/null 2>&1")
rc, out, err = sh("curl -sL https://github.com/grame-cncm/faust/releases/download/%s/libfaust-ubuntu-x86_64.zip -o libfaust.zip && mkdir -p faust-lib && unzip -oq libfaust.zip -d faust-lib && ls faust-lib/lib" % FAUST)
emit("META", "libfaust_fetch_rc", rc, last_line(out, err))
rc, out, err = sh("curl -sL https://github.com/grame-cncm/faust/archive/refs/tags/%s.tar.gz -o faust.tar.gz && mkdir -p faust-src && tar -xzf faust.tar.gz -C faust-src --wildcards '*/architecture/*' && ls faust-src" % FAUST)
emit("META", "faust_src_rc", rc, last_line(out, err))
rc, out, err = sh("curl -sL https://github.com/grame-cncm/faustlibraries/archive/%s.tar.gz -o faustlibs.tar.gz && mkdir -p faust-libs && tar -xzf faustlibs.tar.gz -C faust-libs --strip-components=1 && ls faust-libs/stdfaust.lib" % FAUSTLIB_SHA)
emit("META", "faustlibs_rc", rc, last_line(out, err))

def run(args, cwd):
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout, r.stderr


ARCH = os.path.join(W, "faust-src", "faust-%s" % FAUST, "architecture")
LIBFAUST = os.path.join(W, "faust-lib", "lib", "libfaustwithllvm.a")
FAUSTLIBS = os.path.join(W, "faust-libs")
FAUST_CLI = os.path.join(W, "faust_cli")
with open(os.path.join(W, "stub.c"), "w") as f:
    f.write(STUB)
run(["gcc", "-O2", "-c", "stub.c", "-o", "stub.o"], W)
RECIPES = [
    ("plain", ["-O2", "-std=c++17"], False),
    ("abi0", ["-O2", "-std=c++17", "-D_GLIBCXX_USE_CXX11_ABI=0"], False),
    ("stub", ["-O2", "-std=c++17"], True),
]
for rname, cflags, stub in RECIPES:
    cmd = ["g++"] + cflags + ["-I", ARCH, "-I", os.path.join(W, "faust-lib"), os.path.join(W, "faust_cli.cpp")]
    if stub:
        cmd += [os.path.join(W, "stub.o")]
    cmd += [LIBFAUST, "-lz", "-lpthread", "-ldl", "-lm"]
    if not stub:
        cmd += ["-ltinfo"]
    rc, out, err = run(cmd + ["-o", FAUST_CLI], W)
    emit("META", "faust_cli_recipe", rname, rc, last_line(out, err))
    if rc == 0:
        break
emit("META", "faust_cli_build_rc", rc)
if rc != 0:
    raise SystemExit("faust_cli build failed")

for v in NAMES:
    for tau in TAUS:
        key = "%s_%s" % (v, tau)
        outdir = os.path.join(W, "out", key)
        os.makedirs(outdir, exist_ok=True)
        dsp_path = os.path.join(W, "dsp", key + ".dsp")
        bdir = os.path.join(W, "build", key)
        os.makedirs(bdir, exist_ok=True)
        t0 = time.time()
        frc, fout, ferr = run([FAUST_CLI, "-lang", "cpp", "-vec", "-fun", "-dfs", "-vs", "32", "-nvi", "-ct", "0", "-I", FAUSTLIBS, dsp_path, "-o", "dsp.cpp"], bdir)
        with open(os.path.join(bdir, "faust.log"), "w") as f:
            f.write(fout + ferr)
        cpp_path = os.path.join(bdir, "dsp.cpp")
        cpp_sha = sha256(cpp_path) if os.path.exists(cpp_path) else "none"
        drc = 1
        dout = derr = ""
        if frc == 0:
            shutil.copy(os.path.join(W, "render_cpp_driver.cpp"), os.path.join(bdir, "render_cpp_driver.cpp"))
            drc, dout, derr = run(["g++", "-O3", "-std=c++17", "-I", ARCH, "render_cpp_driver.cpp", "-o", "render_cpp"], bdir)
            with open(os.path.join(bdir, "gxx.log"), "w") as f:
                f.write(dout + derr)
        emit("BUILD", v, tau, frc, drc, cpp_sha, round(time.time() - t0, 1))
        if frc != 0 or drc != 0:
            emit("RUN", v, tau, sha256(dsp_path), "build_failed", round(time.time() - t0, 1))
            continue
        t1 = time.time()
        try:
            r = subprocess.run([os.path.join(bdir, "render_cpp"), dsp_path, "1.0", os.path.join(outdir, "g")] + [os.path.join(INP, f) for f in WAVS], capture_output=True, text=True, timeout=3600, cwd=bdir)
            rc, log = r.returncode, r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            rc, log = "timeout", ""
        with open(os.path.join(W, "log_%s.txt" % key), "w") as f:
            f.write(log)
        emit("RUN", v, tau, sha256(dsp_path), rc, round(time.time() - t1, 1))
        for f in WAVS:
            base = f[:-4]
            path = os.path.join(outdir, "g_%s.txt" % base)
            if not os.path.exists(path):
                emit("ROW", v, tau, base, 0, 0, 0, "null", "null")
                continue
            value, nb, ns, nn = settle_value(load_rows(path))
            lag = lag_constant(value)
            emit("ROW", v, tau, base, nb, ns, nn, "null" if value is None else repr(value), "null" if lag is None else lag)
        for f in os.listdir(outdir):
            if f.endswith(".npy"):
                os.remove(os.path.join(outdir, f))
emit("DONE")
RES.close()
'''


def read(path):
    with open(path) as f:
        return f.read()


def main(shipped_path, normalise_path, outdir):
    shipped = read(shipped_path)
    if hashlib.sha256(shipped.encode()).hexdigest() != SHIPPED_SHA:
        raise SystemExit("shipped sha mismatch")
    normalise = read(normalise_path)
    if hashlib.sha256(normalise.encode()).hexdigest() != NORMALISE_SHA:
        raise SystemExit("normaliser sha mismatch")
    dsps = {}
    for name in variants.NAMES:
        for tau in variants.TAUS:
            dsps[variants.key(name, tau)] = variants.build(shipped, name, tau)
    if dsps["S_0.01"] != shipped:
        raise SystemExit("S_0.01 is not the shipped text")
    src = {
        "fetch_corpus.py": read(os.path.join(REPO, "tools", "corpus", "fetch_corpus.py")),
        "render_cpp_driver.cpp": read(os.path.join(REPO, "tools", "sine-clamp", "render_cpp_driver.cpp")),
        "faust_cli.cpp": read(os.path.join(REPO, "tools", "sine-clamp", "faust_cli.cpp")),
        "normalise-corpus.mjs": normalise,
    }
    code = (
        TEMPLATE.replace("__SRC__", json.dumps(src))
        .replace("__DSP__", json.dumps(dsps))
        .replace("__SHIPPED_SHA__", repr(SHIPPED_SHA))
        .replace("__NORM_SHA__", repr(NORMALISE_SHA))
        .replace("__MC_HEAD__", repr(MC_HEAD))
    )
    os.makedirs(outdir, exist_ok=True)
    lines = code.lstrip("\n").splitlines(True)
    nb = {
        "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines}],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}, "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    with open(os.path.join(outdir, "sine-clamp-witness.ipynb"), "w") as f:
        json.dump(nb, f)
    meta = {
        "id": SLUG,
        "title": "sine clamp witness",
        "code_file": "sine-clamp-witness.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": True,
        "keywords": [],
        "dataset_sources": ["heclgang/mc420-dawdreamer-gate-corpus"],
        "kernel_sources": [],
        "competition_sources": [],
        "model_sources": [],
        "docker_image": DOCKER,
        "machine_shape": "None",
    }
    with open(os.path.join(outdir, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    for key in sorted(dsps):
        print("%s %s" % (hashlib.sha256(dsps[key].encode()).hexdigest(), key))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
