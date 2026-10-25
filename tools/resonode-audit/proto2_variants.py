import hashlib
import math
import os
import shutil
import sys
import traceback

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import diag_resonode as dg
import resonode_audit as ra

RESULTS = "/kaggle/working/results-proto2.txt"
OUT = ra.W + "/proto2"
ORDER = ["base", "r2a", "r2b", "r2c"]
KEYS = list(range(36, 97))
QA_KEYS = [38, 44, 48, 60, 64]
P2_TAGS = ("base", "r2a", "r2b")
SMOOTH = dg.smoothing(1025)

STRETCH_OLD = "    ratioExponent = 1.0 + stretch + stretchJitterAmt*noteJitter(note, gate);"
STRETCH_NEW = "    ratioExponent = 1.0 + 0.15*stretch + stretchJitterAmt*noteJitter(note, gate);"
DECAY_OLD = 'decayTime = hslider("fx/resonode/decay", 1.2, 0.05, 8.0, 0.001) : morphGlide;'
DECAY_NEW = 'decayTime = hslider("fx/resonode/decay", 0.4, 0.05, 8.0, 0.001) : morphGlide;'
LIVE_ENV_DEFS = (
    "liveEnvAttackPole = ba.tau2pole(0.01);\n"
    "liveEnvReleasePole = ba.tau2pole(0.3);\n"
    "liveEnvFollow(x) = e\n"
    "letrec {\n"
    "    'e = ba.if(abs(x) > e, liveEnvAttackPole*e + (1.0 - liveEnvAttackPole)*abs(x), liveEnvReleasePole*e + (1.0 - liveEnvReleasePole)*abs(x));\n"
    "};\n"
    "liveEnvGain(x) = 1.0 - inputAmt*(1.0 - min(1.0, liveEnvFollow(x)));\n"
)
OUT_OLD = "    : *(outLevel*decayLoudnessNorm) : ma.tanh"
OUT_NEW = OUT_OLD + "\n    : *(0.5 + 0.5*liveEnvGain(exciteIn))"
PROCESS_OLD = "process(exciteIn) ="

EDITS = {
    "r2a": [(STRETCH_OLD, STRETCH_NEW)],
    "r2b": [(STRETCH_OLD, STRETCH_NEW), (DECAY_OLD, DECAY_NEW)],
    "r2c": [(PROCESS_OLD, LIVE_ENV_DEFS + PROCESS_OLD), (OUT_OLD, OUT_NEW)],
}


def fmt(xs, p=2):
    return " ".join("%.*f" % (p, x) for x in xs)


def variant_texts(shipped):
    texts = {"base": shipped}
    for name in ORDER[1:]:
        text = shipped
        for old, new in EDITS[name]:
            hits = text.count(old)
            if hits != 1:
                raise SystemExit("anchor hits %d in %s" % (hits, name))
            text = text.replace(old, new)
        texts[name] = text
    return texts


def jobs_for(tag, vlen, p2):
    vocal = {v: ra.NORM + "/" + v + ".wav" for v in ra.VOCALS}
    female = ra.VOCALS[0]
    Lf = ra.PRE + vlen[female]
    jobs = []
    for n in KEYS:
        jobs.append(ra.job("%s_k_%d" % (tag, n), 1.2 * ra.SR, ra.K_IN + ra.key(n, 1)))
    for i, d in enumerate(ra.DECAYS):
        jobs.append(ra.job("%s_r1_%d" % (tag, i), ra.IMP_LEN, ra.M_IN + ra.key(60, 1) + [("fx/resonode/decay", d)], inp=ra.W + "/impulse.wav"))
    for vi, v in enumerate(ra.VOCALS):
        jobs.append(ra.job("%s_m_%d" % (tag, vi), ra.PRE + vlen[v] + ra.TAIL, ra.M_IN + ra.key(60, 1), inp=vocal[v], pre=ra.PRE))
    jobs.append(ra.job("%s_m4k" % tag, Lf + ra.TAIL, ra.K_IN + ra.key(60, 1)))
    if p2:
        for dn, lo, hi, path, mode in ra.DIALS:
            inp = vocal[female] if mode == "M" else "-"
            base = (ra.M_IN if mode == "M" else ra.K_IN) + ra.key(60, 1)
            for i, fr in enumerate(ra.FRACS):
                b = lo + fr * (hi - lo)
                s = b + 0.01 * (hi - lo)
                jobs.append(ra.job("%s_p2_%s_%d_a" % (tag, dn, i), 2.0 * ra.SR, base + [(path, b)], inp=inp))
                jobs.append(ra.job("%s_p2_%s_%d_b" % (tag, dn, i), 2.0 * ra.SR, base + [(path, s)], inp=inp))
    return jobs


