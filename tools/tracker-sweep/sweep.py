#!/usr/bin/env python3
import hashlib
import json
import math
import os
import shutil
import statistics
import struct
import subprocess
import sys
import time
import wave
import zipfile

PINNED = "-vec -fun -dfs -vs 32 -nvi -ct 0"
LIBFAUST_URL = "https://github.com/grame-cncm/faust/releases/download/2.85.9/libfaust-ubuntu-x86_64.zip"
TARGETS = {
    "piano_mid_C4": 262.22,
    "marimba_low_C2B2": 65.21,
    "cello_low_sulC_A2": 111.76,
    "trumpet_high_C6": 1049.13,
    "soprano_sax_high_C6": 1049.13,
    "clarinet_high_C6B6": 1049.13,
    "bassoon_low_C2B2": 69.68,
    "violin_low_sulG_G3B3": 196.64,
    "trumpet_low_A3": 218.35,
    "guitar_pluck_C4B4": 294.53,
}
S3_FILES = ("cello_low_sulC_A2", "trumpet_low_A3", "piano_mid_C4")
SINES = {"sine_65.55": 65.55, "sine_69.75": 69.75, "sine_440": 440.0, "sine_1000": 1000.0, "sine_2093": 2093.0}

SHIPPED_TAU = "tauFor(freqHz) = ba.if(freqHz >= 575.0, 0.02,\n                  0.01);"
SHIPPED_REFINE_TAU = "    energyTau = 0.01;"
SHIPPED_SPREAD = "refineSpreadK(L) = int(refineSpreadRatio * float(L) + 0.5) : max(refineSpreadFloor) : min(refineSpreadMax);"
SHIPPED_MARGIN = "subharmDominanceMargin = 0.004;"
SHIPPED_ONSET = "onsetHoldMs = 35.0;"
SHIPPED_GATE = "    confident = finalConfidence >= corrThresh;"


def subs_for(axis, value):
    table = {
        "coarse": [(SHIPPED_TAU, "tauFor(freqHz) = %s;" % value)],
        "refine": [(SHIPPED_REFINE_TAU, "    energyTau = %s;" % value)],
        "spread": [(SHIPPED_SPREAD, "refineSpreadK(L) = %s;" % value)],
        "margin": [(SHIPPED_MARGIN, "subharmDominanceMargin = %s;" % value)],
        "onset": [(SHIPPED_ONSET, "onsetHoldMs = %s;" % value)],
        "gate": [(SHIPPED_GATE, "    confident = finalConfidence >= %s;" % value)],
    }
    return table[axis]


