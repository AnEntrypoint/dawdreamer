import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SLUG = "heclgang/corpus-gain-witness"
DSP_SHA = "cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0"
DOCKER = "gcr.io/kaggle-images/python@sha256:17b2fc7f27c25c6c2fd4230ec8e66097ab2b89fc88e1e4d6f338b72e1ee0bc3e"

TEMPLATE = r'''
import glob, hashlib, os, shutil, subprocess, sys, zipfile

FAUST = "2.85.9"
FAUSTLIB_SHA = "78a72d4998dec43e20492ef9b78d1a785b3dc864"
DSP_SHA = "cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0"
GAIN_TEXT = "0.00707945784384138"
DATA = "/kaggle/input/datasets/heclgang/mc420-dawdreamer-gate-corpus"
W = "/tmp/corpus-gain-build"
OUTD = os.path.join(W, "out")
SOURCES = __SOURCES__
STUB = "void *set_curterm(void *t){return 0;} int setupterm(const char *t,int fd,int *e){if(e)*e=0;return -1;} int tigetnum(const char *c){return -1;} int del_curterm(void *t){return 0;}\n"
RECIPES = [("plain", ["-O2", "-std=c++17"], False), ("abi0", ["-O2", "-std=c++17", "-D_GLIBCXX_USE_CXX11_ABI=0"], False), ("stub", ["-O2", "-std=c++17"], True)]


def log(*parts):
    print(" ".join(str(p) for p in parts), flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(args, cwd=W):
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout, r.stderr


def fetch(url, dest):
    rc, _, _ = sh(["curl", "-sfL", "--retry", "3", url, "-o", dest], cwd=W)
    if rc != 0:
        raise SystemExit("fetch failed: " + url)


def write(name, text):
    with open(os.path.join(W, name), "w") as f:
        f.write(text)


def main():
    os.makedirs(W, exist_ok=True)
    os.makedirs(OUTD, exist_ok=True)
    for name, text in SOURCES.items():
        write(name, text)
    dsp = os.path.join(W, "pitchtracker_ac.dsp")
    if sha256(dsp) != DSP_SHA:
        raise SystemExit("shipped DSP sha mismatch")
    log("META dsp_sha256", DSP_SHA, "match")

    rc, o, e = sh([sys.executable, "-I", os.path.join(W, "fetch_corpus.py"), "--verify", DATA])
    log("META corpus_verify_rc", rc, (o.strip().splitlines() or [""])[-1])
    if rc != 0:
        raise SystemExit("corpus verify failed: " + o[-800:] + e[-400:])
    corpus = sorted(glob.glob(os.path.join(DATA, "mc420", "*.wav")))
    if len(corpus) != 34:
        raise SystemExit("expected 34 corpus wavs, found %d" % len(corpus))
    for p in corpus:
        log("META input_sha256 corpus", os.path.basename(p)[:-4], sha256(p))

    sines_dir = os.path.join(W, "sines")
    rc, o, e = sh([sys.executable, "-I", os.path.join(W, "make_sines.py"), sines_dir])
    log("META make_sines rc", rc)
    log(o.strip())
    if rc != 0:
        raise SystemExit("make_sines failed: " + e[-400:])
    sines = sorted(glob.glob(os.path.join(sines_dir, "*.wav")))
    if len(sines) != 5:
        raise SystemExit("expected 5 sines, found %d" % len(sines))
    for p in sines:
        log("META input_sha256 generated", os.path.basename(p)[:-4], sha256(p))

    lib = os.path.join(W, "faust-lib")
    src = os.path.join(W, "faust-src")
    libs = os.path.join(W, "faust-libs")
    fetch("https://github.com/grame-cncm/faust/releases/download/%s/libfaust-ubuntu-x86_64.zip" % FAUST, os.path.join(W, "libfaust.zip"))
    zipfile.ZipFile(os.path.join(W, "libfaust.zip")).extractall(lib)
    fetch("https://github.com/grame-cncm/faust/archive/refs/tags/%s.tar.gz" % FAUST, os.path.join(W, "faust.tar.gz"))
    os.makedirs(src, exist_ok=True)
    sh(["tar", "-xzf", os.path.join(W, "faust.tar.gz"), "-C", src, "--wildcards", "*/architecture/*"])
    fetch("https://github.com/grame-cncm/faustlibraries/archive/%s.tar.gz" % FAUSTLIB_SHA, os.path.join(W, "faustlibs.tar.gz"))
    os.makedirs(libs, exist_ok=True)
    sh(["tar", "-xzf", os.path.join(W, "faustlibs.tar.gz"), "-C", libs, "--strip-components=1"])
    sh(["bash", "-c", "(apt-get update -qq && apt-get install -y -qq libncurses-dev) >/dev/null 2>&1"])
    arch = os.path.join(src, "faust-%s" % FAUST, "architecture")
    libfaust = os.path.join(lib, "lib", "libfaustwithllvm.a")
    write("stub.c", STUB)
    sh(["gcc", "-O2", "-c", "stub.c", "-o", "stub.o"])
    chosen = None
    for rname, cflags, stub in RECIPES:
        cmd = ["g++"] + cflags + ["-I", arch, "-I", lib, "faust_cli.cpp"] + (["stub.o"] if stub else [])
        cmd += [libfaust, "-lz", "-lpthread", "-ldl", "-lm"] + ([] if stub else ["-ltinfo"]) + ["-o", "faust_cli"]
        rc, o, e = sh(cmd)
        log("META faust_cli_link", rname, rc, (e or o)[-200:])
        if rc == 0:
            chosen = rname
            break
    if chosen is None:
        raise SystemExit("faust_cli link failed")

    build = os.path.join(W, "build")
    os.makedirs(build, exist_ok=True)
    shutil.copy(dsp, os.path.join(build, "pitchtracker_ac.dsp"))
    os.environ["FAUST_LIBRARY_DIR"] = libs
    rc, o, e = sh([os.path.join(W, "faust_cli"), "-lang", "cpp", "-vec", "-fun", "-dfs", "-vs", "32", "-nvi", "-ct", "0",
                   "-I", libs, "pitchtracker_ac.dsp", "-o", "dsp.cpp"], cwd=build)
    log("META faust_cli_compile rc", rc, (e or o)[-300:])
    if rc != 0 or not os.path.isfile(os.path.join(build, "dsp.cpp")):
        raise SystemExit("faust_cli compile failed")
    log("META dsp_cpp_sha256", sha256(os.path.join(build, "dsp.cpp")))

    driver = SOURCES["render_cpp_driver.cpp"]
    variants = [driver, "".join(l for l in driver.splitlines(keepends=True) if l.strip() != "#include <faust/dsp/dsp.h>")]
    built = False
    for text in variants:
        with open(os.path.join(build, "render_cpp_driver.cpp"), "w") as f:
            f.write(text)
        rc, o, e = sh(["g++", "-O3", "-std=c++17", "-I", arch, "render_cpp_driver.cpp", "-o", "render_cpp"], cwd=build)
        if rc == 0:
            built = True
            break
    log("META render_cpp_build", built)
    if not built:
        raise SystemExit("render_cpp did not build: " + e[-600:])

    corpus_rc, o, e = sh(["./render_cpp", "pitchtracker_ac.dsp", GAIN_TEXT, os.path.join(OUTD, "c")] + corpus, cwd=build)
    log("META render_corpus rc", corpus_rc)
    log(e.strip()[-2000:])
    sine_rc, o, e = sh(["./render_cpp", "pitchtracker_ac.dsp", "1.0", os.path.join(OUTD, "s")] + sines, cwd=build)
    log("META render_sines rc", sine_rc)
    log(e.strip()[-1000:])
    for f in os.listdir(OUTD):
        if f.endswith(".npy"):
            os.remove(os.path.join(OUTD, f))

    sys.path.insert(0, W)
    import analyse
    meta = ["META dsp_sha256 " + DSP_SHA, "META faust_cli_recipe " + chosen, "META gain_corpus " + GAIN_TEXT, "META gain_sines 1.0"]
    analyse.run("/kaggle/working/results.txt", OUTD,
                [("corpus", float(GAIN_TEXT), "c", corpus), ("sine", 1.0, "s", sines)], meta)
    shutil.copytree(OUTD, "/kaggle/working/traces", ignore=shutil.ignore_patterns("*.npy"), dirs_exist_ok=True)


main()
'''


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def main(dsp_path, sines_path, route_dir, outdir):
    dsp = read_bytes(dsp_path)
    if hashlib.sha256(dsp).hexdigest() != DSP_SHA:
        raise SystemExit("shipped sha mismatch")
    sources = {
        "pitchtracker_ac.dsp": dsp.decode("utf-8"),
        "make_sines.py": read_bytes(sines_path).decode("utf-8"),
        "faust_cli.cpp": read_bytes(os.path.join(route_dir, "faust_cli.cpp")).decode("utf-8"),
        "render_cpp_driver.cpp": read_bytes(os.path.join(route_dir, "render_cpp_driver.cpp")).decode("utf-8"),
        "fetch_corpus.py": read_bytes(os.path.join(REPO, "tools", "corpus", "fetch_corpus.py")).decode("utf-8"),
        "analyse.py": read_bytes(os.path.join(HERE, "analyse.py")).decode("utf-8"),
    }
    code = TEMPLATE.replace("__SOURCES__", json.dumps(sources))
    os.makedirs(outdir, exist_ok=True)
    lines = code.lstrip("\n").splitlines(True)
    nb = {
        "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines}],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                     "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    with open(os.path.join(outdir, "corpus-gain-witness.ipynb"), "w") as f:
        json.dump(nb, f)
    meta = {
        "id": SLUG,
        "title": "corpus gain witness",
        "code_file": "corpus-gain-witness.ipynb",
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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
