#!/usr/bin/env python3
import concurrent.futures
import hashlib
import json
import math
import os
import shutil
import statistics
import struct
import subprocess
import sys
import tarfile
import time
import wave
import zipfile

PINNED = "-vec -fun -dfs -vs 32 -nvi -ct 0"
FAUST_VERSION = "2.85.9"
FAUST_URL = "https://github.com/grame-cncm/faust/archive/refs/tags/2.85.9.tar.gz"
LIBFAUST_URL = "https://github.com/grame-cncm/faust/releases/download/2.85.9/libfaust-ubuntu-x86_64.zip"
FAUSTLIB_SHA = "78a72d4998dec43e20492ef9b78d1a785b3dc864"
FAUSTLIB_URL = "https://github.com/grame-cncm/faustlibraries/archive/%s.tar.gz" % FAUSTLIB_SHA
BASELINE_DSP_SHA256 = "abe8866ef78c922a83925f341ce0ef4ae236c380246cb30d5f955076245ac3cb"
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
SINES = {"sine_65.55": 65.55, "sine_69.75": 69.75, "sine_110": 110.0, "sine_440": 440.0, "sine_1000": 1000.0, "sine_2093": 2093.0}

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


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


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


def trace_path(tdir, w):
    return os.path.join(tdir, "out_" + w + ".txt")


def settled(rows):
    vals = [hz for t, hz in rows if t >= 1.0 and hz != 0.0]
    return statistics.median(vals) if vals else 0.0


def cents(hz, target):
    return 1200.0 * math.log2(hz / target)


def wav_names(spec):
    if spec["wavs"] == "all":
        return sorted(f[:-4] for f in os.listdir(os.path.join(spec["input_root"], "wav")) if f.endswith(".wav"))
    return spec["wavs"]


def run_logged(cmd, log, env=None, cwd=None):
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)
    log.write("$ %s\nrc=%d secs=%.1f\n%s%s\n" % (" ".join(cmd), proc.returncode, time.time() - t0, proc.stdout[-4000:], proc.stderr[-4000:]))
    log.flush()
    return proc


def fetch(url, dest, log):
    if run_logged(["curl", "-fL", "-sS", "--retry", "3", "-o", dest, url], log).returncode != 0:
        raise SystemExit("download failed: " + url)
    log.write("fetched %s sha256 %s\n" % (url, sha256_file(dest)))


def build_toolchain(work, log):
    tc = os.path.join(work, "toolchain")
    os.makedirs(tc, exist_ok=True)
    src_tar = os.path.join(tc, "faust-src.tar.gz")
    fetch(FAUST_URL, src_tar, log)
    with tarfile.open(src_tar) as t:
        members = [m for m in t.getmembers() if "/architecture/" in m.name]
        t.extractall(tc, members=members, filter="data")
    arch = os.path.join(tc, "faust-" + FAUST_VERSION, "architecture")
    lib_zip = os.path.join(tc, "libfaust.zip")
    fetch(LIBFAUST_URL, lib_zip, log)
    libroot = os.path.join(tc, "faust-lib")
    with zipfile.ZipFile(lib_zip) as z:
        z.extractall(libroot)
    libfaust = os.path.join(libroot, "lib", "libfaustwithllvm.a")
    if not os.path.isfile(libfaust):
        raise SystemExit("lib/libfaustwithllvm.a missing from the 2.85.9 release zip")
    libs_tar = os.path.join(tc, "faustlibs.tar.gz")
    fetch(FAUSTLIB_URL, libs_tar, log)
    libdir = os.path.join(tc, "faust-libs")
    os.makedirs(libdir, exist_ok=True)
    with tarfile.open(libs_tar) as t:
        members = []
        for m in t.getmembers():
            parts = m.name.split("/", 1)
            if len(parts) == 2 and parts[1]:
                m.name = parts[1]
                members.append(m)
        t.extractall(libdir, members=members, filter="data")
    if not os.path.isfile(os.path.join(libdir, "stdfaust.lib")):
        raise SystemExit("stdfaust.lib missing after the faustlibraries extract")
    subprocess.run(["bash", "-c", "(apt-get update -qq && apt-get install -y -qq libncurses-dev) >/dev/null 2>&1"])
    faust_cli = os.path.join(tc, "faust_cli")
    cli_src = os.path.join(work, "faust_cli.cpp")
    for recipe, cflags in (("plain", ["-O2", "-std=c++17"]), ("abi0", ["-O2", "-std=c++17", "-D_GLIBCXX_USE_CXX11_ABI=0"])):
        cmd = ["g++"] + cflags + ["-I", arch, "-I", libroot, cli_src, libfaust,
                                  "-lz", "-lpthread", "-ldl", "-lm", "-ltinfo", "-o", faust_cli]
        if run_logged(cmd, log).returncode == 0:
            log.write("faust_cli link recipe %s\n" % recipe)
            break
    else:
        raise SystemExit("faust_cli did not link")
    return faust_cli, arch, libdir


