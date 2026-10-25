import hashlib, json, os, shutil, statistics, subprocess, zipfile
from concurrent.futures import ThreadPoolExecutor

REF = "__REF__"
DD = "https://raw.githubusercontent.com/AnEntrypoint/dawdreamer/" + REF + "/tools/piano-diag/"
MC = "https://raw.githubusercontent.com/AnEntrypoint/mc-420/"
MC_DSP = "b563a62a871bf8cfabbc7510da7ee2ffebc7386d"
MC_NORM = "4e38a47d5911f1976f44eaa3383cc3680c833274"
FAUST = "2.85.9"
FAUSTLIB = "78a72d4998dec43e20492ef9b78d1a785b3dc864"
PIN = {
    "shipped_dsp": "cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0",
    "normaliser": "ba2529866947b904772704264fea894971ce3e2c3b0c6ff532de3c4b93288e78",
    "piano_raw": "eeb66ca2217a79843bf205a03deee6978cf76e9e0a09f598baed5266be9a49f2",
    "piano_norm": "1fd2224f39de72d8af8773e4af765aff8892a6495a0669d46802289f593b4821",
}
PINNED = ["-vec", "-fun", "-dfs", "-vs", "32", "-nvi", "-ct", "0"]
TAU_OLD = "    energyTau = 0.01;"
TAU_NEW = "    energyTau = 0.02;"
STUB_C = ("void *set_curterm(void *t){return 0;} int setupterm(const char *t,int fd,int *e){if(e)*e=0;return -1;}"
          " int tigetnum(const char *c){return -1;} int del_curterm(void *t){return 0;}\n")
W = "/kaggle/working/piano-diag"
WAV = "inputs/piano_low_A1.wav"
VARIANTS = ["shipped_tau0.01", "shipped_tau0.02", "instr_tau0.01", "instr_tau0.02"]
SIGNALS = ["out", "raw", "env", "aboveFloor", "holdCount", "ready", "coarse", "refinedHz",
           "refinedLag", "finalConf", "confident", "demoteNow", "dom2", "dom3", "n_ready", "n_conf", "n_voiced"]


def say(*parts):
    print(" ".join(str(p) for p in parts), flush=True)


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def must(cmd, cwd=None, env=None):
    r = run(cmd, cwd, env)
    if r.returncode != 0:
        raise SystemExit("failed: " + " ".join(cmd) + "\n" + (r.stderr or "")[-3000:])
    return r


def fetch(url, dest):
    must(["curl", "-sfL", "--retry", "3", url, "-o", dest])


def pin(name, path):
    got = sha_file(path)
    if got != PIN[name]:
        raise SystemExit("pin mismatch %s %s" % (name, got))
    say("pin ok", name, got)


def subst(text, old, new):
    n = text.count(old)
    if n != 1:
        raise SystemExit("substitution matched %d times" % n)
    return text.replace(old, new)


def npy_payload(path):
    b = open(path, "rb").read()
    hl = int.from_bytes(b[8:10], "little")
    return b[10 + hl:]


def read_tsv(path):
    lines = open(path).read().splitlines()
    head = lines[0].split("\t")
    return head, [dict(zip(head, l.split("\t"))) for l in lines[1:]]


def load_variant(name):
    if name.startswith("shipped"):
        txt = os.path.join(W, "out", name + "_piano_low_A1.txt")
        npy = os.path.join(W, "out", name + "_piano_low_A1.npy")
        pairs = [(float(p[0]), float(p[1])) for p in (l.split() for l in open(txt)) if len(p) == 2]
        return {"pairs": pairs, "ch0_sha": hashlib.sha256(npy_payload(npy)).hexdigest(),
                "trace_sha": sha_file(txt), "trace": txt}
    tsv = os.path.join(W, "out", name + ".tsv")
    f32 = os.path.join(W, "out", name + "_ch0.f32")
    head, rows = read_tsv(tsv)
    pairs = [(float(r["t"]), float(r["out"])) for r in rows]
    return {"pairs": pairs, "ch0_sha": hashlib.sha256(open(f32, "rb").read()).hexdigest(),
            "trace_sha": sha_file(tsv), "trace": tsv}


