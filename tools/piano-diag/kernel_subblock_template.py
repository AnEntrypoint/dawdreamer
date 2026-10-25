import gzip, hashlib, json, os, shutil, subprocess, zipfile
from concurrent.futures import ThreadPoolExecutor

REF = "__REF__"
DD = "https://raw.githubusercontent.com/AnEntrypoint/dawdreamer/" + REF + "/tools/piano-diag/"
MC = "https://raw.githubusercontent.com/AnEntrypoint/mc-420/"
MC_NORM = "4e38a47d5911f1976f44eaa3383cc3680c833274"
MC_SHIP = "b563a62a871bf8cfabbc7510da7ee2ffebc7386d"
FAUST = "2.85.9"
FAUSTLIB = "78a72d4998dec43e20492ef9b78d1a785b3dc864"
PIN_NORM = "ba2529866947b904772704264fea894971ce3e2c3b0c6ff532de3c4b93288e78"
PIN_SHIPPED = "cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0"
RAW_PIN = {
    "violin_high_sulE_C7E7": "5c6bc8d11ee16aeb65e4d02c68a70873ca6d154d1c99553fde0c4a9ea5b8a993",
    "xylophone_run_C7B7": "27953dd0d6a540c0be6e201cc204ab8fe6110581600760c868dc5991e39c94ed",
    "violin_low_sulG_G3B3": "b6a2b4e1e31db0cd1a34d0f007b25e3c666eeff30228cc66d781a5ee83e6d663",
}
PINNED = ["-vec", "-fun", "-dfs", "-vs", "32", "-nvi", "-ct", "0"]
GAIN = "1.0"
STUB_C = ("void *set_curterm(void *t){return 0;} int setupterm(const char *t,int fd,int *e){if(e)*e=0;return -1;}"
          " int tigetnum(const char *c){return -1;} int del_curterm(void *t){return 0;}\n")
W = "/kaggle/working/pin192-subblock"


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


def main():
    global ARCH, LIBS, ENV
    os.makedirs(W, exist_ok=True)
    os.chdir(W)
    for d in ("raw", "level", "out", "builds"):
        os.makedirs(d, exist_ok=True)
    for name in ["subblock_patch.py", "render_subblock.cpp", "faust_cli.cpp"]:
        fetch(DD + name, name)
    say("harness ref", REF)
    fetch(MC + MC_SHIP + "/effects/pitchtracker-src/pitchtracker_ac.dsp", "shipped.dsp")
    pin("shipped", "shipped.dsp", PIN_SHIPPED)
    for name, want in RAW_PIN.items():
        fetch(MC + MC_NORM + "/test-audio-corpus/instruments/" + name + ".wav", "raw/" + name + ".wav")
        pin(name, "raw/" + name + ".wav", want)
    fetch(MC + MC_NORM + "/tools/corpus-level/normalise-corpus.mjs", "normalise-corpus.mjs")
    pin("normaliser", "normalise-corpus.mjs", PIN_NORM)
    must(["node", "normalise-corpus.mjs", "--src", "raw", "--out", "level", "--rms", "0.1"])
    for name in RAW_PIN:
        say("level", name, sha_file("level/" + name + ".wav"))
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
    must(["python3", "subblock_patch.py", "shipped.dsp", "instr.dsp"])
    variants = [("ship", "shipped.dsp"), ("instr", "instr.dsp")]

    def build(item):
        tag, dsp = item
        vdir = os.path.join(W, "builds", tag)
        os.makedirs(vdir, exist_ok=True)
        shutil.copy(dsp, os.path.join(vdir, "in.dsp"))
        must([os.path.join(W, "faust_cli"), "-lang", "cpp"] + PINNED + ["-I", LIBS, "in.dsp", "-o", "dsp.cpp"],
             cwd=vdir, env=ENV)
        shutil.copy(os.path.join(W, "render_subblock.cpp"), os.path.join(vdir, "render_subblock.cpp"))
        must(["g++", "-O3", "-std=c++17", "-I", ARCH, "render_subblock.cpp", "-o", "render"], cwd=vdir)
        say("built", tag)

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(build, variants))

    def render(job):
        tag, name = job
        vdir = os.path.join(W, "builds", tag)
        pre = os.path.join(W, "out", tag + "__" + name)
        r = must([os.path.join(vdir, "render"), GAIN, pre, os.path.join(W, "level", name + ".wav")], cwd=vdir)
        say("rendered", tag, name, (r.stderr or "").strip())
        return job

    jobs = [(tag, name) for tag in ("ship", "instr") for name in RAW_PIN]
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(render, jobs))
    report()
    cleanup()


def report():
    summary = {"harness_ref": REF, "faust": FAUST, "pinned_flags": " ".join(PINNED), "cxx": "g++ -O3",
               "gain": GAIN, "shipped_sha256": sha_file("shipped.dsp"), "jobs": {}}
    for name in RAW_PIN:
        ship = os.path.join(W, "out", "ship__" + name + "_ch0.f32")
        inst = os.path.join(W, "out", "instr__" + name + "_ch0.f32")
        tsv = os.path.join(W, "out", "instr__" + name + ".tsv")
        rows = sum(1 for _ in open(tsv)) - 1
        tsv_sha = sha_file(tsv)
        with open(tsv, "rb") as src, gzip.open(tsv + ".gz", "wb", compresslevel=9) as dst:
            shutil.copyfileobj(src, dst)
        os.remove(tsv)
        ship_sha = sha_file(ship)
        inst_sha = sha_file(inst)
        summary["jobs"][name] = {
            "level_sha256": sha_file("level/" + name + ".wav"),
            "frames": os.path.getsize(inst) // 4,
            "trace_rows": rows,
            "trace_sha256": tsv_sha,
            "trace_file": "out/instr__" + name + ".tsv.gz",
            "ship_out_sha256": ship_sha,
            "instr_out_sha256": inst_sha,
            "out_bit_equal_to_shipped": ship_sha == inst_sha,
        }
        say(name, "rows", rows, "trace_sha256", tsv_sha, "out_bit_equal", ship_sha == inst_sha)
    json.dump(summary, open(os.path.join(W, "summary.json"), "w"), indent=2)


def cleanup():
    for p in ["faust-lib", "faust-src", "faust-libs", "raw", "level", "builds"]:
        shutil.rmtree(os.path.join(W, p), ignore_errors=True)
    for p in ["libfaust.zip", "faust.tar.gz", "faustlibs.tar.gz", "faust_cli", "faust_cli.cpp", "stub.c", "stub.o",
              "normalise-corpus.mjs", "shipped.dsp", "instr.dsp", "subblock_patch.py", "render_subblock.cpp"]:
        path = os.path.join(W, p)
        if os.path.exists(path):
            os.remove(path)
    for f in os.listdir(os.path.join(W, "out")):
        if f.endswith("_ch0.f32"):
            os.remove(os.path.join(W, "out", f))
    say("cleanup done; remaining:", sorted(os.listdir(W)))


if __name__ == "__main__":
    main()
