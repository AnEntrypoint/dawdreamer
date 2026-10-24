# Pre-registration: tracker-parameter-sweep

Source row: mc-420 `tracker-parameter-sweep` (owner dawdreamer-kaggle-1). The thresholds and grid below are copied from the row and are not changed by this file.

## Thresholds (fixed)

- S1: median |cents| over voiced scoreable files <= 20.0 c.
- S2: octave-error count = 0.
- S3: cello_low_sulC_A2, trumpet_low_A3 and piano_mid_C4 each within 25 c of peak.
- S4: beat the shipped baseline on median |cents| by at least 2.0 c, measured in the same run.

## Grid

- refineSpreadK: 1, 4, 8, 16, and the current min(16, max(4, round(0.1*L))).
- corrAtLagTau: 0.005, 0.01, 0.02, 0.04 s.
- demote margin: 0.002, 0.004, 0.008.
- onsetHoldMs: 15, 35, 60.
- confidenceGate: 0.75, 0.85, 0.92.

Each axis is varied alone first, then the best combination.

## Addendum 2026-10-24

ADDENDUM (recorded before any sweep render; S1–S4 and the grid are unchanged)

1. Input: the level-normalised corpus, from mc-420 tools/corpus-level/normalise-corpus.mjs at 4e38a47d, rms 0.1, peak cap 0.9, harness gain 1.0. The corpus gain 0.00707945784384138 is not used, because 27 of 34 files sit at or below the energyReady floor there. Results are level-normalised and are not read against corpus-gain numbers.
2. Scored set: the 10 scoreable files in docs/witness/corpus-pitch-reference.md: piano_mid_C4, marimba_low_C2B2, cello_low_sulC_A2, trumpet_high_C6, soprano_sax_high_C6, clarinet_high_C6B6, bassoon_low_C2B2, violin_low_sulG_G3B3, trumpet_low_A3, guitar_pluck_C4B4. Each target is that file's measured peak in the table, never the filename label. Phrase files and files with no certified peak are reported but not scored. Sines are a separate column and are outside S1–S2.
3. Baseline: the shipped configuration, measured in the same run. The control readings quoted in the row are not a baseline and are re-measured.
4. Octave error: a settled value more than 600 c from its certified peak.
5. Best combination: for each axis, the value with the lowest median |cents| among single-axis configurations that pass S2 and S3. The per-axis winners are combined, rendered once, and ranked with the rest.

## Addendum 2026-10-24 (second, before any sweep render)

Mapping decisions D1–D4. S1–S4 and the grid are unchanged.

D1. corrAtLagTau axis (coarse tau). A value v sets one uniform energy tau v for every frequency band. The baseline keeps the shipped tiering: 0.01 below 575 Hz, 0.02 at or above. Grid 0.005, 0.01, 0.02, 0.04 s: four builds.

D2. confidenceGate axis (output gate). A value g sets only the detector output gate, confident = finalConfidence >= g. corrThresh stays 0.85 and still gates peak picking. The baseline is g = 0.85, which must reproduce the shipped output on one file before the sweep. The literal confidenceGate in multitranspose.dsp is out of scope: the existing harness, tools/render-gate/render_gate.cpp, compiles the single DSP file it is given and renders only that file, with no multitranspose path. The sweep renders pitchtracker_ac.dsp alone.

D3. S3, both checks must hold. (i) |reading| <= 25 c against the certified peak, the formal PASS line. (ii) For each of cello_low_sulC_A2, trumpet_low_A3 and piano_mid_C4: |candidate cents| - |baseline cents| <= 25 c. This is the stricter of the two readings in the row.

D4. Refine tau axis. A second tau axis sets the energy tau of corrAtLagVar only, which feeds refineFreq, corrPeakAt and corrRawAt. The coarse tau stays at the shipped tiering. The baseline is 0.01, the shipped corrAtLagVar value. Grid 0.005, 0.02, 0.04 s: three builds. The 0.01 value is the baseline and is not rebuilt.

Combination (applies item 5 to all six axes): coarse tau, refine tau, refineSpreadK, demote margin, onsetHoldMs and output gate. The per-axis winners are combined and the combined build is rendered once. The per-configuration table reports which path each tau result came from (coarse-only or refine-only), so the two can be read apart.
