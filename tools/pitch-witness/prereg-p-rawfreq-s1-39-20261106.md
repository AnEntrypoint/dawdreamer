# Pre-registration: k8 S1 diagnosis, ROUND 2, candidate P_rawFreq
# Registered 2026-11-06 by dawdreamer-bd, BEFORE any render. Attribution: lanmower only.

## Authority
orchestrator-86 ruling after round 1: all three single-probe variants (P_ready,
P_confident, P_rawFreq) were bit-identical to V0 on three fixed inputs, so each is
a CANDIDATE and must pass S1 on all 39 inputs under its OWN prereg before any gate
value is read. This is round 2 of three; round 3 is held until orchestrator-86 has
read round 2. No gate values are read in round 2. A candidate that fails S1 is
recorded as failed and not used. Thresholds and acceptance wording are unchanged;
the four gate rows stay open.

## Candidate (exact, fixed)
P_rawFreq = shipped `pitchtracker_ac.dsp` at b563a62a, sha256
cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0, with the SINGLE
substitution on the shipped process line:
  `process(sig) = holdLastGood(rawFreq, ready, confident)` ->
  `process(sig) = holdLastGood(rawFreq, ready, confident), rawFreq`
ONE extra output, NO other edit. A substitution not found verbatim makes the run VOID.
V0 = the unmodified shipped DSP.

## The 39 inputs (named here, fixed before render; gain 0.00707945784384138 applied
## uniformly as a float32 multiply BEFORE compute)
   1. balloon_pop_transient.wav
   2. bassoon_low_C2B2.wav
   3. bells_glock_run_C6B6.wav
   4. cello_low_sulC_A2.wav
   5. clarinet_high_C6B6.wav
   6. crotale_high_C7.wav
   7. cymbal_inharmonic.wav
   8. flute_high_C7.wav
   9. flute_trill_high_C7.wav
  10. glockenspiel_high_C7.wav
  11. guitar_pluck_C4B4.wav
  12. marimba_low_C2B2.wav
  13. marimba_mid_C5B5.wav
  14. marimba_roll_AM_C5B5.wav
  15. oboe_mid_C5B5.wav
  16. piano_high_C7.wav
  17. piano_low_A1.wav
  18. piano_mid_C4.wav
  19. soprano_sax_high_C6.wav
  20. tamtam_inharmonic.wav
  21. trumpet_high_C6.wav
  22. trumpet_low_A3.wav
  23. tuba_run_C2B2.wav
  24. vibraphone_mid_C5B5.wav
  25. violin_high_sulE_C7E7.wav
  26. violin_low_sulG_G3B3.wav
  27. vocal_female_vibrato.wav
  28. vocal_male_baritone_scale.wav
  29. vocal_melody_twinkle_CC0.wav
  30. vocal_soprano_range_PD.wav
  31. vocal_tenor_operatic_PD.wav
  32. vocal_tenor_range_PD.wav
  33. xylophone_roll_AM_C6B6.wav
  34. xylophone_run_C7B7.wav
  35. sine_55.69.wav
  36. sine_110.wav
  37. sine_220.wav
  38. sine_440.wav
  39. sine_1000.wav

## Harness (fixed)
Faust 2.85.9 libfaust, faustlibraries 78a72d4998dec43e20492ef9b78d1a785b3dc864,
compiled with ONLY -I flags (no -vec/-fun/-dfs/-vs), g++ -O2 -std=c++17, 48000 Hz,
4800-sample blocks, 1 input channel. The driver reads ONLY channel 0 (the shipped
published-pitch output); it does NOT read, print or store any gate-signal value.

## S1 criterion (fixed)
For EVERY one of the 39 inputs, compare this candidate's full float32 channel-0
trace to V0's, sample for sample. Report per input, verbatim: identical (bool),
first_divergent_sample_index (int or null), n_diff_samples (int), max_abs_diff
(float), v0_len, candidate_len, and sha256 of each trace. Also report the libfaust
factory SHA key (getSHAKey()) for V0 and for this candidate.

## Pass/fail rule (fixed before render)
- S1 PASS iff `identical` is true for ALL 39 inputs.
- S1 FAIL if ANY input has identical=false; report that input's first divergent
  index verbatim. No number in this file may be added, removed or changed after a
  result is seen. No verdict beyond the S1 measurement is made here.

## Explicitly out of scope
No gate-signal run, no gate value read, no fix, no causal claim, no row close, no
threshold or acceptance-text change, no input re-cut. G4 (+116.95 c on
marimba_low_C2B2) and R3 (pin 21/24 at both taus) stay FAILING and are reported as
they are, not re-evaluated here. Stop after three rounds.

## Witness
One Kaggle kernel id, one results blob sha256 and one gm witness dispatch id are
sent to orchestrator-86 and 420 after the run.
