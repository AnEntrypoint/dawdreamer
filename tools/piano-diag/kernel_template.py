import hashlib, json, os, shutil, statistics, subprocess, zipfile
from concurrent.futures import ThreadPoolExecutor

REF = "__REF__"
DD = "https://raw.githubusercontent.com/AnEntrypoint/dawdreamer/" + REF + "/tools/piano-diag/"
MC = "https://raw.githubusercontent.com/AnEntrypoint/mc-420/"
MC_NORM = "4e38a47d5911f1976f44eaa3383cc3680c833274"
FAUST = "2.85.9"
FAUSTLIB = "78a72d4998dec43e20492ef9b78d1a785b3dc864"
PIN_NORM = "ba2529866947b904772704264fea894971ce3e2c3b0c6ff532de3c4b93288e78"
PIN_PIANO_LEVEL = "1fd2224f39de72d8af8773e4af765aff8892a6495a0669d46802289f593b4821"
PIN_PIANO_TSV = {
    "tau0.01": "b526a1e8f02ce96fdb2a32d49192c9db7bf2463958893bb4e1344333dab47fad",
    "tau0.02": "b7b8aeb160272630ff8e191f128f71c4e6d83ac7bd2038b670fa775be5471532",
}
RAW_PIN = {
    "piano_low_A1": "eeb66ca2217a79843bf205a03deee6978cf76e9e0a09f598baed5266be9a49f2",
    "violin_low_sulG_G3B3": "b6a2b4e1e31db0cd1a34d0f007b25e3c666eeff30228cc66d781a5ee83e6d663",
    "violin_high_sulE_C7E7": "5c6bc8d11ee16aeb65e4d02c68a70873ca6d154d1c99553fde0c4a9ea5b8a993",
    "xylophone_run_C7B7": "27953dd0d6a540c0be6e201cc204ab8fe6110581600760c868dc5991e39c94ed",
    "crotale_high_C7": "34d5e68ec10c20d1ede955c2bbbf2bc74de6ce8a77e21a9e1b2312d91915c449",
    "vocal_melody_twinkle_CC0": "71932a610f1104a8dbf9b730c1cccc83d4e77259d6991793d23a546d9846a5f1",
    "vocal_tenor_operatic_PD": "048bb69bf3b37cfa58e79240b5a130a78762e48d0b171767758de59b5491c96e",
}
PINNED = ["-vec", "-fun", "-dfs", "-vs", "32", "-nvi", "-ct", "0"]
TAU_OLD = "    energyTau = 0.01;"
TAU_NEW = "    energyTau = 0.02;"
GAINS = {"level": "1.0", "corpus": "0.00707945784384138"}
JOBS = [
    ("level", "piano_low_A1", "tau0.01"),
    ("level", "piano_low_A1", "tau0.02"),
    ("level", "violin_low_sulG_G3B3", "tau0.01"),
    ("level", "violin_low_sulG_G3B3", "tau0.02"),
    ("level", "violin_high_sulE_C7E7", "tau0.01"),
    ("level", "xylophone_run_C7B7", "tau0.01"),
    ("corpus", "violin_low_sulG_G3B3", "tau0.01"),
    ("corpus", "violin_low_sulG_G3B3", "tau0.02"),
    ("corpus", "violin_high_sulE_C7E7", "tau0.01"),
    ("corpus", "xylophone_run_C7B7", "tau0.01"),
    ("corpus", "crotale_high_C7", "tau0.01"),
    ("corpus", "vocal_melody_twinkle_CC0", "tau0.01"),
    ("corpus", "vocal_tenor_operatic_PD", "tau0.01"),
]
STUB_C = ("void *set_curterm(void *t){return 0;} int setupterm(const char *t,int fd,int *e){if(e)*e=0;return -1;}"
          " int tigetnum(const char *c){return -1;} int del_curterm(void *t){return 0;}\n")
W = "/kaggle/working/piano-diag"


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


def pin(label, path, want):
    got = sha_file(path)
    if got != want:
        raise SystemExit("pin mismatch %s %s" % (label, got))
    say("pin ok", label, got)


def subst(text, old, new):
    n = text.count(old)
    if n != 1:
        raise SystemExit("substitution matched %d times" % n)
    return text.replace(old, new)


def read_tsv(path):
    lines = open(path).read().splitlines()
    head = lines[0].split("\t")
    return head, [dict(zip(head, l.split("\t"))) for l in lines[1:]]


