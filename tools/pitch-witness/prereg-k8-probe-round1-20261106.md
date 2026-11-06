# Pre-registration: k8 S1 diagnosis, ROUND 1 (single-probe variants)
# Registered 2026-11-06 by dawdreamer-bd, BEFORE any render. Attribution: lanmower only.

## Authority
orchestrator-86 ruling after k11 (V1 bit-identical, V2 diverges at samples 1761 /
35101 / 4578, NO causal claim). GO on ONE more diagnosis line with these limits,
all accepted here:
1. Each round gets its own prereg, committed before its kernel, naming the exact
   variant set.
2. Each variant adds ONE gate-signal output to the shipped DSP so the break can be
   traced to a single probe. Compare each variant to V0 on the same three fixed
   inputs as in k11.
3. A variant bit-identical on all three inputs is a CANDIDATE; it must then pass S1
   on all 39 inputs under its own prereg before any gate value is read.
4. Stop after THREE rounds and report, even if no candidate emerges.
5. No gate values are read in these rounds. No threshold, acceptance text or input
   changes. The four gate rows stay open with wording unchanged.
6. Each round's results are reported verbatim, with no verdict beyond the measurement.

## Fixed inputs (unchanged from k11)
- Shipped DSP: `effects/pitchtracker-src/pitchtracker_ac.dsp` at `b563a62a`,
  sha256 cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0.
  A sha mismatch makes the run VOID.
- Three exactly-fixed render inputs at gain 0.00707945784384138 applied uniformly
  as a float32 multiply before compute: `sine_440` (from make_sines.py),
  `vocal_female_vibrato.wav` and `crotale_high_C7.wav` (34-file manifest).
  All rendered in 4800-sample blocks, 48000 Hz, 1 input channel.
- Harness: Faust 2.85.9 libfaust, faustlibraries
  78a72d4998dec43e20492ef9b78d1a785b3dc864, compiled with ONLY `-I` flags (no
  -vec/-fun/-dfs/-vs), g++ -O2 -std=c++17. Same flags for every variant.
- The driver reads ONLY channel 0 (the shipped published-pitch output). It does NOT
  read, print or store any gate-signal value.

## EXACT ROUND-1 VARIANT SET (four DSPs, named before render)
- V0 = shipped DSP, 1 output.
- P_ready = shipped text with the single substitution
  `process(sig) = holdLastGood(rawFreq, ready, confident)` ->
  `process(sig) = holdLastGood(rawFreq, ready, confident), ready`
  (exactly ONE extra output: `ready`).
- P_confident = same substitution with `, confident` as the single extra output.
- P_rawFreq = same substitution with `, rawFreq` as the single extra output.
No other edit to any definition. `ready`, `confident` and `rawFreq` are already
defined in the shipped `process` with-block. If any of the three substitutions is
not found verbatim, the run is VOID and reports that only.

## Fixed measurements (definitions, not thresholds)
For each of V0, P_ready, P_confident, P_rawFreq and each of the three inputs:
record the full float32 channel-0 trace; report its length and sha256, plus the
libfaust factory SHA key (`getSHAKey()`) for each variant. For each of the three
probes against V0, report verbatim: identical (bool), first_divergent_sample_index
(int or null), n_diff_samples (int), max_abs_diff (float), v0_len, variant_len.
No number in this file may be added, removed or changed after a result is seen.

## Fixed verdict rule
NONE beyond measurement. A probe bit-identical on all three inputs is reported as
a CANDIDATE for the next round's S1-on-39 test under its own prereg; that test is
NOT performed in this round. No causal claim, no fix, no verdict, no gate value.
This run does NOT change the shipped DSP, any threshold, any gate-row acceptance
text, or any input. It does NOT close any row.

## Explicitly out of scope
- No gate-signal run, no 39-input S1 test in this round. The four gate PRDs remain
  pending with wording unchanged. G4 (+116.95 c on marimba_low_C2B2) and R3
  (pin 21/24 at both taus) stay failing and are reported as they are, not
  re-evaluated here.
- No second kernel in this round. Rounds 2 and 3 (if reached) get their own preregs
  and kernels. STOP after three rounds.

## Witness
One Kaggle kernel id, one results blob sha256 and one gm witness dispatch id are
sent to orchestrator-86 and 420 after the run.
