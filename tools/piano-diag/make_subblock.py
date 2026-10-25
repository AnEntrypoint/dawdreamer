import json, os, sys

ref, outdir = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(outdir, exist_ok=True)
source = open(os.path.join(here, "kernel_subblock_template.py")).read().replace("__REF__", ref)
open(os.path.join(outdir, "kernel.py"), "w").write(source)
meta = {
    "id": "heclgang/pin192-subblock",
    "title": "pin192 subblock",
    "code_file": "kernel.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": True,
    "enable_gpu": False,
    "enable_internet": True,
    "dataset_sources": [],
    "competition_sources": [],
    "kernel_sources": [],
}
json.dump(meta, open(os.path.join(outdir, "kernel-metadata.json"), "w"), indent=2)