def build(tau, instr):
    text = instr if tau == "tau0.01" else subst(instr, TAU_OLD, TAU_NEW)
    vdir = os.path.join(W, "build_" + tau)
    os.makedirs(vdir, exist_ok=True)
    open(os.path.join(vdir, "in.dsp"), "w").write(text)
    must([os.path.join(W, "faust_cli"), "-lang", "cpp"] + PINNED + ["-I", LIBS, "in.dsp", "-o", "dsp.cpp"],
         cwd=vdir, env=ENV)
    shutil.copy(os.path.join(W, "render_trace.cpp"), os.path.join(vdir, "render_trace.cpp"))
    must(["g++", "-O3", "-std=c++17", "-I", ARCH, "render_trace.cpp", "-o", "render"], cwd=vdir)
    return tau


def render(job):
    gk, wav, tau = job
    label = "%s__%s__%s" % (gk, wav, tau)
    src = os.path.join(W, "level" if gk == "level" else "raw", wav + ".wav")
    vdir = os.path.join(W, "build_" + tau)
    must([os.path.join(vdir, "render"), GAINS[gk], os.path.join(W, "out", label), src], cwd=vdir)
    return label


def main():
    global ARCH, LIBS, ENV
    os.makedirs(W, exist_ok=True)
    os.chdir(W)
    for d in ("raw", "level", "out"):
        os.makedirs(d, exist_ok=True)
    for name in ["pitchtracker_ac_diag.dsp", "render_trace.cpp", "faust_cli.cpp"]:
        fetch(DD + name, name)
    say("harness ref", REF)
    for name, want in RAW_PIN.items():
        fetch(MC + MC_NORM + "/test-audio-corpus/instruments/" + name + ".wav", "raw/" + name + ".wav")
        pin(name, "raw/" + name + ".wav", want)
    fetch(MC + MC_NORM + "/tools/corpus-level/normalise-corpus.mjs", "normalise-corpus.mjs")
    pin("normaliser", "normalise-corpus.mjs", PIN_NORM)
    must(["node", "normalise-corpus.mjs", "--src", "raw", "--out", "level", "--rms", "0.1"])
    pin("piano_level", "level/piano_low_A1.wav", PIN_PIANO_LEVEL)
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
    instr = open("pitchtracker_ac_diag.dsp").read()
    with ThreadPoolExecutor(max_workers=2) as ex:
        for tau in ex.map(lambda t: build(t, instr), ["tau0.01", "tau0.02"]):
            say("built", tau)
    with ThreadPoolExecutor(max_workers=4) as ex:
        labels = list(ex.map(render, JOBS))
    report(labels)
    cleanup()


def report(labels):
    summary = {"harness_ref": REF, "faust": FAUST, "pinned_flags": " ".join(PINNED), "jobs": {}}
    for label in labels:
        path = os.path.join(W, "out", label + ".tsv")
        head, rows = read_tsv(path)
        pairs = [(float(r["t"]), float(r["out"])) for r in rows]
        settled = [hz for t, hz in pairs if t >= 1.0 and hz != 0.0]
        summary["jobs"][label] = {
            "settled_median_hz": statistics.median(settled) if settled else None,
            "settled_n": len(settled),
            "voiced_blocks_total": sum(1 for _, hz in pairs if hz != 0.0),
            "blocks": len(rows),
            "trace": "out/" + label + ".tsv",
            "trace_sha256": sha_file(path),
        }
        say(label, "settled_median_hz", summary["jobs"][label]["settled_median_hz"],
            "settled_n", len(settled), "voiced_total", summary["jobs"][label]["voiced_blocks_total"],
            "trace_sha256", summary["jobs"][label]["trace_sha256"])
    for tau in ("tau0.01", "tau0.02"):
        label = "level__piano_low_A1__" + tau
        got = summary["jobs"][label]["trace_sha256"]
        summary["piano_tsv_matches_v1_" + tau] = got == PIN_PIANO_TSV[tau]
        say("piano tsv matches v1", tau, got == PIN_PIANO_TSV[tau])
    json.dump(summary, open(os.path.join(W, "summary.json"), "w"), indent=2)


def cleanup():
    for p in ["faust-lib", "faust-src", "faust-libs", "raw", "level", "build_tau0.01", "build_tau0.02"]:
        shutil.rmtree(os.path.join(W, p), ignore_errors=True)
    for p in ["libfaust.zip", "faust.tar.gz", "faustlibs.tar.gz", "faust_cli", "faust_cli.cpp", "stub.c",
              "stub.o", "normalise-corpus.mjs", "pitchtracker_ac_diag.dsp", "render_trace.cpp"]:
        path = os.path.join(W, p)
        if os.path.exists(path):
            os.remove(path)
    say("cleanup done; remaining:", sorted(os.listdir(W)))


if __name__ == "__main__":
    main()