def build(name, text, driver):
    vdir = os.path.join(W, name)
    os.makedirs(vdir, exist_ok=True)
    open(os.path.join(vdir, "in.dsp"), "w").write(text)
    must([os.path.join(W, "faust_cli"), "-lang", "cpp"] + PINNED + ["-I", LIBS, "in.dsp", "-o", "dsp.cpp"],
         cwd=vdir, env=ENV)
    shutil.copy(os.path.join(W, driver), os.path.join(vdir, driver))
    must(["g++", "-O3", "-std=c++17", "-I", ARCH, driver, "-o", "render"], cwd=vdir)
    out = os.path.join(W, "out", name)
    exe = os.path.join(vdir, "render")
    if driver == "render_cpp_driver.cpp":
        must([exe, name, "1.0", out, os.path.join(W, WAV)], cwd=vdir)
    else:
        must([exe, "1.0", out, os.path.join(W, WAV)], cwd=vdir)
    return name


def main():
    global ARCH, LIBS, ENV
    os.makedirs(W, exist_ok=True)
    os.chdir(W)
    for d in ("raw", "inputs", "out"):
        os.makedirs(d, exist_ok=True)
    fetch(MC + MC_DSP + "/effects/pitchtracker-src/pitchtracker_ac.dsp", "shipped.dsp")
    pin("shipped_dsp", "shipped.dsp")
    fetch(MC + MC_NORM + "/tools/corpus-level/normalise-corpus.mjs", "normalise-corpus.mjs")
    pin("normaliser", "normalise-corpus.mjs")
    fetch(MC + MC_NORM + "/test-audio-corpus/instruments/piano_low_A1.wav", "raw/piano_low_A1.wav")
    pin("piano_raw", "raw/piano_low_A1.wav")
    must(["node", "normalise-corpus.mjs", "--src", "raw", "--out", "inputs", "--rms", "0.1"])
    pin("piano_norm", WAV)
    for name in ["pitchtracker_ac_diag.dsp", "render_trace.cpp", "faust_cli.cpp", "render_cpp_driver.cpp"]:
        fetch(DD + name, name)
    say("harness ref", REF)
    fetch("https://github.com/grame-cncm/faust/releases/download/%s/libfaust-ubuntu-x86_64.zip" % FAUST,
          "libfaust.zip")
    zipfile.ZipFile("libfaust.zip").extractall("faust-lib")
    fetch("https://github.com/grame-cncm/faust/archive/refs/tags/%s.tar.gz" % FAUST, "faust.tar.gz")
    os.makedirs("faust-src", exist_ok=True)
    must(["tar", "-xzf", "faust.tar.gz", "-C", "faust-src", "--wildcards", "*/architecture/*"])
    fetch("https://github.com/grame-cncm/faustlibraries/archive/%s.tar.gz" % FAUSTLIB, "faustlibs.tar.gz")
    os.makedirs("faust-libs", exist_ok=True)
    must(["tar", "-xzf", "faustlibs.tar.gz", "-C", "faust-libs", "--strip-components=1"])
    run(["bash", "-c", "apt-get update -qq && apt-get install -y -qq libncurses-dev"])
    ARCH = os.path.abspath("faust-src/faust-%s/architecture" % FAUST)
    LIBS = os.path.abspath("faust-libs")
    LIB = os.path.abspath("faust-lib/lib/libfaustwithllvm.a")
    ENV = dict(os.environ, FAUST_LIBRARY_DIR=LIBS)
    open("stub.c", "w").write(STUB_C)
    must(["gcc", "-O2", "-c", "stub.c", "-o", "stub.o"])
    built = None
    recipes = [("plain", ["-O2", "-std=c++17"], False),
               ("abi0", ["-O2", "-std=c++17", "-D_GLIBCXX_USE_CXX11_ABI=0"], False),
               ("stub", ["-O2", "-std=c++17"], True)]
    for rname, cflags, stub in recipes:
        cmd = (["g++"] + cflags + ["-I", ARCH, "-I", os.path.abspath("faust-lib"), "faust_cli.cpp"]
               + (["stub.o"] if stub else []) + [LIB, "-lz", "-lpthread", "-ldl", "-lm"]
               + ([] if stub else ["-ltinfo"]) + ["-o", "faust_cli"])
        r = run(cmd)
        if r.returncode == 0:
            built = rname
            break
        say("link failed", rname, (r.stderr or "")[-300:])
    if built is None:
        raise SystemExit("faust_cli did not link")
    say("faust_cli link", built)
    shipped = open("shipped.dsp").read()
    instr = open("pitchtracker_ac_diag.dsp").read()
    jobs = [
        ("shipped_tau0.01", shipped, "render_cpp_driver.cpp"),
        ("shipped_tau0.02", subst(shipped, TAU_OLD, TAU_NEW), "render_cpp_driver.cpp"),
        ("instr_tau0.01", instr, "render_trace.cpp"),
        ("instr_tau0.02", subst(instr, TAU_OLD, TAU_NEW), "render_trace.cpp"),
    ]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name in ex.map(lambda j: build(*j), jobs):
            say("built and rendered", name)
    report()
    for heavy in ("faust-lib", "faust-src", "faust-libs"):
        shutil.rmtree(heavy, ignore_errors=True)


