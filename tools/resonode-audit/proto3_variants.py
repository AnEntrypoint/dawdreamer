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

RESULTS = "/kaggle/working/results-proto3.txt"
OUT = ra.W + "/proto3"
ORDER = ["base", "e1", "e2"]
KEYS = list(range(36, 97))
QA_KEYS = [38, 44, 48, 60, 64]

ENV_DEFS = (
    "exciteEnvAttackPole = ba.tau2pole(0.01);\n"
    "exciteEnvReleasePole = ba.tau2pole(0.1);\n"
    "exciteEnvFloor = 0.1;\n"
    "exciteEnvFollow(x) = e\n"
    "letrec {\n"
    "    'e = ba.if(abs(x) > e, exciteEnvAttackPole*e + (1.0 - exciteEnvAttackPole)*abs(x), exciteEnvReleasePole*e + (1.0 - exciteEnvReleasePole)*abs(x));\n"
    "};\n"
    "exciteEnvGain(x) = 1.0 - inputAmt*(1.0 - exciteEnvFloor)*(1.0 - min(1.0, exciteEnvFollow(x)));\n"
)
PEAK_DEFS = (
    "exciteEnvPeakPole = ba.tau2pole(0.5);\n"
    "envPeak(e) = p\n"
    "letrec {\n"
    "    'p = ba.if(e > p, e, exciteEnvPeakPole*p + (1.0 - exciteEnvPeakPole)*e);\n"
    "};\n"
    "exciteEnvRatioFloor = 0.05;\n"
    "dampShortenMax = 3.0;\n"
)
EXCITE_OLD = "exciteBus(exciteIn) = sharedExciteIn(exciteIn)*inputAmt + internalExciter*(1.0 - inputAmt);"
EXCITE_NEW = "exciteBus(exciteIn) = (sharedExciteIn(exciteIn)*inputAmt + internalExciter*(1.0 - inputAmt))*exciteEnvGain(exciteIn);"
VOICE_OLD = "voice(busIn, note, gate, vel) = collisionDrive((bankOut + objOut*body)*drivePreGain) * invDrivePreGain * voiceGain * voiceBassTilt(fundHz)"
VOICE_NEW = "voice(busIn, liveIn, note, gate, vel) = collisionDrive((bankOut + objOut*body)*drivePreGain) * invDrivePreGain * voiceGain * voiceBassTilt(fundHz)"
BANK_OLD = "    bankOut = (exc, fundHz, ratioExponent, positionLive) : modeBank(modeCount);"
BANK_NEW = (
    "    envNow = exciteEnvFollow(liveIn);\n"
    "    envRatio = (envNow + exciteEnvRatioFloor)/(envPeak(envNow) + exciteEnvRatioFloor);\n"
    "    dampShorten = 1.0 + inputAmt*dampShortenMax*(1.0 - min(1.0, envRatio));\n"
    "    bankOut = (exc, fundHz, ratioExponent, positionLive, dampShorten) : modeBank(modeCount);"
)
STAGE_OLD = "modeStage(i, coupledIn, exc, freqFund, ratioExponent, positionLive) = normalisedOut, weightedOut"
STAGE_NEW = "modeStage(i, coupledIn, exc, freqFund, ratioExponent, positionLive, dampShorten) = normalisedOut, weightedOut"
POLE_OLD = "    poleRadius = modePole(freqFund, modeDecayScale(i)*exp(highFreqDampExponent*modeLogRatioLive));"
POLE_NEW = "    poleRadius = modePole(freqFund*dampShorten, modeDecayScale(i)*exp(highFreqDampExponent*modeLogRatioLive));"
ROUTE_OLD = (
    "modeBankStep(n) = route(n+4, n*5,\n"
    "        par(i, n, (i+1, i*5+1)),\n"
    "        par(i, n, (n+1, i*5+2)),\n"
    "        par(i, n, (n+2, i*5+3)),\n"
    "        par(i, n, (n+3, i*5+4)),\n"
    "        par(i, n, (n+4, i*5+5)))"
)
ROUTE_NEW = (
    "modeBankStep(n) = route(n+5, n*6,\n"
    "        par(i, n, (i+1, i*6+1)),\n"
    "        par(i, n, (n+1, i*6+2)),\n"
    "        par(i, n, (n+2, i*6+3)),\n"
    "        par(i, n, (n+3, i*6+4)),\n"
    "        par(i, n, (n+4, i*6+5)),\n"
    "        par(i, n, (n+5, i*6+6)))"
)
PROC_OLD = "    (voice(bus,note0,gate0,vel0) + voice(bus,note1,gate1,vel1) + voice(bus,note2,gate2,vel2) + voice(bus,note3,gate3,vel3))"
PROC_NEW = "    (voice(bus,exciteIn,note0,gate0,vel0) + voice(bus,exciteIn,note1,gate1,vel1) + voice(bus,exciteIn,note2,gate2,vel2) + voice(bus,exciteIn,note3,gate3,vel3))"

