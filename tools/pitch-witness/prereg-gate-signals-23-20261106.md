# Pre-registration: shipped-DSP gate signals for the 23 silent inputs
# Registered 2026-11-06 by dawdreamer-bd, BEFORE any render.
# Attribution: lanmower only.

## Purpose
Satisfy the ruling by orchestrator-86 on gate-silence-23-of-37-ready-unvoiced:
the acceptance text stays UNCHANGED; v2's DIAG_NOT_SHIPPED.dsp does NOT satisfy
the clause; the clause needs gate signals for all 23 silent inputs from an
instrumented copy of the SHIPPED pitchtracker_ac.dsp. G4 (+116.95 c) and R3
(21/24 at both taus) stay failing and are reported as they are. No threshold is
changed, added, lowered or re-registered by this run.

## The 23 silent inputs (named here, fixed before render)
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

The three named ready-but-unvoiced inputs are crotale_high_C7,
vocal_melody_twinkle_CC0 and vocal_tenor_operatic_PD; the other 20 are the
gate-silent corpus files. This is the exact 23-name before-silent set from
heclgang/mc420-gate-silence-normalised-gain-witness v2 (blob 9866ad61...).

## All 39 inputs (fixed, not re-cut)
The 34 manifest corpus files plus the five make_sines.py sines
(55.69, 110, 220, 440, 1000 Hz), at GAIN 0.00707945784384138 applied
uniformly. Identical to the input set of
heclgang/mc420-shipped-dsp-corpus-gain-witness.

## Gate signals to read (fixed before render)
An instrumented copy of the SHIPPED pitchtracker_ac.dsp
(sha cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0)
exposing, as extra outputs, exactly these internal signals:
  1. ready          (energyReady: holdCount >= 1680)
  2. confident      (finalConfidence >= corrThresh 0.85)
  3. finalConfidence (the numeric value compared with 0.85)
  4. env            (3 ms one-pole of x^2)
  5. aboveFloor     (env > 1e-6)
  6. holdCount      (consecutive samples above floor, capped 1680)
  7. rawFreq        (pitch after minTrackHz 60 / maxTrackHz 1500 clamp)
  8. published_pitch (the shipped DSP's own channel-0 output)
The instrumented copy is compiled with the SAME flags as render_gate.cpp
(only -I), not with the vectorisation flags used by the v2 diagnostic.

## Fixed procedure (registered before any render, not changeable after)
S1 BIT-IDENTITY PROOF FIRST. Render the shipped DSP and the instrumented copy
   on all 39 inputs at the fixed gain and compare channel 0 sample-for-sample
   (sha256 of the full float32 trace per input). If ANY input differs, STOP
   and report the mismatching inputs; no gate-signal reading is reported.
S2 Only if S1 passes for all 39: run ONCE and report, verbatim, for each of
   the 23 silent inputs, the eight gate signals over the settled window
   t >= 1.0 s: first_ready_t, first_published_pitch_t, ready fraction,
   confident fraction, finalConfidence min/max, env min/max, aboveFloor
   fraction, holdCount max, rawFreq median, published nonzero block count.
S3 Completeness: all 23 named inputs must have a gate-signal record. No file
   dropped, substituted or imputed.

## What this run does NOT do
- It does not close any gate row, decide any acceptance wording, or offer
  DIAG_NOT_SHIPPED.dsp as satisfying the clause.
- It does not change G1-G5, T1-T5, the pin-rule 22, or any pitch-row threshold.
- It makes no claim that a gate signal causes a defect unless S1 passes.

## Witness
One Kaggle kernel id, one results blob sha256 and one gm witness dispatch id
are sent to orchestrator-86 and 420 after the run. No mc-420 edits.
