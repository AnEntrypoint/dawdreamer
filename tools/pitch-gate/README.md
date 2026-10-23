# pitch-gate settle rule

One rule, used for every tracker value the gate reports:

> the median of the **nonzero** block-end Hz values at **t >= 1.0 s**

Blocks that read exactly `0` are excluded. A silent or unconfident
block is not a pitch reading, and including it drags the median to 0.
When a render has no nonzero block at or after 1.0 s, the settled value
is reported as `null`, never as `0`.

## Why this window

Two windows were in use and disagreed. On the crotale baseline, settling
on the second half (`t >= T/2`) gave 170.2 Hz and settling on `t >= 1.0 s`
gave 708.6 Hz, from the same pinned driver output, so the difference was
the window and not the tracker. `t >= 1.0 s` is chosen because it is the
same for every file regardless of length, so a 3 s and a 10 s render are
settled alike, and because it matches the window the mc-420 corpus
comparisons already use.

## Use

```
node tools/pitch-gate/settle.mjs <trace.txt> [<trace.txt> ...]
```

Traces are `time Hz` per block, one block per line, as written by the
DawDreamer libfaust render harness at 4800 samples per block.

## Measured under this rule

Shipped baseline tracker `3f0184ab36e8bb243fdaa9a325736175b1a64f54dbd93719baa658af2cb6bef3`,
corpus gain `0.00707945784384138`, 4800-sample blocks:

| file | settled blocks | nonzero | settle Hz | audio sha256 |
| --- | --- | --- | --- | --- |
| crotale_high_C7 | 36 | 0 | null | `d3d812fb8cadfdde3c75fea6bfdfc98146cf951105d186717c202968d514f2f7` |
| marimba_mid_C5B5 | 91 | 1 | 560.7418 | `4a326e7e6da89312fa34e2efd81e172574a3b4e32ecafbb1accc52352cf1f563` |

Crotale publishes no nonzero block at this gain, so its settled value is
`null` and the window question does not arise for it here.