def partial_db(x, n):
    seg = x[int(0.3 * ra.SR):int(1.2 * ra.SR)]
    seg = seg * np.hanning(len(seg))
    N = 1 << 18
    mag2 = np.abs(np.fft.rfft(seg, n=N)) ** 2
    freqs = np.fft.rfftfreq(N, 1.0 / ra.SR)
    f0 = 440.0 * 2.0 ** ((n - 69) / 12.0)
    vals = []
    for k in range(1, 7):
        band = np.where((freqs >= 0.94 * k * f0) & (freqs <= 1.06 * k * f0))[0]
        vals.append(10.0 * math.log10(float(mag2[band].max()) + 1e-30))
    return np.array(vals)


def cents_of(x, n):
    f0 = 440.0 * 2.0 ** ((n - 69) / 12.0)
    return 1200.0 * math.log2(ra.settled_peak(x) / f0)


def measure(tag, d, vlen, p2):
    m = {"keys": {}, "cents": {}, "qa_db": {}}
    for n in KEYS:
        name = "%s_k_%d" % (tag, n)
        m["keys"][n] = ra.sha256(os.path.join(d, name + ".f32"))
        x = ra.fo(name, d)
        m["cents"][n] = cents_of(x, n)
        if n in QA_KEYS:
            m["qa_db"][n] = partial_db(x, n)
    m["r1"] = [ra.rt60(ra.fo("%s_r1_%d" % (tag, i), d), ra.IMP_AT) for i in range(len(ra.DECAYS))]
    m["m1"] = []
    for vi, v in enumerate(ra.VOCALS):
        L = ra.PRE + vlen[v]
        x_in = np.concatenate([np.zeros(ra.PRE), ra.read_wav(ra.NORM + "/" + v + ".wav")])
        out = ra.fo("%s_m_%d" % (tag, vi), d)
        m["m1"].append(ra.pearson(ra.env_rms(x_in, 960)[ra.PRE:L], ra.env_rms(out, 960)[ra.PRE:L]))
    Lf = ra.PRE + vlen[ra.VOCALS[0]]
    Lm = ra.PRE + vlen[ra.VOCALS[1]]
    o_f = ra.fo("%s_m_0" % tag, d)[ra.PRE:Lf]
    o_m = ra.fo("%s_m_1" % tag, d)[ra.PRE:Lm]
    o_k = ra.fo("%s_m4k" % tag, d)[ra.PRE:Lf]
    m["m4"] = (ra.ltas_dist(o_f, o_m), ra.ltas_dist(o_f, o_k))
    if p2:
        m["p2"] = {}
        for dn, lo, hi, path, mode in ra.DIALS:
            bins, smooths = [], []
            for i in range(len(ra.FRACS)):
                a = ra.fo("%s_p2_%s_%d_a" % (tag, dn, i), d)
                b = ra.fo("%s_p2_%s_%d_b" % (tag, dn, i), d)
                bins.append(ra.lsd(a, b))
                smooths.append(dg.smoothed_lsd(a, b, SMOOTH))
            m["p2"][dn] = {"bin": bins, "smooth": smooths}
    return m