EDITS = {
    "e1": [(EXCITE_OLD, ENV_DEFS + EXCITE_NEW)],
    "e2": [
        (EXCITE_OLD, ENV_DEFS + PEAK_DEFS + EXCITE_NEW),
        (VOICE_OLD, VOICE_NEW),
        (BANK_OLD, BANK_NEW),
        (STAGE_OLD, STAGE_NEW),
        (POLE_OLD, POLE_NEW),
        (ROUTE_OLD, ROUTE_NEW),
        (PROC_OLD, PROC_NEW),
    ],
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


def jobs_for(tag, vlen):
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
    return jobs


def cents_of(x, n):
    f0 = 440.0 * 2.0 ** ((n - 69) / 12.0)
    return 1200.0 * math.log2(ra.settled_peak(x) / f0)


def measure(tag, d, vlen):
    m = {"keys": {}, "cents": {}, "m1": [], "peak": []}
    for n in KEYS:
        name = "%s_k_%d" % (tag, n)
        m["keys"][n] = ra.sha256(os.path.join(d, name + ".f32"))
        m["cents"][n] = cents_of(ra.fo(name, d), n)
    m["r1"] = [ra.rt60(ra.fo("%s_r1_%d" % (tag, i), d), ra.IMP_AT) for i in range(len(ra.DECAYS))]
    for vi, v in enumerate(ra.VOCALS):
        L = ra.PRE + vlen[v]
        x_in = np.concatenate([np.zeros(ra.PRE), ra.read_wav(ra.NORM + "/" + v + ".wav")])
        out = ra.fo("%s_m_%d" % (tag, vi), d)
        m["m1"].append(ra.pearson(ra.env_rms(x_in, 960)[ra.PRE:L], ra.env_rms(out, 960)[ra.PRE:L]))
        m["peak"].append(float(np.max(np.abs(out))))
    Lf = ra.PRE + vlen[ra.VOCALS[0]]
    Lm = ra.PRE + vlen[ra.VOCALS[1]]
    o_f = ra.fo("%s_m_0" % tag, d)[ra.PRE:Lf]
    o_m = ra.fo("%s_m_1" % tag, d)[ra.PRE:Lm]
    o_k = ra.fo("%s_m4k" % tag, d)[ra.PRE:Lf]
    m["m4"] = (ra.ltas_dist(o_f, o_m), ra.ltas_dist(o_f, o_k))
    return m


def verdicts(add, res):
    b = res.get("base")
    if b is None:
        add("FAIL no baseline measurement")
        return
    add("REPRO cents " + " ".join("%d:%s" % (n, "match" if abs(round(b["cents"][n], 1) - dg.V2_P3_CENTS[n]) < 0.06 else "differs") for n in QA_KEYS))
    add("CRIT base m1_median_r=%.4f" % float(np.median(b["m1"])))
    for name in ORDER:
        v = res.get(name)
        if v is None:
            add("SUM %s not measured" % name)
            continue
        rel = 20.0 * math.log10(v["peak"][0] / max(1e-30, b["peak"][0]))
        add("SUM %s m1_median_r=%.4f m1_r=%s" % (name, float(np.median(v["m1"])), fmt(v["m1"], 4)))
        add("SUM %s m4_ltas_fm_db=%.3f m4_ltas_fk_db=%.3f" % (name, v["m4"][0], v["m4"][1]))
        add("SUM %s rt60=%s" % (name, fmt(v["r1"], 4)))
        add("SUM %s keys_bit_identical_to_base=%d/%d peak_m0_vs_base_db=%.2f" % (
            name,
            sum(1 for n in KEYS if v["keys"][n] == b["keys"][n]),
            len(KEYS),
            rel,
        ))
        add("SUM %s qa_cents=%s" % (name, " ".join("%d:%.2f" % (n, v["cents"][n]) for n in QA_KEYS)))
    for name in ORDER[1:]:
        v = res.get(name)
        if v is None:
            add("CRIT %s not measured" % name.upper())
            continue
        m1 = float(np.median(v["m1"]))
        m4a, m4b = v["m4"]
        ident = sum(1 for n in KEYS if v["keys"][n] == b["keys"][n])
        ok = m1 >= 0.8 and m4a >= 1.0 and m4b >= 1.0 and ident == len(KEYS)
        extra = ""
        final = ok
        if name == "e2":
            r1_ok = v["r1"][0] <= 0.2 and v["r1"][5] >= 6.0
            extra = " r1_rt60_005=%.4f r1_rt60_800=%.4f r1_ok=%s" % (v["r1"][0], v["r1"][5], str(r1_ok))
            final = ok and r1_ok
        add("CRIT %s m1_median_r=%.4f m4_fm_db=%.3f m4_fk_db=%.3f keys_bit_identical=%d/%d%s threshold=M1>=0.8,M4 both>=1,bit-identical all%s verdict=%s" % (
            name.upper(),
            m1,
            m4a,
            m4b,
            ident,
            len(KEYS),
            extra,
            ",R1 0.2 to 6 s" if name == "e2" else "",
            "PASS" if final else "FAIL",
        ))


def run(add):
    add("META resonode-proto3 faust=%s shipped_dsp_sha256=%s" % (ra.FAUST, ra.DSP_SHA))
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
        try:
            ra.compile_dsp(arch, add)
            ra.build_driver(arch, add)
            jobs = jobs_for(name, vlen)
            jobfile = ra.W + "/%s.txt" % name
            ra.write_jobs(jobfile, jobs)
            add("META jobs variant=%s count=%d" % (name, len(jobs)))
            outdir = OUT + "/" + name
            ra.run_jobs(jobfile, outdir, add, name)
            res[name] = measure(name, outdir, vlen)
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
