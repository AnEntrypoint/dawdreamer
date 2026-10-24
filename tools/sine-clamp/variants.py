import hashlib
import os
import sys

RAW_CLAMP = "rawFreq = rawFreqUnclamped : max(minTrackHz) : min(maxTrackHz);"
CEILING = [("maxTrackHz = 1500.0;", "maxTrackHz = 2600.0;")]
FALLBACK_GATE = [
    (
        "confident = finalConfidence >= corrThresh;",
        "confident = (finalConfidence >= corrThresh) & (coarseFreq > minTrackHz);",
    )
]
TAU_EDIT = [("energyTau = 0.01;", "energyTau = 0.02;")]
MARGIN_DECL = "subharmDominanceMargin = 0.004;"


def promote_margin(value):
    return [
        (MARGIN_DECL, MARGIN_DECL + "\npromoteMargin = %s;" % value),
        ("raw3 > pBase + subharmDominanceMargin", "raw3 > pBase + promoteMargin"),
        ("raw2 > pBase + subharmDominanceMargin", "raw2 > pBase + promoteMargin"),
    ]


EDITS = {
    "S": [],
    "A1": [(RAW_CLAMP, "rawFreq = rawFreqUnclamped : min(maxTrackHz);")],
    "A2": FALLBACK_GATE,
    "A3": [(RAW_CLAMP, "rawFreq = rawFreqUnclamped : max(minTrackHz);")],
    "B1": CEILING + promote_margin("0.001"),
    "B2": CEILING + promote_margin("0.0005"),
    "B3": promote_margin("0.001"),
    "C1": CEILING + promote_margin("0.001") + FALLBACK_GATE,
}
NAMES = ["S", "A1", "A2", "A3", "B1", "B2", "B3", "C1"]
TAUS = ["0.01", "0.02"]


def apply(text, edits):
    for old, new in edits:
        count = text.count(old)
        if count != 1:
            raise ValueError("edit target occurs %d times: %s" % (count, old))
        text = text.replace(old, new)
    return text


def build(shipped, name, tau):
    text = apply(shipped, EDITS[name])
    if tau == "0.02":
        text = apply(text, TAU_EDIT)
    elif tau != "0.01":
        raise ValueError("tau must be 0.01 or 0.02, got %s" % tau)
    return text


def key(name, tau):
    return "%s_%s" % (name, tau)


def main(shipped_path, outdir):
    with open(shipped_path) as f:
        shipped = f.read()
    os.makedirs(outdir, exist_ok=True)
    for name in NAMES:
        for tau in TAUS:
            text = build(shipped, name, tau)
            with open(os.path.join(outdir, key(name, tau) + ".dsp"), "w") as f:
                f.write(text)
            print("%s %s" % (hashlib.sha256(text.encode()).hexdigest(), key(name, tau)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
