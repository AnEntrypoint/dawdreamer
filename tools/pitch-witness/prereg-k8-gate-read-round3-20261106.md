# Pre-registration: k8 S1 diagnosis, ROUND 3 (final round, the gate read)
# Registered 2026-11-06 by dawdreamer-bd, BEFORE any render. Attribution: lanmower only.

## Authority
orchestrator-86 ruling after round 2: P_ready, P_confident and P_rawFreq each PASS
S1 on all 39 inputs (117/117 comparisons identical), satisfying the bit-identity
precondition. Round 3 is GO as the FINAL round and is the GATE READ. After round 3
this side is done with diagnosis and stops. Thresholds and acceptance wording are
unchanged; the four gate rows stay open; no row is closed. The report goes to
orchestrator-86 as the record.

## The 23 silent inputs (fixed by name, before render)
   1. balloon_pop_transient
   2. bassoon_low_C2B2
   3. bells_glock_run_C6B6
   4. crotale_high_C7
   5. cymbal_inharmonic
   6. glockenspiel_high_C7
   7. guitar_pluck_C4B4
   8. marimba_low_C2B2
   9. oboe_mid_C5B5
  10. piano_high_C7
  11. piano_low_A1
  12. piano_mid_C4
  13. tamtam_inharmonic
  14. trumpet_high_C6
  15. trumpet_low_A3
  16. tuba_run_C2B2
  17. vibraphone_mid_C5B5
  18. violin_high_sulE_C7E7
  19. violin_low_sulG_G3B3
  20. vocal_melody_twinkle_CC0
  21. vocal_tenor_operatic_PD
  22. xylophone_roll_AM_C6B6
  23. xylophone_run_C7B7

## The three named ready-but-unvoiced inputs (fixed)
  - crotale_high_C7
  - vocal_melody_twinkle_CC0
  - vocal_tenor_operatic_PD

## The 20 gate-silent corpus files (the other 20 of the 23)
   1. balloon_pop_transient
   2. bassoon_low_C2B2
   3. bells_glock_run_C6B6
   4. cymbal_inharmonic
   5. glockenspiel_high_C7
   6. guitar_pluck_C4B4
   7. marimba_low_C2B2
   8. oboe_mid_C5B5
   9. piano_high_C7
  10. piano_low_A1
  11. piano_mid_C4
  12. tamtam_inharmonic
  13. trumpet_high_C6
  14. trumpet_low_A3
  15. tuba_run_C2B2
  16. vibraphone_mid_C5B5
  17. violin_high_sulE_C7E7
  18. violin_low_sulG_G3B3
  19. xylophone_roll_AM_C6B6
  20. xylophone_run_C7B7

## The three candidate signals to read (fixed)
Each candidate is the shipped pitchtracker_ac.dsp at b563a62a, sha256
cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0, with the SINGLE
substitution `process(sig) = holdLastGood(rawFreq, ready, confident)` ->
`process(sig) = holdLastGood(rawFreq, ready, confident), <signal>`:
- P_ready reads `ready` (energyReady: holdCount >= 1680).
- P_confident reads `confident` (finalConfidence >= corrThresh 0.85).
- P_rawFreq reads `rawFreq` (pitch after minTrackHz 60 / maxTrackHz 1500 clamp).
Channel 1 of each 2-output candidate is the signal; channel 0 is the shipped
published pitch. These are exactly the three DSPs that passed S1 in round 2.
A substitution not found verbatim, or a sha mismatch, makes the run VOID.

## Fixed render conditions
Gain 0.00707945784384138 applied uniformly as a float32 multiply BEFORE compute;
Faust 2.85.9 libfaust, faustlibraries 78a72d4998dec43e20492ef9b78d1a785b3dc864;
compiled with ONLY -I flags; g++ -O2 -std=c++17; 48000 Hz; 4800-sample compute
blocks; signal sampled at every 64-sample block end. Only the 23 named silent
inputs are rendered in this round. Channel 0 is also recorded so the shipped output
can be checked against V0; that check is a measurement, not a new S1 verdict.

## Reconciliation rule (fixed, from the clause; NOT reinterpreted here)
The 23 silent inputs reconcile as exactly 20 gate-silent corpus files plus the
3 named ready-but-unvoiced inputs. Each named input carries its witnessed cause:
its own measured gate-signal values. REPORT THE COUNTS AS MEASURED, with no verdict
beyond that. No threshold may be added after results are seen.

## Reporting rule (fixed before render)
For EACH of the 23 inputs and EACH of the three candidate signals, report verbatim
from the settled window (t >= 1.0 s): settled_blocks, first_t, last_t, min, max,
mean, median, fraction_above_0_5, fraction_zero, and the first 12 sampled values.
The full per-block sequences are stored in results.json. Report the reconciliation
counts (20 gate-silent + 3 named) as measured, and each named input's signals
verbatim. Report each candidate's libfaust factory SHA key. No number in this file
may be added, removed or changed after a result is seen.

## Explicitly out of scope
No new threshold, no reinterpretation of the clause, no verdict, no fix, no causal
claim, no row close, no acceptance-text change, no input re-cut. G4 (+116.95 c on
marimba_low_C2B2) and R3 (pin 21/24 at both taus) stay FAILING and are reported as
they are. This is the THIRD and FINAL round; no further diagnosis kernel is run.

## Witness
One Kaggle kernel id, one results blob sha256 and one gm witness dispatch id are
sent to orchestrator-86 and 420 after the run.
