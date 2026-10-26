#!/bin/sh
set -eu

SHA="$1"
OUT="$2"
MODE="${3:-version}"
REPO=/config/workspace/DawDreamer
MC420=/config/workspace/mc-420
DSPREV=72a872faa99df6f5f4b703d654910e1dd519481d
STAGE="$OUT/stage"
DSET="$OUT/dataset"
KDIR="$OUT/kernel"

rm -rf "$STAGE" "$DSET" "$KDIR"
mkdir -p "$STAGE" "$DSET" "$KDIR"

git -C "$REPO" show "$SHA:tools/loop-witness/loop_witness.cpp" > "$STAGE/loop_witness.cpp"
git -C "$REPO" show "$SHA:tools/loop-witness/faust_cli.cpp" > "$STAGE/faust_cli.cpp"
git -C "$REPO" show "$SHA:tools/loop-witness/prereg.txt" > "$STAGE/prereg.txt"
git -C "$REPO" show "$SHA:tools/loop-witness/make_bundle.sh" > "$STAGE/make_bundle.sh"
git -C "$MC420" show "$DSPREV:dsp/loop.dsp" > "$STAGE/loop.dsp"
git -C "$REPO" show "$SHA:tools/loop-witness/run_witness.py" > "$KDIR/run_witness.py"

(cd "$STAGE" && sha256sum loop.dsp loop_witness.cpp faust_cli.cpp prereg.txt > MANIFEST.sha256)
tar -czf "$DSET/inputs.tar.gz" -C "$STAGE" .

cat > "$DSET/dataset-metadata.json" <<'EOF'
{"title": "loop-witness fix-verify inputs", "id": "heclgang/loop-witness-fix-verify-inputs", "licenses": [{"name": "CC0-1.0"}]}
EOF

cat > "$KDIR/kernel-metadata.json" <<'EOF'
{"id": "heclgang/loop-witness-fix-verify", "title": "loop-witness fix-verify", "code_file": "run_witness.py", "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": false, "enable_tpu": false, "enable_internet": true, "dataset_sources": ["heclgang/loop-witness-fix-verify-inputs"], "competition_sources": [], "kernel_sources": [], "model_sources": []}
EOF

if [ "$MODE" = create ]; then
  kaggle datasets create -p "$DSET" -q
else
  kaggle datasets version -p "$DSET" -m "$SHA" -q
fi
kaggle kernels push -p "$KDIR"
