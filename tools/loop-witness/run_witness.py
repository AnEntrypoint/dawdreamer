import hashlib
import os
import shutil
import subprocess
import tarfile
import zipfile

DSP_SHA = "dd50018ea3f94c213d16bf2e448e8d7a25615bce7a77498a3324acedc14377e3"
FAUST = "2.85.9"
FAUSTLIB_SHA = "78a72d4998dec43e20492ef9b78d1a785b3dc864"
WORK = "/kaggle/working"
RESULTS = os.path.join(WORK, "results.txt")
LIBFAUST_URL = "https://github.com/grame-cncm/faust/releases/download/%s/libfaust-ubuntu-x86_64.zip" % FAUST
FAUST_SRC_URL = "https://github.com/grame-cncm/faust/archive/refs/tags/%s.tar.gz" % FAUST
FAUSTLIB_URL = "https://github.com/grame-cncm/faustlibraries/archive/%s.tar.gz" % FAUSTLIB_SHA
FLAGS = ["-lang", "cpp", "-vec", "-fun", "-dfs", "-vs", "32", "-nvi", "-ct", "0"]


def sh(args):
    p = subprocess.run(args, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def find_input():
    for root, _dirs, files in os.walk("/kaggle/input"):
        if "inputs.tar.gz" in files:
            return os.path.join(root, "inputs.tar.gz")
        if "loop.dsp" in files and "loop_witness.cpp" in files:
            return root
    return None


def emit(lines):
    text = "\n".join(lines) + "\n"
    with open(RESULTS, "w") as f:
        f.write(text)
    print(text, end="")


def fail(log, msg, detail=""):
    emit(log + ["INCONCLUSIVE " + msg, detail[-3000:]])
    return 1


def main():
    src = find_input()
    if src is None:
        emit(["INCONCLUSIVE no inputs.tar.gz or loop.dsp under /kaggle/input"])
        return 1
    dd = os.path.join(WORK, "dd")
    shutil.rmtree(dd, ignore_errors=True)
    if src.endswith(".tar.gz"):
        os.makedirs(dd)
        with tarfile.open(src, "r:gz") as t:
            t.extractall(dd)
    else:
        shutil.copytree(src, dd)
    os.chdir(dd)

    digest = sha256("loop.dsp")
    log = ["loop.dsp sha256 %s" % digest]
    if digest != DSP_SHA:
        return fail(log, "loop.dsp sha256 != pre-registered %s" % DSP_SHA)
    log.append("loop.dsp sha256 matches the pre-registered value")

    sh(["sh", "-c", "(apt-get update -qq && apt-get install -y -qq libncurses-dev) >/dev/null 2>&1"])

    for url, name in ((LIBFAUST_URL, "libfaust.zip"), (FAUST_SRC_URL, "faust.tar.gz"), (FAUSTLIB_URL, "faustlibs.tar.gz")):
        rc, out = sh(["curl", "-sfL", "--retry", "3", url, "-o", name])
        if rc != 0:
            return fail(log, "fetch failed: " + url, out)
        log.append("fetched %s sha256 %s" % (name, sha256(name)))

    zipfile.ZipFile("libfaust.zip").extractall("faust-lib")
    os.makedirs("faust-src", exist_ok=True)
    rc, out = sh(["tar", "-xzf", "faust.tar.gz", "-C", "faust-src", "--wildcards", "*/architecture/*"])
    os.makedirs("faust-libs", exist_ok=True)
    rc2, out2 = sh(["tar", "-xzf", "faustlibs.tar.gz", "-C", "faust-libs", "--strip-components=1"])
    arch = os.path.abspath("faust-src/faust-%s/architecture" % FAUST)
    libfaust = os.path.abspath("faust-lib/lib/libfaustwithllvm.a")
    libdir = os.path.abspath("faust-libs")
    if not (os.path.isdir(arch) and os.path.isfile(libfaust) and os.path.isfile(os.path.join(libdir, "stdfaust.lib"))):
        return fail(log, "toolchain incomplete", out + out2)

    rc, out = sh(["g++", "-O2", "-std=c++17", "-I", arch, "-I", os.path.abspath("faust-lib"), "faust_cli.cpp",
                  libfaust, "-lz", "-lpthread", "-ldl", "-lm", "-ltinfo", "-o", "faust_cli"])
    if rc != 0:
        return fail(log, "faust_cli build failed", out)
    log.append("faust_cli built (plain recipe) sha256 %s" % sha256("faust_cli"))

    rc, out = sh(["./faust_cli"] + FLAGS + ["-I", libdir, "loop.dsp", "-o", "dsp.cpp"])
    if rc != 0 or not os.path.isfile("dsp.cpp"):
        return fail(log, "faust_cli did not generate dsp.cpp", out)
    log.append("dsp.cpp sha256 %s" % sha256("dsp.cpp"))
    with open("dsp.cpp") as f:
        for line in f:
            if "Compilation options" in line or "Code generated with Faust" in line:
                log.append("dsp.cpp header: " + line.strip())

    rc, out = sh(["g++", "-O3", "-std=c++17", "-I", arch, "loop_witness.cpp", "-o", "loop_witness"])
    if rc != 0:
        return fail(log, "harness build failed", out)
    log.append("harness built g++ -O3 sha256 %s" % sha256("loop_witness"))

    rc, out = sh(["./loop_witness"])
    io_lines = [l for l in out.splitlines() if l.startswith("io inputs=")]
    lines = [l for l in out.splitlines() if not l.startswith("io inputs=")]
    emit(log + ["harness exit rc=%d" % rc] + io_lines[:1] + lines)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(os.path.join(WORK, "dd"), ignore_errors=True)
    raise SystemExit(code)
