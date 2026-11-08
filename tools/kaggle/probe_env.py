"""Kaggle smoke test: report this runtime's Python, CPU count and memory.

The report is printed and saved as probe.json in /kaggle/working, which the runner downloads.
"""
import json
import os
import platform
import sys
from pathlib import Path


def total_memory_gib():
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 1024 ** 2, 2)
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3, 2)
    except (AttributeError, ValueError, OSError):
        return None


report = {
    "python": sys.version.split()[0],
    "implementation": platform.python_implementation(),
    "platform": platform.platform(),
    "cpu_count": os.cpu_count(),
    "memory_total_gib": total_memory_gib(),
}
destination = Path("/kaggle/working")
if not destination.is_dir():
    destination = Path.cwd()
(destination / "probe.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
