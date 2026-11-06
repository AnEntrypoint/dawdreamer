# Pre-registration: diagnosis of the k8 S1 bit-identity failure
# Registered 2026-11-06 by dawdreamer-bd, BEFORE any render. Attribution: lanmower only.

## Authority
orchestrator-86 ruling: k8 S1 failed on 37 of 39 inputs, so no gate reading exists
and none is to be read. The four gate rows stay open with wording unchanged. The
failure is a FINDING, not a verdict. ONE diagnosis is allowed to find why the
instrumented copy diverges from the shipped DSP. A new gate-signal run is allowed
only after a new design passes S1 on all 39 inputs under its own pre-registration.
This run reads NO gate values and applies NO fix.

## Question (fixed)
Why does adding extra outputs to the shipped `pitchtracker_ac.dsp` change its
channel-0 output? No hypothesis about the cause is registered as a verdict; the
run reports measurements only.

## Fixed inputs
- Shipped DSP: `effects/pitchtracker-src/pitchtracker_ac.dsp` at `b563a62a`,
  sha256 cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0.
  A sha mismatch makes the run VOID.
- Three exactly-fixed render inputs, at gain 0.00707945784384138 applied uniformly
  as a float32 multiply before compute: `sine_440` (from make_sines.py), 
  `vocal_female_vibrato.wav` and `crotale_high_C7.wav` (34-file manifest).
  All rendered in 4800-sample blocks, 48000 Hz, 1 input channel.
- Harness: Faust 2.85.9 libfaust, faustlibraries
  78a72d4998dec43e20492ef9b78d1a785b3dc864, compiled with ONLY `-I` flags (no
  -vec/-fun/-dfs/-vs), g++ -O2 -std=c++17. Same flags for every variant.

## Variants (exactly three, fixed before render)
- V0 = shipped DSP, 1 output (channel 0 = published pitch).
- V1 = shipped DSP with process changed to `holdLastGood(rawFreq, ready, confident), 0.0`
  (2 outputs: published pitch plus a constant zero). This isolates whether ANY
  extra output changes codegen.
- V2 = the 8-output instrumented copy used by k8 (ready, confident, finalConfidence,
  env, aboveFloor, holdCount, rawFreq, published_pitch), same transform as k8.

## Fixed measurements (definitions, not thresholds)
For each of V0, V1, V2 and each of the 3 inputs: record the full float32 channel-0
trace; report its length and sha256. For V1 and V2 against V0, report verbatim:
  identical (bool), first_divergent_sample_index (int or null),
  n_diff_samples (int), max_abs_diff (float), and the factory SHA key reported by
  libfaust (`getSHAKey()`) for each variant.
No number in this file may be added, removed or changed after a result is seen.

## Fixed verdict rule
NONE: this is a diagnosis, not a pass/fail experiment. It reports measurements
verbatim and makes no claim that a variant is acceptable. It does NOT read or
report any gate signal value. It does NOT change the shipped DSP, any threshold,
any gate-row acceptance text, or any input. It does NOT close any row.

## Explicitly out of scope
- No gate-signal run, no bit-identity "fix", no new design, and no second kernel
  for this diagnosis. The four gate PRDs remain pending with wording unchanged.
- G4 (+116.95 c on marimba_low_C2B2) and R3 (pin 21/24 at both taus) stay failing
  and are reported as they are, not re-evaluated here.

## Witness
One Kaggle kernel id, one results blob sha256 and one gm witness dispatch id are
sent to orchestrator-86 and 420 after the run.