def report():
    summary = {"harness_ref": REF, "faust": FAUST, "pinned_flags": " ".join(PINNED), "variants": {}}
    loaded = {}
    for name in VARIANTS:
        v = load_variant(name)
        loaded[name] = v
        settled = [hz for t, hz in v["pairs"] if t >= 1.0 and hz != 0.0]
        summary["variants"][name] = {
            "settled_median_hz": statistics.median(settled) if settled else None,
            "settled_n": len(settled),
            "voiced_blocks_total": sum(1 for _, hz in v["pairs"] if hz != 0.0),
            "ch0_payload_sha256": v["ch0_sha"],
            "trace": v["trace"],
            "trace_sha256": v["trace_sha"],
        }
        say(name, "settled_median_hz", summary["variants"][name]["settled_median_hz"],
            "settled_n", len(settled), "voiced_total", summary["variants"][name]["voiced_blocks_total"],
            "trace_sha256", v["trace_sha"])
    for tau in ("0.01", "0.02"):
        a = summary["variants"]["shipped_tau" + tau]["ch0_payload_sha256"]
        b = summary["variants"]["instr_tau" + tau]["ch0_payload_sha256"]
        summary["proof_tau" + tau] = {"shipped_ch0": a, "instr_ch0": b, "identical": a == b}
        say("proof tau", tau, "identical", a == b)
    head, A = read_tsv(os.path.join(W, "out", "instr_tau0.01.tsv"))
    _, B = read_tsv(os.path.join(W, "out", "instr_tau0.02.tsv"))
    first = {}
    for c in SIGNALS:
        for i, (ra, rb) in enumerate(zip(A, B)):
            if c in ra and ra[c] != rb[c]:
                first[c] = i
                break
    vdiv = None
    for i, (ra, rb) in enumerate(zip(A, B)):
        if (float(ra["out"]) != 0.0) != (float(rb["out"]) != 0.0):
            vdiv = i
            break
    summary["first_divergent_block_per_signal"] = first
    summary["first_voicing_divergent_block"] = vdiv
    if vdiv is not None:
        summary["voicing_block_values"] = {
            "tau0.01": {c: A[vdiv].get(c) for c in ["block", "t"] + SIGNALS if c in A[vdiv]},
            "tau0.02": {c: B[vdiv].get(c) for c in ["block", "t"] + SIGNALS if c in B[vdiv]},
        }
    say("first voicing divergent block", vdiv)
    say("first divergent block per signal", first)
    json.dump(summary, open(os.path.join(W, "summary.json"), "w"), indent=2)
    say(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
