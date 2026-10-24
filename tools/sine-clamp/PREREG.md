# Pre-registration: sine-clamp witness

Peer session 420 owns two mc-420 rows: `defect-sine-2093-subharmonic` and
`defect-tracker-value-clamp-60-192`. This witness runs the variants below and reports
evidence to the peer. It does not close either row.

Fixed before any render. Rules are not changed after numbers are seen.

## Measurement conditions

- Shipped tracker: mc-420 HEAD `b563a62a`, file `effects/pitchtracker-src/pitchtracker_ac.dsp`,
  last changed at commit `e5572527`, sha256 `cea5e4f00533f0364bfd7eb9f62e851029ee9a1301b4ba8566d0c5dc7f4d67e0`.
  Variant `S` is measured in every run. No baseline is taken from earlier numbers.
- Level-normalised corpus: the 34 mc-420 instrument WAVs in the shared dataset
  `heclgang/mc420-dawdreamer-gate-corpus`, verified with `fetch_corpus.py --verify` against
  `manifest.sha256`, then normalised by `tools/corpus-level/normalise-corpus.mjs` at mc-420 commit
  `4e38a47d` (sha256 `ba2529866947b904772704264fea894971ce3e2c3b0c6ff532de3c4b93288e78`) with
  `--rms 0.1 --floor 1e-6`. The peak cap 0.9 is built into that script. Harness gain 1.0.
  The dataset as shipped is not level-normalised (per-file RMS 0.006 to 0.34), so normalisation runs in the kernel.
  The dataset's two DawDreamer WAVs are excluded: they are 24-bit stereo 44.1 kHz and `render_gate.cpp` loads 16-bit only.
- Sines: the six dataset sines `sines/sine_<hz>.wav` (8 s, amplitude 0.3, 48 kHz mono 16-bit) at gain 1.0:
  65.55, 69.75, 110, 440, 1000, 2093 Hz.
- Pitchless additions generated in the kernel: `silence` (8 s of zeros) and `white_noise`
  (8 s, Gaussian sd 0.1 from `random.Random(20261024)`, clipped to plus or minus 0.9, 48 kHz mono 16-bit).
- Renderer: `tools/render-gate/render_gate.cpp`, libfaust 2.85.9, faust-libraries
  `78a72d4998dec43e20492ef9b78d1a785b3dc864`. Every Faust compile passes
  `-vec -fun -dfs -vs 32 -nvi -ct 0` plus `-I $FAUST_LIBRARY_DIR`. Blocks of 4800 samples. A trace line is
  the block-end sample of channel 0 with time = block end in seconds.
- Settle rule (`tools/pitch-gate/settle.mjs`): median, index `len >> 1`, of the nonzero block values at
  `t >= 1.0 s`; `null` when there are none.
- Tau: `energyTau` in `corrAtLagVar` (shipped line 39, `energyTau = 0.01;`). Tau 0.02 is the same one-line
  edit as commit `98ed9068` (`git diff e5572527 98ed9068` is that line only). The coarse tiering in `tauFor`
  is never varied. A tau 0.02 result here is not a claim against the closed row `defect-lowfreq-corr-ripple`.

## Variants

Each variant is an exact string edit of the shipped text, implemented in `variants.py`. A target that does not
occur exactly once aborts the build. Each variant runs at tau 0.01 and tau 0.02. Shipped line numbers are
those of the file as committed at `b563a62a`.

| name | edit | why it is a candidate |
|---|---|---|
| S | none | shipped baseline |
| A1 | L224 `max(minTrackHz)` removed | L8 `minTrackHz = 60.0` in L224 clamps every sub-60 Hz reading to exactly 60.0. A refine clip gives 48000/816 = 58.82 on the 60 Hz fallback, which the clamp turns into 60.0. Removing the lower clamp shows which 60.0 values it creates |
| A2 | L194 `confident` also requires `coarseFreq > minTrackHz` | The 60 Hz grid floor (L90-91, `ba.if(c(60.0) >= corrThresh, 60.0, 60.0)`) is the only way 60 becomes a coarse pick. A fallback coarse pick with a saturated refine (delta clipped at L112-113) lands on exact-lag values: 48000/784 = 61.2245 (seen in the lock table on cymbal) and 48000/250 = 192.0 (violin). The gate makes a fallback pick unconfident. This gate is not in the sweep addendum's confidence-gate axis, which sets g only |
| A3 | L224 `min(maxTrackHz)` removed | L9 `maxTrackHz = 1500.0` bounds the output at 1500.0. The witness table records sine_3000 at exactly 1500.0. Removing the output bound separates that clamp from the grid top (L52-53, candidate 1500.0) |
| B1 | L9 `maxTrackHz` 1500 to 2600, plus promotion margin 0.001 | sine_2093 cannot be reached: the grid tops at 1500 and `maxTrackHz` blocks the 3x promotion (L159-160). The witness ceiling-only variants c2100 and c2200 left the sine at 719.4 Hz, where the 3x candidate is reachable, so the promotion margin (L162, 0.004) is the likely blocker. Estimate from integer-lag correlation, not measured: corr(3x) minus corr(1x) at 2093 Hz is about 0.0013, which is below 0.004 and above 0.001 |
| B2 | as B1 with promotion margin 0.0005 | sensitivity to the margin: the estimated gap is about 0.0013, so 0.0005 leaves room for the ripple the witness notes describe |
| B3 | promotion margin 0.001 only, ceiling 1500 | isolates the margin from the ceiling, so the controls show what the margin alone does |
| C1 | B1 plus A2 | the combination: the ceiling and margin change together with the fallback gate, so one run shows whether the clamp constants and the 2093 row close in the same config |

