import os
import shutil
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import resonode_audit as ra

RESULTS = "/kaggle/working/results-diag.txt"
OUT = ra.W + "/diag"
KEYS_A = [38, 44, 48, 60, 64]
CONTROLS = (48, 60)
V2_P3_CENTS = {38: 1204.1, 44: 1194.6, 48: -10.8, 60: -0.5, 64: 1200.7}
V2_P2 = {"position": (3.2458, 4.3984), "stretch": (10.2723, 13.5870)}
QB = [("position", 0.0, 1.0, "fx/resonode/position"), ("stretch", -0.5, 1.5, "fx/resonode/stretch")]
BAND = 2.0 ** (1.0 / 6.0)


def jobs_for():
    jobs = []
    for n in KEYS_A:
        jobs.append(ra.job("qa_%d" % n, 1.2 * ra.SR, ra.K_IN + ra.key(n, 1)))
    base = ra.K_IN + ra.key(60, 1)
    for dn, lo, hi, path in QB:
        for i, fr in enumerate(ra.FRACS):
            b = lo + fr * (hi - lo)
            s = b + 0.01 * (hi - lo)
            jobs.append(ra.job("qb_%s_%d_a" % (dn, i), 2.0 * ra.SR, base + [(path, b)]))
            jobs.append(ra.job("qb_%s_%d_b" % (dn, i), 2.0 * ra.SR, base + [(path, s)]))
    return jobs


def partials(x, n):
    seg = x[int(0.3 * ra.SR):int(1.2 * ra.SR)]
    seg = seg * np.hanning(len(seg))
    N = 1 << 18
    mag2 = np.abs(np.fft.rfft(seg, n=N)) ** 2
    freqs = np.fft.rfftfreq(N, 1.0 / ra.SR)
    f0 = 440.0 * 2.0 ** ((n - 69) / 12.0)
    powers, peaks = [], []
    for k in range(1, 7):
        band = np.where((freqs >= 0.94 * k * f0) & (freqs <= 1.06 * k * f0))[0]
        j = band[int(np.argmax(mag2[band]))]
        powers.append(float(mag2[j]))
        peaks.append(float(freqs[j]))
    powers = np.array(powers)
    db = 10.0 * np.log10(powers / powers.max() + 1e-30)
    return f0, db, peaks


def analyse_a(add):
    for n in KEYS_A:
        x = ra.fo("qa_%d" % n, OUT)
        f_est = ra.settled_peak(x)
        f0, db, peaks = partials(x, n)
        cents = 1200.0 * np.log2(f_est / f0)
        dist = [abs(1200.0 * np.log2(f_est / (k * f0))) for k in range(1, 7)]
        k_chosen = 1 + int(np.argmin(dist))
        d12 = float(db[0] - db[1])
        artefact = d12 < -12.0 and k_chosen == 2
        role = "control" if n in CONTROLS else "error"
        repro = "match" if abs(round(cents, 1) - V2_P3_CENTS[n]) < 0.06 else "differs"
        add("QA key=%d role=%s f_nom=%.3f f_est=%.3f cents=%.2f v2_cents=%.1f repro=%s" % (n, role, f0, f_est, cents, V2_P3_CENTS[n], repro))
        add("QA key=%d dB_p1_to_p6=%s p1_minus_p2_db=%.2f measured_ratio_p1_to_p6=%s k_chosen=%d verdict=%s" % (
            n,
            " ".join("%.2f" % v for v in db),
            d12,
            " ".join("%.4f" % (peaks[k] / ((k + 1) * f0)) for k in range(6)),
            k_chosen,
            "PEAK-PICKING ARTEFACT" if artefact else "INSTRUMENT PROPERTY",
        ))


def smoothing(k):
    M = np.zeros((k, k))
    for c in range(k):
        lo = min(c, int(np.ceil(c / BAND)))
        hi = min(k - 1, max(c, int(np.floor(c * BAND))))
        M[c, lo:hi + 1] = 1.0 / (hi - lo + 1)
    return M


def smooth_db(x, M):
    P = np.abs(np.fft.rfft(ra.frames(x), axis=1)) ** 2
    return 10.0 * np.log10(P @ M.T + 1e-10)


def smoothed_lsd(a, b, M):
    m = min(len(a), len(b))
    A = smooth_db(a[:m], M)
    B = smooth_db(b[:m], M)
    return float(np.mean(np.sqrt(np.mean((A - B) ** 2, axis=1))))


def analyse_b(add, M):
    for dn, lo, hi, path in QB:
        bins, smooths = [], []
        for i, fr in enumerate(ra.FRACS):
            a = ra.fo("qb_%s_%d_a" % (dn, i), OUT)
            b = ra.fo("qb_%s_%d_b" % (dn, i), OUT)
            lb = ra.lsd(a, b)
            ls = smoothed_lsd(a, b, M)
            bins.append(lb)
            smooths.append(ls)
            add("QB dial=%s base=%.5f bin_lsd_db=%.4f smooth_lsd_db=%.4f" % (dn, lo + fr * (hi - lo), lb, ls))
        mb = float(np.median(bins))
        xb = float(max(bins))
        ms = float(np.median(smooths))
        xs = float(max(smooths))
        if mb > 1.5 and ms <= 1.5:
            verdict = "METRIC ARTEFACT"
        elif mb > 1.5:
            verdict = "REAL"
        else:
            verdict = "NO MEDIAN FAIL"
        max_rule = "MAX ARTEFACT" if (xb > 6.0 and xs <= 6.0) else "NOT MAX ARTEFACT"
        v2m, v2x = V2_P2[dn]
        repro = "match" if (abs(round(mb, 4) - v2m) < 0.0002 and abs(round(xb, 4) - v2x) < 0.0002) else "differs"
        add("QB DIAL %s bin_median=%.4f bin_max=%.4f smooth_median=%.4f smooth_max=%.4f verdict=%s max_rule=%s v2_median=%.4f v2_max=%.4f repro=%s" % (dn, mb, xb, ms, xs, verdict, max_rule, v2m, v2x, repro))


def run(add):
    if ra.sha256(ra.W + "/resonode_synth.dsp") != ra.DSP_SHA:
        raise SystemExit("dsp sha mismatch")
    add("META resonode-diag faust=%s dsp_sha256=%s" % (ra.FAUST, ra.DSP_SHA))
    arch, recipe = ra.build_toolchain(add)
    add("META faust_cli_recipe %s" % recipe)
    ra.compile_dsp(arch, add)
    ra.build_driver(arch, add)
    jobs = jobs_for()
    ra.write_jobs(ra.W + "/diag.txt", jobs)
    add("META jobs=%d" % len(jobs))
    ra.run_jobs(ra.W + "/diag.txt", OUT, add, "diag")
    analyse_a(add)
    analyse_b(add, smoothing(1025))


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
