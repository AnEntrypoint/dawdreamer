import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SLUG = "heclgang/resonode-audit"
DSP_SHA = "9afb3b32d5851ae554aaaf513f70dbdcf804257a29c79cc937f0b2f631f8ec8e"
NORM_SHA = "ba2529866947b904772704264fea894971ce3e2c3b0c6ff532de3c4b93288e78"
DATASET = "heclgang/mc420-dawdreamer-gate-corpus"
DOCKER = "gcr.io/kaggle-images/python@sha256:17b2fc7f27c25c6c2fd4230ec8e66097ab2b89fc88e1e4d6f338b72e1ee0bc3e"

BOOT = r'''
import json, os, subprocess, sys
W = "/tmp/resonode-audit"
SOURCES = __SOURCES__
os.makedirs(W, exist_ok=True)
for name, text in SOURCES.items():
    with open(os.path.join(W, name), "w") as f:
        f.write(text)
rc = subprocess.run([sys.executable, "-I", os.path.join(W, "resonode_audit.py")]).returncode
if rc != 0:
    raise SystemExit("resonode_audit exited %d" % rc)
'''


def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def sha(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(dsp_path, norm_path, outdir):
    if sha(dsp_path) != DSP_SHA:
        raise SystemExit("dsp sha mismatch: " + sha(dsp_path))
    if sha(norm_path) != NORM_SHA:
        raise SystemExit("normaliser sha mismatch: " + sha(norm_path))
    sources = {
        "resonode_synth.dsp": read_text(dsp_path),
        "normalise-corpus.mjs": read_text(norm_path),
        "faust_cli.cpp": read_text(os.path.join(HERE, "faust_cli.cpp")),
        "render_cpp_driver.cpp": read_text(os.path.join(HERE, "render_cpp_driver.cpp")),
        "resonode_audit.py": read_text(os.path.join(HERE, "resonode_audit.py")),
        "fetch_corpus.py": read_text(os.path.join(REPO, "tools", "corpus", "fetch_corpus.py")),
    }
    code = BOOT.replace("__SOURCES__", json.dumps(sources, ensure_ascii=True))
    os.makedirs(outdir, exist_ok=True)
    lines = code.lstrip("\n").splitlines(True)
    nb = {
        "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines}],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                     "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    with open(os.path.join(outdir, "resonode-audit.ipynb"), "w") as f:
        json.dump(nb, f)
    meta = {
        "id": SLUG,
        "title": "resonode audit",
        "code_file": "resonode-audit.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": True,
        "keywords": [],
        "dataset_sources": [DATASET],
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
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
