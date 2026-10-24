#!/usr/bin/env python3
"""Fetch the shared gate corpus and verify every file against its manifest.

usage: fetch_corpus.py [dest]

Downloads heclgang/mc420-dawdreamer-gate-corpus with the kaggle CLI and
checks each wav against manifest.sha256, so both projects measure the
same bytes. A mismatch is reported per file and exits nonzero, because a
corpus that drifted silently invalidates every gate number taken from it.

The dataset is private by default. Make it public only with an explicit
decision; the mc-420 corpus carries per-file licences in its own
instruments/manifest.json.
"""
import hashlib
import os
import subprocess
import sys

SLUG = "heclgang/mc420-dawdreamer-gate-corpus"
DEST = sys.argv[1] if len(sys.argv) > 1 else "corpus"


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
    return r.returncode


def main():
    os.makedirs(DEST, exist_ok=True)
    if sh("kaggle datasets download -d %s -p %s --unzip" % (SLUG, DEST)) != 0:
        print("download failed; is the kaggle CLI on PATH and authenticated?")
        return 1

    manifest = os.path.join(DEST, "manifest.sha256")
    if not os.path.exists(manifest):
        print("no manifest.sha256 in the dataset")
        return 1

    bad = []
    checked = 0
    for line in open(manifest):
        parts = line.split()
        if len(parts) != 2:
            continue
        want, rel = parts
        path = os.path.join(DEST, rel)
        if not os.path.exists(path):
            bad.append((rel, "missing"))
            continue
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        got = h.hexdigest()
        checked += 1
        if got != want:
            bad.append((rel, "sha256 %s != %s" % (got, want)))

    print("checked %d files" % checked)
    for rel, why in bad:
        print("MISMATCH %s: %s" % (rel, why))
    if bad:
        return 1
    print("corpus ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
