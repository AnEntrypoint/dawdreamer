#!/usr/bin/env python3
"""Run a .py or .ipynb file as a Kaggle kernel and download its output.

    python3 tools/kaggle/kaggle_run.py SCRIPT OWNER/KERNEL-SLUG [options]

Stages the file with a generated kernel-metadata.json in a temp folder, pushes
it with the kaggle CLI, polls `kaggle kernels status` until the run finishes,
then saves the execution log and the kernel's /kaggle/working files under
tools/kaggle/out/KERNEL-SLUG/STAMP/. The kaggle CLI reads its own credentials
from ~/.kaggle; this file never opens or prints them.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
KERNEL_RE = re.compile(r"^[\w.-]+/[a-z0-9][a-z0-9-]*$")
URL_RE = re.compile(r"https://www\.kaggle\.com/code/[^\s\"']+")
STATE_RE = re.compile(r"status\W+(?:\w+\.)?([A-Za-z_]+)", re.IGNORECASE)
FINISHED_OK = {"COMPLETE"}
FINISHED_BAD = {"ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED"}
FINISHED = FINISHED_OK | FINISHED_BAD
EXIT_OK, EXIT_KERNEL_FAILED, EXIT_USAGE, EXIT_TIMEOUT = 0, 1, 2, 3


def fail(message, code=EXIT_USAGE):
    print(f"kaggle_run: {message}", file=sys.stderr)
    raise SystemExit(code)


def kaggle(*args):
    exe = shutil.which("kaggle")
    if exe is None:
        fail("kaggle CLI not found on PATH; see tools/kaggle/README.md")
    try:
        proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return 124, f"kaggle {args[0]} {args[1]} timed out after 300s"
    return proc.returncode, proc.stdout + proc.stderr


def kernel_metadata(script, kernel, internet):
    return {
        "id": kernel,
        "title": kernel.split("/", 1)[1],
        "code_file": script.name,
        "language": "python",
        "kernel_type": "script" if script.suffix == ".py" else "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": internet,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }


def kernel_state(kernel):
    _, text = kaggle("kernels", "status", kernel)
    match = STATE_RE.search(text)
    if match:
        return match.group(1).upper(), text
    return "UNKNOWN", text


def wait_for_kernel(kernel, poll, max_wait):
    started = time.monotonic()
    last = None
    while True:
        state, text = kernel_state(kernel)
        if state != last:
            detail = f" {text.strip()}" if state == "UNKNOWN" else ""
            print(f"[{time.monotonic() - started:6.0f}s] {state}{detail}", flush=True)
            last = state
        if state in FINISHED or time.monotonic() - started >= max_wait:
            return state
        time.sleep(poll)


def run(args):
    script = args.script.resolve()
    if script.suffix not in {".py", ".ipynb"} or not script.is_file():
        fail(f"need an existing .py or .ipynb file: {args.script}")
    if not KERNEL_RE.match(args.kernel):
        fail(f"kernel must be OWNER/kernel-slug (lowercase, digits, hyphens): {args.kernel}")

    name = args.kernel.split("/", 1)[1]
    max_wait = args.max_wait or args.timeout + 900
    staging = Path(tempfile.mkdtemp(prefix=f"kaggle-{name}-"))
    try:
        shutil.copy2(script, staging / script.name)
        meta = kernel_metadata(script, args.kernel, args.internet)
        (staging / "kernel-metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
        if args.dry_run:
            print(json.dumps(meta, indent=2))
            return EXIT_OK

        code, text = kaggle("kernels", "push", "-p", str(staging), "-t", str(args.timeout))
        if code != 0:
            fail(f"push failed:\n{text.strip()}", EXIT_KERNEL_FAILED)
        url_match = URL_RE.search(text)
        url = url_match.group(0) if url_match else f"https://www.kaggle.com/code/{args.kernel}"
        print(f"pushed {args.kernel}\nurl {url}", flush=True)

        state = wait_for_kernel(args.kernel, args.poll, max_wait)
        if state not in FINISHED:
            print(f"gave up after {max_wait}s in state {state}; the kernel may still be running", file=sys.stderr)
            return EXIT_TIMEOUT

        out = args.out / name / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out.mkdir(parents=True, exist_ok=True)
        _, logs = kaggle("kernels", "logs", args.kernel)
        (out / "kernel.log").write_text(logs)
        dl_code, dl_text = kaggle("kernels", "output", args.kernel, "-p", str(out), "-o", "-q")
        if dl_code != 0:
            print(f"output download exited {dl_code}: {dl_text.strip()}", file=sys.stderr)
        files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
        summary = {"kernel": args.kernel, "url": url, "state": state, "timeout_s": args.timeout, "files": files}
        (out / "run.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(f"state {state}\noutput {out}\nfiles {' '.join(files)}")
        return EXIT_OK if state in FINISHED_OK else EXIT_KERNEL_FAILED
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a .py or .ipynb file as a Kaggle kernel and download its output.")
    parser.add_argument("script", type=Path, help="file to run: .py or .ipynb")
    parser.add_argument("kernel", help="OWNER/KERNEL-SLUG, e.g. heclgang/dawdreamer-kaggle-probe")
    parser.add_argument("--timeout", type=int, default=3600, help="kernel run limit in seconds (default 3600)")
    parser.add_argument("--internet", action="store_true", help="let the kernel reach the internet (off by default)")
    parser.add_argument("--poll", type=int, default=15, help="seconds between status checks (default 15)")
    parser.add_argument("--max-wait", type=int, help="seconds to wait before giving up (default: timeout + 900)")
    parser.add_argument("--out", type=Path, default=HERE / "out", help="download root (default tools/kaggle/out)")
    parser.add_argument("--dry-run", action="store_true", help="print kernel-metadata.json and stop before pushing")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