def verdicts(add, res):
    b = res.get("base")
    if b is None:
        add("FAIL no baseline measurement")
        return
    for n in QA_KEYS:
        add("QA base key=%d cents=%.2f p_db=%s" % (n, b["cents"][n], fmt(b["qa_db"][n])))
    add("REPRO cents " + " ".join("%d:%s" % (n, "match" if abs(round(b["cents"][n], 1) - dg.V2_P3_CENTS[n]) < 0.06 else "differs") for n in QA_KEYS))
    for dn in ("position", "stretch"):
        bins = b["p2"][dn]["bin"]
        mb, xb = float(np.median(bins)), float(max(bins))
        v2m, v2x = dg.V2_P2[dn]
        ok = abs(mb - v2m) < 0.0002 and abs(xb - v2x) < 0.0002
        add("REPRO p2 %s bin_median=%.4f bin_max=%.4f v2=%s verdict=%s" % (dn, mb, xb, dg.V2_P2[dn], "match" if ok else "differs"))
    for name in ORDER:
        v = res.get(name)
        if v is None:
            add("SUM %s not measured" % name)
            continue
        add("SUM %s m1_median_r=%.4f m1_r=%s rt60=%s" % (name, float(np.median(v["m1"])), fmt(v["m1"], 4), fmt(v["r1"], 4)))
        add("SUM %s m4_ltas_fm_db=%.3f m4_ltas_fk_db=%.3f" % (name, v["m4"][0], v["m4"][1]))
        add("SUM %s qa_cents=%s" % (name, " ".join("%d:%.2f" % (n, v["cents"][n]) for n in QA_KEYS)))
        add("SUM %s keys_bit_identical_to_base=%d/%d" % (name, sum(1 for n in KEYS if v["keys"][n] == b["keys"][n]), len(KEYS)))
    for name in P2_TAGS:
        v = res.get(name)
        if v is None:
            continue
        for dn, _, _, _, _ in ra.DIALS:
            bins = v["p2"][dn]["bin"]
            smooths = v["p2"][dn]["smooth"]
            add("P2 %s dial=%s bin_median=%.4f bin_max=%.4f smooth_median=%.4f smooth_max=%.4f" % (name, dn, float(np.median(bins)), float(max(bins)), float(np.median(smooths)), float(max(smooths))))
    base_r1 = b["r1"]
    base_m1 = float(np.median(b["m1"]))
    add("CRIT base m1_median_r=%.4f" % base_m1)

    v = res.get("r2a")
    if v is None:
        add("CRIT R2a not measured")
    else:
        s_med = float(np.median(v["p2"]["stretch"]["smooth"]))
        devs = {}
        for dn, _, _, _, _ in ra.DIALS:
            if dn == "stretch":
                continue
            bm = float(np.median(b["p2"][dn]["bin"]))
            bx = float(max(b["p2"][dn]["bin"]))
            vm = float(np.median(v["p2"][dn]["bin"]))
            vx = float(max(v["p2"][dn]["bin"]))
            devs[dn] = max(abs(vm - bm), abs(vx - bx))
        ok = s_med <= 1.5 and all(x <= 0.5 for x in devs.values())
        add("CRIT R2a stretch_smooth_median_db=%.4f base_stretch_smooth_median_db=%.4f other_dial_max_dev_db=%s threshold=stretch<=1.5,others<=0.5 verdict=%s" % (
            s_med,
            float(np.median(b["p2"]["stretch"]["smooth"])),
            " ".join("%s:%.4f" % (dn, devs[dn]) for dn in devs),
            "PASS" if ok else "FAIL",
        ))

    v = res.get("r2b")
    if v is None:
        add("CRIT R2b not measured")
    else:
        s_med = float(np.median(v["p2"]["stretch"]["smooth"]))
        m1 = float(np.median(v["m1"]))
        rt_ok = all(abs(v["r1"][i] - base_r1[i]) <= 0.01 * abs(base_r1[i]) for i in range(len(base_r1)))
        ok = s_med <= 1.5 and m1 >= 0.8 and rt_ok
        add("CRIT R2b stretch_smooth_median_db=%.4f m1_median_r=%.4f rt60_unchanged=%s rt60=%s audit_r1_rt60_005=%.4f audit_r1_rt60_8=%.4f threshold=stretch<=1.5,M1>=0.8,RT60 within 1pct verdict=%s" % (
            s_med,
            m1,
            str(rt_ok),
            fmt(v["r1"], 4),
            v["r1"][0],
            v["r1"][5],
            "PASS" if ok else "FAIL",
        ))

    v = res.get("r2c")
    if v is None:
        add("CRIT R2c not measured")
    else:
        m1 = float(np.median(v["m1"]))
        m4a, m4b = v["m4"]
        ident = sum(1 for n in KEYS if v["keys"][n] == b["keys"][n])
        ok = m1 >= 0.8 and m4a >= 1.0 and m4b >= 1.0 and ident == len(KEYS)
        add("CRIT R2c m1_median_r=%.4f m4_ltas_fm_db=%.3f m4_ltas_fk_db=%.3f keys_bit_identical=%d/%d threshold=M1>=0.8,M4 both>=1,bit-identical all keys verdict=%s" % (
            m1,
            m4a,
            m4b,
            ident,
            len(KEYS),
            "PASS" if ok else "FAIL",
        ))


