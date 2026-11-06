# Pre-registration: resonode prototype round 5, variant r5a
# Registered 2026-11-06 by dawdreamer-bd, BEFORE any render.
# Attribution: lanmower only.

## Authority
Owner approved the Kaggle lane for all issues via orchestrator-86. This file is
the SEPARATE variant pre-registration commit required by
tools/resonode-audit/prereg-proto5.txt: "No variant is pre-registered here.
Round 5 variants are not chosen by this file. A variant is added by a separate
pre-registration commit before its render."

## Threshold (UNCHANGED)
M1 envelope follow: median Pearson r >= 0.30 on the vocal set. Definition
unchanged from prereg-proto5.txt: 20 ms RMS envelope (window 960 samples, same
definition for input and output), over the input active window after the
0.5 s pre-roll, six vocal_* files of the audit corpus, M mode, defaults
otherwise. No threshold is added, removed, lowered or changed. The fixed
verdict rule is unchanged: a variant passes round 5 only if EVERY threshold in
prereg-proto5.txt holds (M1 0.30, M4, R1, P1, P2, P3, control keys 48 and 60,
and key-only bit-identity). Inputs are NOT re-cut; no number in this file is
changed after results are seen.

## Variant r5a (the single round-5 candidate)
Base: the shipped resonode_synth.dsp, sha256
9afb3b32d5851ae554aaaf513f70dbdcf804257a29c79cc937f0b2f631f8ec8e (the DSP sha
pinned by tools/resonode-audit/build_kernel.py).

r5a = the round-2 best variant R2b, chosen because it is the best measured M1
across rounds 1-4 (0.2905, round 2) and is therefore the nearest admissible
candidate to the re-registered 0.30 target. It is exactly the two edits from
tools/resonode-audit/proto2_variants.py EDITS["r2b"]:
  1. "    ratioExponent = 1.0 + stretch + stretchJitterAmt*noteJitter(note, gate);"
     -> "    ratioExponent = 1.0 + 0.15*stretch + stretchJitterAmt*noteJitter(note, gate);"
  2. 'decayTime = hslider("fx/resonode/decay", 1.2, 0.05, 8.0, 0.001) : morphGlide;'
     -> 'decayTime = hslider("fx/resonode/decay", 0.4, 0.05, 8.0, 0.001) : morphGlide;'
No other edit. Output-amplitude modulation remains out of scope by the owner's
earlier decision in prereg-proto5.txt. The instrumented/shipped comparison,
render harness, normaliser and corpus are the pinned ones in
tools/resonode-audit/.

## Fixed reporting rule
Report the M1 value verbatim, whether it passes or fails, along with the
sha256 of every fetched source, the kernel id and one results blob sha256.
The CI/round-2 0.2905 figure is NOT treated as verified until this run
reproduces it. A failing M1 is reported as failing; no threshold is moved
to make it pass.

## What this run does not do
It does not close the row, change any acceptance text, add a variant after
seeing numbers, or decide any gate-row wording. Gate rows stay open.

## Witness
One Kaggle kernel id, one results blob sha256, one gm witness dispatch id.
