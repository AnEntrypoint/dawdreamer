import hashlib
import os
import shutil
import subprocess
import tarfile

DSP_SHA = "1be68dc68d3ccb1e6aa37f17e08f9a8d7a219e97e3007b9d4c25f95c57187c8b"
WORK = "/kaggle/working"
RESULTS = os.path.join(WORK, "results.txt")


def sh(cmd, cwd=None, env=None):
    p = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def find_input():
    for root, _dirs, files in os.walk("/kaggle/input"):
        if "loop.dsp" in files and "loop_witness.cpp" in files:
            return root
        if "inputs.tar.gz" in files:
            return os.path.join(root, "inputs.tar.gz")
    return None


def emit(lines):
    text = "\n".join(lines) + "\n"
    with open(RESULTS, "w") as f:
        f.write(text)
    print(text, end="")


def main():
    src = find_input()
    if src is None:
        emit(["INCONCLUSIVE no loop.dsp, loop_witness.cpp or inputs.tar.gz under /kaggle/input"])
        return 1
    dd = os.path.join(WORK, "dd")
    shutil.rmtree(dd, ignore_errors=True)
    if src.endswith(".tar.gz"):
        os.makedirs(dd)
        with tarfile.open(src, "r:gz") as t:
            t.extractall(dd)
    else:
        shutil.copytree(src, dd)

    with open(os.path.join(dd, "loop.dsp"), "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != DSP_SHA:
        emit(["INCONCLUSIVE loop.dsp sha256 %s != pre-registered %s" % (digest, DSP_SHA)])
        return 1

    sh("apt-get install -y -q libncurses-dev unzip >/dev/null 2>&1 || sudo apt-get install -y -q libncurses-dev unzip >/dev/null 2>&1")

    rc, out = sh("python3 download_libfaust.py --arch x86_64", cwd=os.path.join(dd, "thirdparty", "libfaust"))
    if rc != 0:
        emit(["INCONCLUSIVE libfaust download failed rc=%d" % rc, out[-3000:]])
        return 1

    inc = os.path.join(dd, "thirdparty", "libfaust", "ubuntu-x86_64", "Release")
    lib = os.path.join(inc, "lib", "libfaustwithllvm.a")
    arch = os.path.join(dd, "thirdparty", "faust", "architecture")
    cmd = "g++ -O2 -std=c++17 -I %s -I %s loop_witness.cpp %s -lz -lpthread -ldl -lm -ltinfo -o loop_witness" % (arch, inc, lib)
    rc, out = sh(cmd, cwd=dd)
    if rc != 0:
        emit(["INCONCLUSIVE harness build failed rc=%d" % rc, out[-3000:]])
        return 1

    env = dict(os.environ)
    env["FAUST_LIBRARY_DIR"] = os.path.join(dd, "dawdreamer", "faustlibraries")
    rc, out = sh("./loop_witness loop.dsp", cwd=dd, env=env)
    head = ["loop.dsp sha256 %s (verified)" % digest, "harness exit rc=%d" % rc]
    emit(head + out.splitlines())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