def build_variant(name, text, faust_cli, arch, libdir, driver, gain, wav_paths, work):
    vdir = os.path.join(work, "build", name)
    tdir = os.path.join(work, "traces", name)
    os.makedirs(os.path.join(vdir, "src"), exist_ok=True)
    os.makedirs(tdir, exist_ok=True)
    log = open(os.path.join(vdir, "build.log"), "w")
    rec = {"name": name, "dsp_sha256": None, "error": None}
    try:
        with open(os.path.join(vdir, "src", "pitchtracker_ac.dsp"), "w") as f:
            f.write(text)
        r = run_logged([faust_cli, "-lang", "cpp"] + PINNED.split() + ["-I", libdir, "src/pitchtracker_ac.dsp", "-o", "dsp.cpp"], log, cwd=vdir)
        if r.returncode != 0 or not os.path.isfile(os.path.join(vdir, "dsp.cpp")):
            rec["error"] = "faust_cli rc=%d" % r.returncode
            return rec
        rec["dsp_sha256"] = sha256_file(os.path.join(vdir, "dsp.cpp"))
        shutil.copy(driver, os.path.join(vdir, "render_cpp_driver.cpp"))
        r = run_logged(["g++", "-O3", "-std=c++17", "-I", arch, "render_cpp_driver.cpp", "-o", "render_cpp"], log, cwd=vdir)
        if r.returncode != 0:
            rec["error"] = "g++ rc=%d" % r.returncode
            return rec
        t0 = time.time()
        r = run_logged(["./render_cpp", name, str(gain), os.path.join(tdir, "out")] + wav_paths, log, cwd=vdir)
        rec["render_secs"] = round(time.time() - t0, 1)
        if r.returncode != 0:
            rec["error"] = "render rc=%d" % r.returncode
        for f in os.listdir(tdir):
            if f.endswith(".npy"):
                os.remove(os.path.join(tdir, f))
        return rec
    finally:
        log.close()