def make_sines(outdir):
    os.makedirs(outdir, exist_ok=True)
    sr, n = 48000, 3 * 48000
    for name, hz in SINES.items():
        frames = b"".join(
            struct.pack("<h", round(0.3 * math.sin(2 * math.pi * hz * i / sr) * 32767)) for i in range(n)
        )
        with wave.open(os.path.join(outdir, name + ".wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(frames)


def read_trace(path):
    rows = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) == 2:
                rows.append((float(p[0]), float(p[1])))
    return rows


def settled(rows):
    vals = [hz for t, hz in rows if t >= 1.0 and hz != 0.0]
    return statistics.median(vals) if vals else 0.0


def cents(hz, target):
    return 1200.0 * math.log2(hz / target)


def find_libfaust(libroot):
    inc = lib = None
    for dp, _, fn in os.walk(libroot):
        if "llvm-dsp.h" in fn and dp.endswith(os.path.join("faust", "dsp")):
            inc = os.path.dirname(os.path.dirname(dp))
        if "libfaustwithllvm.a" in fn:
            lib = os.path.join(dp, "libfaustwithllvm.a")
    if not inc or not lib:
        raise SystemExit("libfaust layout not found under %s" % libroot)
    return inc, lib


def wav_names(spec):
    if spec["wavs"] == "all":
        return sorted(f[:-4] for f in os.listdir(os.path.join(spec["input_root"], "wav")) if f.endswith(".wav"))
    return spec["wavs"]


def run(spec_path):
    spec = json.load(open(spec_path))
    root, work = spec["input_root"], spec["work"]
    os.makedirs(work, exist_ok=True)
    libroot = os.path.join(work, "libfaust")
    if not os.path.exists(os.path.join(libroot, ".extracted")):
        zip_local = os.path.join(work, "libfaust-ubuntu-x86_64.zip")
        if not os.path.exists(zip_local):
            subprocess.run(["curl", "-fL", "-sS", "-o", zip_local, LIBFAUST_URL], check=True)
        with open(zip_local, "rb") as fz:
            print("libfaust zip sha256 %s bytes %d" % (hashlib.sha256(fz.read()).hexdigest(), os.path.getsize(zip_local)), flush=True)
        with zipfile.ZipFile(zip_local) as z:
            z.extractall(libroot)
        open(os.path.join(libroot, ".extracted"), "w").close()
    inc, lib = find_libfaust(libroot)
    exe = os.path.join(work, "render_sweep")
    if not os.path.exists(exe):
        subprocess.run(
            ["g++", "-O2", "-std=c++17", "-I", inc, os.path.join(root, "render_sweep.cpp"), lib,
             "-lz", "-lpthread", "-ldl", "-lm", "-ltinfo", "-o", exe],
            check=True,
        )
    wavs = wav_names(spec)
    srcs = {}
    log = open(os.path.join(work, "run.log"), "a")
    for v in spec["variants"]:
        if v["dsp"] not in srcs:
            srcs[v["dsp"]] = open(os.path.join(root, "dsp", v["dsp"] + ".dsp")).read()
        text = srcs[v["dsp"]]
        for old, new in v.get("subs", []):
            cnt = text.count(old)
            if cnt != 1:
                raise SystemExit("%s: substitution matched %d times: %r" % (v["name"], cnt, old[:60]))
            text = text.replace(old, new)
        dsp_dir = os.path.join(work, "dsp")
        os.makedirs(dsp_dir, exist_ok=True)
        dsp_path = os.path.join(dsp_dir, v["name"] + ".dsp")
        with open(dsp_path, "w") as f:
            f.write(text)
        tdir = os.path.join(work, "traces", v["name"])
        os.makedirs(tdir, exist_ok=True)
        env = dict(os.environ)
        env["FAUST_LIBRARY_DIR"] = os.path.join(root, "faustlibraries")
        env["FAUST_FLAGS"] = PINNED if v["flags"] == "pinned" else ""
        t0 = time.time()
        proc = subprocess.run(
            [exe, dsp_path, str(spec["gain"]), tdir] + [os.path.join(root, "wav", w + ".wav") for w in wavs],
            env=env, capture_output=True, text=True,
        )
        dt = time.time() - t0
        log.write("%s rc=%d secs=%.1f\n%s%s\n" % (v["name"], proc.returncode, dt, proc.stderr, proc.stdout))
        log.flush()
        print("%s rc=%d secs=%.1f" % (v["name"], proc.returncode, dt), flush=True)
    log.close()
    summarize(spec_path)


def settled_map(tdir, wavs):
    out = {}
    for w in wavs:
        p = os.path.join(tdir, w + ".txt")
        out[w] = settled(read_trace(p)) if os.path.exists(p) else None
    return out


def sweep_metrics(vals, base_vals):
    err = {f: cents(vals[f], TARGETS[f]) for f in TARGETS if vals.get(f)}
    base_err = {f: cents(base_vals[f], TARGETS[f]) for f in TARGETS if base_vals.get(f)}
    absd = [abs(e) for e in err.values()]
    med = statistics.median(absd) if absd else None
    base_med = statistics.median([abs(e) for e in base_err.values()]) if base_err else None
    octs = sum(1 for e in err.values() if abs(e) > 600.0)
    s3 = {}
    for f in S3_FILES:
        c, b = err.get(f), base_err.get(f)
        s3[f] = {
            "cents": c,
            "base": b,
            "i": c is not None and abs(c) <= 25.0,
            "ii": c is not None and b is not None and abs(c) - abs(b) <= 25.0,
        }
    gain = (base_med - med) if (med is not None and base_med is not None) else None
    s1 = med is not None and med <= 20.0
    s2 = octs == 0
    s3ok = all(v["i"] and v["ii"] for v in s3.values())
    s4 = gain is not None and gain >= 2.0
    return {
        "voiced": len(err),
        "med": med,
        "octaves": octs,
        "s3": s3,
        "s3ok": s3ok,
        "gain": gain,
        "s1": s1,
        "s2": s2,
        "s4": s4,
        "pass": s1 and s2 and s3ok and s4,
        "err": err,
    }


def fmt(x, nd=2):
    return "-" if x is None else ("%." + str(nd) + "f") % x


def summarize(spec_path):
    spec = json.load(open(spec_path))
    root, work = spec["input_root"], spec["work"]
    wavs = wav_names(spec)
    tr = os.path.join(work, "traces")
    lines, out = [], {}
    if spec["report"] == "flag":
        for a, b in spec["pairs"]:
            lines.append("PAIR %s vs %s (block-end Hz, exact float match)" % (a, b))
            for w in spec["wavs"]:
                ra = read_trace(os.path.join(tr, a, w + ".txt"))
                rb = read_trace(os.path.join(tr, b, w + ".txt"))
                n = min(len(ra), len(rb))
                mism = sum(1 for i in range(n) if ra[i][1] != rb[i][1])
                mx = max((abs(ra[i][1] - rb[i][1]) for i in range(n)), default=0.0)
                sa, sb = settled(ra), settled(rb)
                same = len(ra) == len(rb) and mism == 0
                lines.append("  %-16s blocks %d/%d mismatched %d max_abs_diff_Hz %.9g settled %.9g %.9g identical %s"
                             % (w, len(ra), len(rb), mism, mx, sa, sb, same))
                out.setdefault("flag", []).append({"wav": w, "a": a, "b": b, "blocks": n, "mismatched": mism,
                                                   "max_abs_diff_hz": mx, "settled_a": sa, "settled_b": sb,
                                                   "identical": same})
    elif spec["report"] == "lowfreq":
        lines.append("LOWFREQ recheck, gain %s, target = exact sine frequency" % spec["gain"])
        for w in spec["wavs"]:
            f = SINES[w]
            sa = settled(read_trace(os.path.join(tr, "A", w + ".txt")))
            sb = settled(read_trace(os.path.join(tr, "B", w + ".txt")))
            ca, cb = cents(sa, f), cents(sb, f)
            bma = 1200.0 * math.log2(sb / sa)
            lines.append("  %-12s A settled %.6f c %+.3f | B settled %.6f c %+.3f | B-A %+.3f c | |cA|-|cB| %+.3f c"
                         % (w, sa, ca, sb, cb, bma, abs(ca) - abs(cb)))
            out.setdefault("lowfreq", []).append({"wav": w, "freq": f, "A_settled": sa, "A_cents": ca,
                                                  "B_settled": sb, "B_cents": cb, "B_minus_A_cents": bma,
                                                  "accuracy_gain_c": abs(ca) - abs(cb)})
    elif spec["report"] == "sweep":
        base_vals = settled_map(os.path.join(tr, "baseline"), wavs)
        results = []
        for v in spec["variants"]:
            vals = settled_map(os.path.join(tr, v["name"]), wavs)
            m = sweep_metrics(vals, base_vals)
            m.update({"name": v["name"], "axis": v.get("axis", "baseline"), "path": v.get("path", "-"),
                      "value": v.get("value", "-"), "per_file": vals,
                      "sines": {w: (cents(vals[w], SINES[w]) if vals.get(w) else None) for w in SINES if w in vals}})
            results.append(m)
        lines.append("%-22s %-7s %-7s %-7s %3s %8s %3s %8s %8s %8s %-5s %-5s %-5s %-5s %8s %-5s" % (
            "config", "axis", "path", "value", "vc", "medAbsC", "oct", "cello", "trumpLA3", "piano", "S1", "S2", "S3", "S4", "gainC", "PASS"))
        for m in results:
            s3 = m["s3"]
            lines.append("%-22s %-7s %-7s %-7s %3d %8s %3d %8s %8s %8s %-5s %-5s %-5s %-5s %8s %-5s" % (
                m["name"], m["axis"], m["path"], m["value"], m["voiced"], fmt(m["med"]), m["octaves"],
                fmt(s3["cello_low_sulC_A2"]["cents"]), fmt(s3["trumpet_low_A3"]["cents"]),
                fmt(s3["piano_mid_C4"]["cents"]), m["s1"], m["s2"], m["s3ok"], m["s4"], fmt(m["gain"]), m["pass"]))
        lines.append("per-file settled Hz and cents vs certified peak (scored), then sines (outside S1-S2)")
        for m in results:
            cells = []
            for w in list(TARGETS) + list(SINES):
                if w in TARGETS:
                    c = m["err"].get(w)
                    cells.append("%s=%s" % (w, "unvoiced" if c is None else "%+.2f" % c))
                else:
                    c = m["sines"].get(w)
                    cells.append("%s=%s" % (w, "unvoiced" if c is None else "%+.2f" % c))
            lines.append("  " + m["name"] + ": " + " ".join(cells))
        ranked = sorted(results, key=lambda m: (m["med"] is None, m["med"] if m["med"] is not None else 0))
        lines.append("ranked by medAbsC: " + " > ".join("%s(%s)" % (m["name"], fmt(m["med"])) for m in ranked))
        out["sweep"] = [{k: v for k, v in m.items() if k != "per_file"} for m in results]
        out["base_settled"] = base_vals
    text = "\n".join(lines) + "\n"
    with open(os.path.join(work, "results.txt"), "w") as f:
        f.write(text)
    with open(os.path.join(work, "results.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    sys.stdout.write(text)


def write_kernel(spec_path, kdir, slug, title):
    spec_text = open(spec_path).read()
    os.makedirs(kdir, exist_ok=True)
    meta = {
        "id": "heclgang/" + slug,
        "title": title,
        "code_file": "kernel.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": False,
        "enable_internet": True,
        "dataset_sources": ["heclgang/tracker-sweep-inputs"],
        "competition_sources": [],
        "kernel_sources": [],
    }
    with open(os.path.join(kdir, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    code = (
        "import json, os, shutil, subprocess, sys, zipfile\n"
        "SRC = '/kaggle/input/tracker-sweep-inputs'\n"
        "DST = '/kaggle/working/inputs'\n"
        "SPEC = json.loads(%r)\n"
        "if os.path.exists(os.path.join(SRC, 'inputs.zip')):\n"
        "    os.makedirs(DST, exist_ok=True)\n"
        "    zipfile.ZipFile(os.path.join(SRC, 'inputs.zip')).extractall(DST)\n"
        "else:\n"
        "    shutil.copytree(os.path.join(SRC, 'inputs'), DST)\n"
        "SPEC['input_root'] = DST\n"
        "path = '/kaggle/working/spec.json'\n"
        "with open(path, 'w') as f:\n"
        "    json.dump(SPEC, f)\n"
        "subprocess.run([sys.executable, '/kaggle/input/tracker-sweep-inputs/sweep.py', 'run', path], check=True)\n"
    ) % spec_text
    with open(os.path.join(kdir, "kernel.py"), "w") as f:
        f.write(code)


def stage(dest, zip_path, libs_dir, wav_dir, dsp_dir, here):
    os.makedirs(dest, exist_ok=True)
    shutil.copy(os.path.join(here, "sweep.py"), dest)
    shutil.copy(os.path.join(here, "render_sweep.cpp"), dest)
    shutil.copytree(dsp_dir, os.path.join(dest, "dsp"), dirs_exist_ok=True)
    shutil.copytree(wav_dir, os.path.join(dest, "wav"), dirs_exist_ok=True)
    shutil.copytree(libs_dir, os.path.join(dest, "faustlibraries"), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("doc", "tests", "docs", ".git*"))
    meta = {"title": "tracker sweep inputs", "id": "heclgang/tracker-sweep-inputs",
            "licenses": [{"name": "CC0-1.0"}]}
    with open(os.path.join(dest, "dataset-metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)


def main(argv):
    cmd = argv[1]
    if cmd == "sines":
        make_sines(argv[2])
    elif cmd == "run":
        run(argv[2])
    elif cmd == "summarize":
        summarize(argv[2])
    elif cmd == "kernel":
        write_kernel(argv[2], argv[3], argv[4], argv[5])
    elif cmd == "stage":
        stage(argv[2], argv[3], argv[4], argv[5], argv[6], os.path.dirname(os.path.abspath(__file__)))
    elif cmd == "subs":
        print(json.dumps(subs_for(argv[2], argv[3])))
    else:
        raise SystemExit("unknown command %s" % cmd)


if __name__ == "__main__":
    main(sys.argv)
