# Pre-registration: pitch-reference comb / submultiple floor rule and local rerun

Row: `pitch-reference-comb-submultiple-floor-disagree`
(`/config/workspace/mc-420/.gm/prd/pitch-reference-comb-submultiple-floor-disagree.yml`, `status: pending`).
Registered 2026-11-06, BEFORE either tool is run. The sha256 of this file is the
pre-registration sha. Nothing below is added, removed or changed after results are seen.

## 1. Acceptance clause and witness plan (verbatim from the row)

`acceptance_criteria: Both tools use one stated floor definition, and on
vocal_tenor_operatic_PD they give the same verdict for the 100-150 Hz line, or the
difference is recorded in the archive as a stated rule.`

`witness_plan: Rerun comb.mjs --only and submultiple.mjs --wav on
vocal_tenor_operatic_PD in one dispatch and print both 114 Hz verdicts.`

## 2. Stated floor rule (fixed here, before the run)

The archive's stated floor rule for this row is the BAND-MEDIAN MAGNITUDE floor:

- `floorMag` = median of `magAt(hz)` over the swept band `[lo, hi]` Hz, expressed on
  `20*log10(max(1e-12, magnitude))` dB. This is exactly the estimator in
  `tools/pitch-reference/submultiple.mjs`.
- A band peak clears iff `db(m) >= db(refPeakMag) - margin` AND
  `db(m) >= db(floorMag) + margin`, with `margin = 12 dB`, `step = 0.02 Hz`,
  `seconds = 6`. `refPeakMag` is `magAt(--peak)` refined over +-1.0 Hz in 0.05 Hz steps.

`comb.mjs` uses a DIFFERENT estimator, the GLOBAL POWER-MEDIAN floor:

- `floorPow` = median of FFT power bins from `fmin` Hz to 4000 Hz, expressed on
  `10*log10(power)`; `floorGate = floorPow * 10^(margin/10)`; a candidate requires
  `at(f0) >= floorGate`, and certification requires no missing low partials
  (`k <= 4`) plus `f0 > fmin * 1.01`.

The two estimators are different quantities: different band, different transform,
different dB convention. The stated rule recorded for this row is therefore that the
two floors are distinct by construction, that the difference is recorded as the stated
rule, and that no single floor is retrofitted onto either tool by a new threshold
after results. Both tools are run UNMODIFIED; no file under `mc-420` is changed.

This documents the second branch of the acceptance clause ("or the difference is
recorded in the archive as a stated rule"). It does NOT itself close the row and it
does NOT assert that the two tools give the same verdict.

## 3. Fixed commands (one local dispatch; no Kaggle kernel, no gate read)

`cwd = /config/workspace/mc-420`, `node v24.21.0`, input
`test-audio-corpus/instruments/vocal_tenor_operatic_PD.wav` (432044 bytes).

[A]
```
node tools/pitch-reference/comb.mjs --src test-audio-corpus/instruments --only vocal_tenor_operatic_PD
```
Unmodified defaults: `--seconds 6`, `--fmin 60`, `--fmax 1500`, `--grid 0.005`,
`--partials 8`, `--within 3`, `--margin 12`, `fftSize 524288`, band ceiling 4000 Hz,
phrase exclusion by `_(run|scale|range|melody|trill)(_|\.)`.

[B]
```
node tools/pitch-reference/submultiple.mjs --wav test-audio-corpus/instruments/vocal_tenor_operatic_PD.wav --peak 461.06 --lo 100 --hi 150 --margin 12 --step 0.02 --seconds 6
```
`--peak 461.06` Hz is the archived comb peak for this file
(`mc-420/docs/measurements-archive.md`, "Unpinned pin-hit readings vs reference
tools": "comb peak 461.06 Hz, combF0 114.18 Hz, certified"). It is FIXED here and is
NOT re-derived from the fresh comb output after results. The band `[100, 150]` Hz is
the row's 100-150 Hz line; the archived `/4 = 115.27 Hz` is `461.06 / 4`.

## 4. Reporting rule (fixed)

Both tools' complete stdout is reported verbatim, in order, with no elision, no
rounding and no paraphrase. The "114 Hz verdicts" are quoted verbatim as [A]'s row
(columns `file peakHz combF0 belowBestDb missingP centsVsPeak f0vsFloorDb missing
verdict`) and [B]'s `clearing candidates in band: N` line and final `verdict: ...`
line. Exit codes and any stderr are reported verbatim. If a command fails, the failure
is reported verbatim and no substitution is made. No causal claim, verdict on the row,
or interpretation is added to the quoted output.

## 5. Fixed out-of-scope

- No threshold, margin, band, floor rule, gain, input or argument is added or changed
  after results; the floor rule above stays exactly as registered at this sha.
- No verdict on the row, no row close, no `status` change. The row stays `pending`
  until the gm route exists.
- No edit to `comb.mjs`, `submultiple.mjs`, the PRD row, the measurements archive, or
  any file under `/config/workspace/mc-420`.
- No Kaggle kernel, no gate read, no new diagnosis round. The k11-to-round-3
  diagnosis chain is closed and stays closed.
- No reinterpretation of the acceptance clause, no inputs re-cut, no normalisation.
- Attribution: `lanmower` only, no Co-Authored-By.