def run(spec_path):
    spec = json.load(open(spec_path))
    root, work = spec["input_root"], spec["work"]
    os.makedirs(work, exist_ok=True)
    log = open(os.path.join(work, "run.log"), "a")
    shutil.copy(os.path.join(root, "faust_cli.cpp"), work)
    faust_cli, arch, libdir = build_toolchain(work, log)
    driver = os.path.join(root, "render_cpp_driver.cpp")
    wav_paths = [os.path.join(root, "wav", w + ".wav") for w in wav_names(spec)]
    texts, jobs = {}, []
    for v in spec["variants"]:
        if v["dsp"] not in texts:
            texts[v["dsp"]] = open(os.path.join(root, "dsp", v["dsp"] + ".dsp")).read()
        text = texts[v["dsp"]]
        for old, new in v.get("subs", []):
            cnt = text.count(old)
            if cnt != 1:
                raise SystemExit("%s: substitution matched %d times: %r" % (v["name"], cnt, old[:60]))
            text = text.replace(old, new)
        jobs.append((v["name"], text, v["dsp"] == "A_e557252" and not v.get("subs")))
    records = []
    for name, text, is_shipped in (j for j in jobs if j[2] or j[0] == "baseline"):
        rec = build_variant(name, text, faust_cli, arch, libdir, driver, spec["gain"], wav_paths, work)
        records.append(rec)
        log.write("%s\n" % json.dumps(rec))
        log.flush()
        if rec["dsp_sha256"] != BASELINE_DSP_SHA256:
            raise SystemExit("shipped dsp.cpp sha256 %s != %s; no render started" % (rec["dsp_sha256"], BASELINE_DSP_SHA256))
    rest = [j for j in jobs if not (j[2] or j[0] == "baseline")]
    workers = int(os.environ.get("SWEEP_WORKERS", "2"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(build_variant, name, text, faust_cli, arch, libdir, driver, spec["gain"], wav_paths, work)
                for name, text, _ in rest]
        for fut in concurrent.futures.as_completed(futs):
            rec = fut.result()
            records.append(rec)
            log.write("%s\n" % json.dumps(rec))
            log.flush()
            print("%s dsp=%s error=%s secs=%s" % (rec["name"], rec["dsp_sha256"], rec["error"], rec.get("render_secs")), flush=True)
    with open(os.path.join(work, "build_manifest.json"), "w") as f:
        json.dump(records, f, indent=1)
    log.close()
    summarize(spec_path)


def settled_map(tdir, wavs):
    out = {}
    for w in wavs:
        p = trace_path(tdir, w)
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
    out["sine_sha256_generated"] = {
        w: sha256_file(os.path.join(root, "wav", w + ".wav"))
        for w in SINES if os.path.exists(os.path.join(root, "wav", w + ".wav"))
    }
    manifest_path = os.path.join(work, "build_manifest.json")
    records = json.load(open(manifest_path)) if os.path.exists(manifest_path) else []
    out["dsp_sha256"] = {r["name"]: r.get("dsp_sha256") for r in records}
    out["build_errors"] = [r for r in records if r.get("error")]
    out["driver_backend"] = ("faust_cli %s (libfaustwithllvm.a) %s, render_cpp_driver.cpp, g++ -O3 -std=c++17, no -mcpu"
                             % (FAUST_VERSION, PINNED))
    if spec["report"] == "flag":
        for a, b in spec["pairs"]:
            lines.append("PAIR %s vs %s (block-end Hz, exact float match)" % (a, b))
            for w in spec["wavs"]:
                ra = read_trace(trace_path(os.path.join(tr, a), w))
                rb = read_trace(trace_path(os.path.join(tr, b), w))
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
        lines.append("LOWFREQ recheck, gain %s, target = exact generated sine frequency" % spec["gain"])
        for w in spec["wavs"]:
            f = SINES[w]
            sa = settled(read_trace(trace_path(os.path.join(tr, "A"), w)))
            sb = settled(read_trace(trace_path(os.path.join(tr, "B"), w)))
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
        out["trace_sha256"] = {}
        for v in spec["variants"]:
            vdir = os.path.join(tr, v["name"])
            vals = settled_map(vdir, wavs)
            out["trace_sha256"][v["name"]] = {
                w: (sha256_file(trace_path(vdir, w)) if os.path.exists(trace_path(vdir, w)) else None) for w in wavs
            }
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
        lines.append("per-file settled cents vs certified peak (scored), then GENERATED sines (3 s, make_sines convention, not manifest; outside S1-S2)")
        for m in results:
            cells = []
            for w in list(TARGETS) + list(SINES):
                c = m["err"].get(w) if w in TARGETS else m["sines"].get(w)
                cells.append("%s=%s" % (w, "unvoiced" if c is None else "%+.2f" % c))
            lines.append("  " + m["name"] + ": " + " ".join(cells))
        ranked = sorted(results, key=lambda m: (m["med"] is None, m["med"] if m["med"] is not None else 0))
        lines.append("ranked by medAbsC: " + " > ".join("%s(%s)" % (m["name"], fmt(m["med"])) for m in ranked))
        out["sweep"] = [{k: v for k, v in m.items() if k != "per_file"} for m in results]
        out["base_settled"] = base_vals
    if out["build_errors"]:
        lines.append("BUILD/RENDER FAILURES: " + "; ".join("%s %s" % (r["name"], r["error"]) for r in out["build_errors"]))
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
        "SPEC = json.loads(%r)\n"
        "DST = '/kaggle/working/inputs'\n"
        "found, zips, sweep, seen = None, [], None, []\n"
        "for dp, dn, fn in os.walk('/kaggle/input'):\n"
        "    seen.append(dp + ' dirs=' + ','.join(sorted(dn)[:15]) + ' files=' + ','.join(sorted(fn)[:15]))\n"
        "    if found is None and {'dsp', 'wav'} <= set(dn):\n"
        "        found = dp\n"
        "    if 'inputs.zip' in fn:\n"
        "        zips.append(os.path.join(dp, 'inputs.zip'))\n"
        "    if 'sweep.py' in fn and sweep is None:\n"
        "        sweep = os.path.join(dp, 'sweep.py')\n"
        "print('\\n'.join(seen[:40]))\n"
        "print('found', found, 'zips', zips, 'sweep', sweep)\n"
        "if found is not None:\n"
        "    shutil.copytree(found, DST, dirs_exist_ok=True)\n"
        "elif zips:\n"
        "    os.makedirs(DST, exist_ok=True)\n"
        "    zipfile.ZipFile(zips[0]).extractall(DST)\n"
        "else:\n"
        "    raise SystemExit('dataset inputs not found')\n"
        "for name in ('render_cpp_driver.cpp', 'faust_cli.cpp'):\n"
        "    if not os.path.exists(os.path.join(DST, name)) and sweep:\n"
        "        shutil.copy(os.path.join(os.path.dirname(sweep), name), DST)\n"
        "    if not os.path.exists(os.path.join(DST, name)):\n"
        "        raise SystemExit(name + ' missing from inputs')\n"
        "SPEC['input_root'] = DST\n"
        "path = '/kaggle/working/spec.json'\n"
        "json.dump(SPEC, open(path, 'w'))\n"
        "subprocess.run([sys.executable, sweep, 'run', path], check=True)\n"
    ) % spec_text
    with open(os.path.join(kdir, "kernel.py"), "w") as f:
        f.write(code)


