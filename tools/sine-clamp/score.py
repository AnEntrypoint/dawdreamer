import math
import sys

REF = {
    "piano_mid_C4": 262.22,
    "marimba_low_C2B2": 65.21,
    "cello_low_sulC_A2": 111.76,
    "trumpet_high_C6": 1049.13,
    "soprano_sax_high_C6": 1049.13,
    "clarinet_high_C6B6": 1049.13,
    "sine_65.55": 65.55,
    "sine_69.75": 69.75,
    "sine_110": 110.0,
    "sine_440": 440.0,
    "sine_1000": 1000.0,
    "sine_2093": 2093.0,
}
CONTROLS = [
    "cello_low_sulC_A2",
    "piano_mid_C4",
    "marimba_low_C2B2",
    "clarinet_high_C6B6",
    "soprano_sax_high_C6",
    "trumpet_high_C6",
]
ROW_B = "sine_2093"
PITCHLESS = ["silence", "white_noise", "balloon_pop_transient", "cymbal_inharmonic", "tamtam_inharmonic"]
NAMES = ["S", "A1", "A2", "A3", "B1", "B2", "B3", "C1"]
TAUS = ["0.01", "0.02"]
SR = 48000.0
ACC_CENTS = 50.0
REG_CENTS = 5.0
OCT_CENTS = 600.0
LAG_TOL = 1e-4


def cents(value, name):
    if value is None:
        return None
    return 1200.0 * math.log2(value / REF[name])


def lag_constant(value):
    if value is None or value <= 0:
        return None
    lag = int(round(SR / value))
    if 2 <= lag <= 3200 and abs(SR / lag - value) < LAG_TOL:
        return lag
    return None


def parse(path):
    rows = {}
    with open(path) as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if p[0] != "ROW" or len(p) < 9:
                continue
            value = None if p[7] == "null" else float(p[7])
            rows[(p[1], p[2], p[3])] = value
    return rows


def run_status(path):
    status = {}
    with open(path) as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if p[0] == "RUN" and len(p) >= 6:
                status[(p[1], p[2])] = (p[4], p[5])
    return status


def score_variant(rows, name, tau):
    s = {}
    value = rows.get((name, tau, ROW_B))
    c = cents(value, ROW_B)
    s["row_b_settle"] = value
    s["row_b_cents"] = c
    s["r1"] = c is not None and abs(c) <= ACC_CENTS
    worst = None
    regress = []
    for k in CONTROLS:
        base = cents(rows.get(("S", tau, k)), k)
        var = cents(rows.get((name, tau, k)), k)
        if base is None and var is None:
            continue
        if base is None or var is None:
            regress.append(k + ":null")
            continue
        delta = abs(var) - abs(base)
        if worst is None or delta > worst[1]:
            worst = (k, delta)
        if delta > REG_CENTS:
            regress.append("%s:%+.1f" % (k, delta))
    s["r2"] = not regress
    s["r2_worst"] = worst
    s["r2_fail"] = regress
    octave = []
    for k in REF:
        if k == ROW_B:
            continue
        ck = cents(rows.get((name, tau, k)), k)
        if ck is not None and abs(ck) > OCT_CENTS:
            octave.append("%s:%+.0f" % (k, ck))
    s["r3"] = not octave
    s["r3_fail"] = octave
    pit = []
    for k in PITCHLESS:
        v = rows.get((name, tau, k))
        if lag_constant(v) is not None:
            pit.append("%s=%s" % (k, v))
    s["r4"] = not pit
    s["r4_fail"] = pit
    consts = []
    for (v_name, v_tau, f), v in rows.items():
        if v_name == name and v_tau == tau and lag_constant(v) is not None:
            consts.append("%s=%s" % (f, v))
    s["lag_constants_all"] = sorted(consts)
    return s


def main(path):
    rows = parse(path)
    status = run_status(path)
    print("variant\ttau\trun_rc\tsecs\tsine2093_Hz\tsine2093_c\tR1\tR2\tR2_worst\tR3_octave\tR4_pitchless\tlag_constants(all files)")
    summary = {}
    for name in NAMES:
        for tau in TAUS:
            s = score_variant(rows, name, tau)
            rc, secs = status.get((name, tau), ("missing", "-"))
            worst = "-" if s["r2_worst"] is None else "%s:%+.1f" % s["r2_worst"]
            print("\t".join([
                name,
                tau,
                str(rc),
                str(secs),
                "null" if s["row_b_settle"] is None else "%.4f" % s["row_b_settle"],
                "null" if s["row_b_cents"] is None else "%+.1f" % s["row_b_cents"],
                "pass" if s["r1"] else "fail",
                "pass" if s["r2"] else "fail " + ",".join(s["r2_fail"]),
                worst,
                "pass" if s["r3"] else "fail " + ",".join(s["r3_fail"]),
                "pass" if s["r4"] else "fail " + ",".join(s["r4_fail"]),
                ";".join(s["lag_constants_all"]) or "none",
            ]))
            summary[(name, tau)] = s
    print("")
    for name in NAMES:
        ok = all(summary[(name, t)]["r1"] and summary[(name, t)]["r2"] and summary[(name, t)]["r3"] for t in TAUS)
        pitch = all(summary[(name, t)]["r4"] for t in TAUS)
        print("%s row_B_pass=%s row_A_R4_pass=%s" % (name, ok, pitch))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