The promotion margin is a new constant `promoteMargin` used only in the 2x and 3x promotion tests (L162-163).
The demotion test (L146) keeps `subharmDominanceMargin`.

Not repeated. A codesearch of the witness trees finds no `promoteMargin`, no `coarseFreq > minTrackHz`, and no
change to `subharmDominanceMargin` (every witness variant keeps 0.004). Earlier witness variants not rerun
here: ceiling 2100, 2150, 2200, 2600 and 4200, with and without grid extensions; the K-policy variants p1q2, p1q4,
c2150_q2 and lock-sub30 v1 to v3; energy floors 1e-7 and 1e-8 (hv-floor); heldStep without the falling edge (hv-floor);
minTrackHz 50 (a1-dropout, pitch-lowhz-split, pitch-lowhz-period); the sweep addendum's coarse tau, confidence gate
and refine tau axes. Disclosed neighbour: pitch-ceiling moved the output ceiling to 4200 (`maxRawHz`). A3 removes
the output ceiling altogether, so it is near that variant but not the same.

## Targets and controls

- Reference peaks from `docs/witness/corpus-pitch-reference.md`, Reliable table: piano_mid_C4 262.22;
  marimba_low_C2B2 65.21; cello_low_sulC_A2 111.76; trumpet_high_C6 1049.13; soprano_sax_high_C6 1049.13;
  clarinet_high_C6B6 1049.13. Sines use their frequency.
- Phrase files vibraphone_mid_C5B5 and marimba_mid_C5B5 are reported, not scored (the reference marks them as phrases).
- Target table: the six files above plus the six sines (12 files).
- Controls: cello_low_sulC_A2, piano_mid_C4, marimba_low_C2B2, clarinet_high_C6B6, soprano_sax_high_C6, trumpet_high_C6.
- Cents: c = 1200 log2(settled / reference).
- Pitchless set P: silence, white_noise, balloon_pop_transient, cymbal_inharmonic, tamtam_inharmonic.
- Out-of-range report, not scored: piano_low_A1 (55 Hz, below minTrackHz), violin_high_sulE_C7E7 and
  xylophone_run_C7B7 (above maxTrackHz).

## Rules (scored by `tools/sine-clamp/score.py`)

- R1 acceptance (Row B): |c(sine_2093)| <= 50 at tau 0.01 AND at tau 0.02, same run.
- R2 no regression (Row B): for each control and each tau, |c_variant| - |c_S| <= 5. If exactly one of the two
  readings is null, the control counts as a regression. Both null counts as no regression.
- R3 octave (Row B): for each target-table file except sine_2093, the count of |c| > 600 must be 0 at each tau.
  sine_2093's octave state is reported on its own line.
- R4 no-pitch constant (Row A): for each file in P, the settled value must be null or not a lag constant.
  A lag constant is a value v with L = round(48000 / v) an integer in [2, 3200] and |48000 / L - v| < 1e-4.
  60.0 = 48000/800, 192.0 = 48000/250, 1500.0 = 48000/32.
- Row B verdict: a variant passes if R1, R2 and R3 hold at both taus. If none passes, the verdict is "no variant passes".
- Row A verdict: a change "removes the constant" if R4 holds at both taus. It is a candidate fix only if R2 and R3
  also hold at both taus. Lag constants over every file are also listed, unscored, so effects on pitched files show.

## Not tested (declared now)

- Comb certification or whole-series measurement of the phrase files and out-of-range files; the sweep addendum's
  axes are not rerun.
- Truncating `lagFor` (int) in pickFundamental and rounding in `corrRawAt` are not varied.
- Platforms other than Kaggle Linux x64; gains other than 1.0; inputs longer than 8 s.
- No adjustment for the number of variants (8 variants, 2 taus). Each rule is scored as written.