def run(add):
    add("META resonode-proto2 faust=%s shipped_dsp_sha256=%s" % (ra.FAUST, ra.DSP_SHA))
    shipped_path = ra.W + "/resonode_synth.dsp"
    if ra.sha256(shipped_path) != ra.DSP_SHA:
        raise SystemExit("shipped dsp sha mismatch")
    if ra.sha256(ra.W + "/normalise-corpus.mjs") != ra.NORM_SHA:
        raise SystemExit("normaliser sha mismatch")
    with open(shipped_path, encoding="utf-8") as f:
        shipped = f.read()
    texts = variant_texts(shipped)
    for name in ORDER:
        data = texts[name].encode("utf-8")
        add("META variant=%s dsp_text_sha256=%s bytes=%d" % (name, hashlib.sha256(data).hexdigest(), len(data)))
    ra.verify_corpus(add)
    node = ra.ensure_node()
    ra.normalise(node, add)
    vlen = {v: len(ra.read_wav(ra.NORM + "/" + v + ".wav")) for v in ra.VOCALS}
    arch, recipe = ra.build_toolchain(add)
    add("META faust_cli_recipe %s" % recipe)
    ra.write_impulse(ra.W + "/impulse.wav")
    res = {}
    for name in ORDER:
        with open(ra.W + "/resonode_synth.dsp", "w", encoding="utf-8") as f:
            f.write(texts[name])
        p2 = name in P2_TAGS
        try:
            ra.compile_dsp(arch, add)
            ra.build_driver(arch, add)
            jobs = jobs_for(name, vlen, p2)
            jobfile = ra.W + "/%s.txt" % name
            ra.write_jobs(jobfile, jobs)
            add("META jobs variant=%s count=%d" % (name, len(jobs)))
            outdir = OUT + "/" + name
            ra.run_jobs(jobfile, outdir, add, name)
            res[name] = measure(name, outdir, vlen, p2)
        except SystemExit as ex:
            add("FAIL variant=%s %s" % (name, ex))
    verdicts(add, res)


def main():
    R = []

    def add(line):
        R.append(line)
        print(line, flush=True)

    try:
        run(add)
    except BaseException as ex:
        add("FAILED %s" % ex)
        add(traceback.format_exc()[-1500:])
    finally:
        os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
        with open(RESULTS, "w") as f:
            f.write("\n".join(R) + "\n")
        shutil.rmtree(ra.W, ignore_errors=True)


if __name__ == "__main__":
    main()