def stage(dest, wav_dir, dsp_dir, here):
    os.makedirs(dest, exist_ok=True)
    for name in ("sweep.py", "faust_cli.cpp", "render_cpp_driver.cpp"):
        shutil.copy(os.path.join(here, name), dest)
    shutil.copytree(dsp_dir, os.path.join(dest, "dsp"), dirs_exist_ok=True)
    shutil.copytree(wav_dir, os.path.join(dest, "wav"), dirs_exist_ok=True)
    make_sines(os.path.join(dest, "wav"))
    meta = {"title": "tracker sweep inputs", "id": "heclgang/tracker-sweep-inputs",
            "licenses": [{"name": "CC0-1.0"}]}
    with open(os.path.join(dest, "dataset-metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)


def zip_inputs(stage_dir, out_zip):
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("faust_cli.cpp", "render_cpp_driver.cpp"):
            z.write(os.path.join(stage_dir, name), name)
        for sub in ("dsp", "wav"):
            for dp, _, fn in os.walk(os.path.join(stage_dir, sub)):
                for f in fn:
                    full = os.path.join(dp, f)
                    z.write(full, os.path.relpath(full, stage_dir))


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
        stage(argv[2], argv[3], argv[4], os.path.dirname(os.path.abspath(__file__)))
    elif cmd == "zip":
        zip_inputs(argv[2], argv[3])
    elif cmd == "subs":
        print(json.dumps(subs_for(argv[2], argv[3])))
    else:
        raise SystemExit("unknown command %s" % cmd)


if __name__ == "__main__":
    main(sys.argv)
