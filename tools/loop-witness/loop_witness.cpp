#include <faust/dsp/llvm-dsp.h>
#include <faust/gui/MapUI.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <string>
#include <vector>

namespace
{

const long SR = 48000;
const long BEAT = 24000;
const long T0 = 1000;
const int NIN = 10;
const int NOUT = 22;
const int LOOPER_OUT = 2;

llvm_dsp_factory* gFac = nullptr;
std::vector<float> gX;

struct Cfg {
    long M;
    float B;
    float F;
    long L;
    long finAt;
    long relAt;
    bool press;
    long bias;
    long total;
};

struct Trace {
    std::vector<float> y;
    std::vector<float> widx;
    std::vector<float> wlen;
};

struct Loop {
    long mism;
    long first;
    float maxerr;
    float wmin;
    float wmax;
    long wlenBad;
    float wrapStep;
    float otherMax;
    bool wrapOk;
};

float* zone(std::map<std::string, FAUSTFLOAT*>& zm, const std::string& path)
{
    std::map<std::string, FAUSTFLOAT*>::iterator it = zm.find(path);
    if (it == zm.end()) {
        std::printf("INCONCLUSIVE control path missing: %s\n", path.c_str());
        std::exit(5);
    }
    return it->second;
}

Trace run(const Cfg& c)
{
    Trace tr;
    tr.y.assign(c.total, 0.0f);
    tr.widx.assign(c.total, 0.0f);
    tr.wlen.assign(c.total, 0.0f);

    dsp* d = gFac->createDSPInstance();
    d->init((int)SR);
    if (d->getNumInputs() != NIN || d->getNumOutputs() != NOUT) {
        std::printf("INCONCLUSIVE io mismatch inputs=%d outputs=%d\n", d->getNumInputs(), d->getNumOutputs());
        std::exit(6);
    }

    MapUI ui;
    d->buildUserInterface(&ui);
    std::map<std::string, FAUSTFLOAT*>& zm = ui.getFullpathMap();
    float* zRec = zone(zm, "/looper00/rec");
    float* zFin = zone(zm, "/looper00/finishreq");
    float* zTarget = zone(zm, "/looper00/finishtarget");
    float* zBias = zone(zm, "/looper00/latencybias");
    float* zPlay = zone(zm, "/looper00/play");
    float* zVol = zone(zm, "/looper00/vol");
    float* zErase = zone(zm, "/looper00/erase");
    float* zSide = zone(zm, "/looper00/sidechainsrc");
    float* zWidx = zone(zm, "/looper00/writeidx");
    float* zWlen = zone(zm, "/looper00/wraplen");

    *zPlay = 1.0f;
    *zVol = 1.0f;
    *zErase = 0.0f;
    *zSide = 0.0f;
    *zTarget = (float)c.L;
    *zBias = (float)c.bias;

    float ib[NIN];
    float ob[NOUT];
    float* inp[NIN];
    float* outp[NOUT];
    for (int i = 0; i < NIN; i++) {
        ib[i] = 0.0f;
        inp[i] = &ib[i];
    }
    for (int j = 0; j < NOUT; j++) {
        ob[j] = 0.0f;
        outp[j] = &ob[j];
    }

    for (long t = 0; t < c.total; t++) {
        *zRec = (t >= T0 && t < c.relAt) ? 1.0f : 0.0f;
        *zFin = (c.press && t == c.finAt) ? 1.0f : 0.0f;
        ib[0] = 0.0f;
        ib[1] = gX[t];
        ib[2] = 0.0f;
        ib[3] = 1.0f;
        ib[4] = 1.0f;
        ib[5] = (float)(t % c.M);
        ib[6] = (float)c.M;
        ib[7] = 0.0f;
        ib[8] = c.B;
        ib[9] = c.F;
        d->compute(1, inp, outp);
        tr.y[t] = ob[LOOPER_OUT];
        tr.widx[t] = *zWidx;
        tr.wlen[t] = *zWlen;
    }

    delete d;
    return tr;
}

Loop analyseLoop(const Trace& tr, long L)
{
    Loop r;
    r.mism = 0;
    r.first = -1;
    r.maxerr = 0.0f;
    r.wmin = 1e30f;
    r.wmax = -1e30f;
    r.wlenBad = 0;
    r.wrapStep = 0.0f;
    r.otherMax = 0.0f;
    r.wrapOk = false;

    const long s = T0 + L + 1;
    const long e = T0 + 4 * L + 1;
    for (long t = s; t < e; t++) {
        const float ex = gX[T0 + ((t - T0) % L)];
        const float y = tr.y[t];
        if (y != ex) {
            r.mism++;
            if (r.first < 0) r.first = t - T0;
        }
        const float err = std::fabs(y - ex);
        if (err > r.maxerr) r.maxerr = err;
        const float w = tr.wlen[t];
        if (w < r.wmin) r.wmin = w;
        if (w > r.wmax) r.wmax = w;
        if (w != (float)L) r.wlenBad++;
    }
    for (long t = s + 1; t < e; t++) {
        const float st = std::fabs(tr.y[t] - tr.y[t - 1]);
        if ((t - T0) % L == 0) {
            if (st > r.wrapStep) r.wrapStep = st;
        } else if (st > r.otherMax) {
            r.otherMax = st;
        }
    }
    r.wrapOk = r.wrapStep <= r.otherMax;
    return r;
}

}

int main(int argc, char** argv)
{
    if (argc < 2) {
        std::fprintf(stderr, "usage: loop_witness loop.dsp\n");
        return 2;
    }

    std::vector<const char*> flags;
    const char* lib = std::getenv("FAUST_LIBRARY_DIR");
    if (lib != nullptr && *lib != '\0') {
        flags.push_back("-I");
        flags.push_back(lib);
    }
    flags.push_back("-vec");
    flags.push_back("-fun");
    flags.push_back("-dfs");
    flags.push_back("-vs");
    flags.push_back("32");
    flags.push_back("-nvi");
    flags.push_back("-ct");
    flags.push_back("0");

    std::string err;
    gFac = createDSPFactoryFromFile(argv[1], (int)flags.size(), flags.data(), "", err, -1);
    if (gFac == nullptr) {
        std::printf("INCONCLUSIVE compile failed: %s\n", err.c_str());
        return 4;
    }
    std::printf("compiled %s with %d flags\n", argv[1], (int)flags.size());

    gX.assign(1000000, 0.0f);
    unsigned int seed = 12345u;
    for (size_t i = 0; i < gX.size(); i++) {
        seed = seed * 1664525u + 1013904223u;
        gX[i] = (float)(seed >> 8) * (1.0f / 16777216.0f) - 0.5f;
    }

    bool c1ok = true;
    const long takes[4] = {BEAT, 2 * BEAT, 84000, 6 * BEAT};
    const char* takeName[4] = {"1", "2", "3.5", "6"};
    for (int sc = 0; sc < 2; sc++) {
        for (int i = 0; i < 4; i++) {
            const long L = takes[i];
            const long M = (sc == 0) ? 6 * BEAT : L;
            const float B = (sc == 0) ? 6.0f : (float)L / (float)BEAT;
            Cfg c = {M, B, 0.0f, L, T0 + L / 2, T0 + L / 2 + 1, true, 0, T0 + 4 * L + 16};
            Trace tr = run(c);
            Loop r = analyseLoop(tr, L);
            const bool ok = (r.mism == 0) && r.wrapOk;
            c1ok = c1ok && ok;
            std::printf("C1 scen=%c take=%s beats L=%ld mism=%ld first=%ld maxerr=%g wlen=[%g,%g] wrapstep=%g other=%g %s\n",
                        sc == 0 ? 'A' : 'B', takeName[i], L, r.mism, r.first, r.maxerr, r.wmin, r.wmax,
                        r.wrapStep, r.otherMax, ok ? "ok" : "bad");
        }
    }
    std::printf("CHECK1 %s\n", c1ok ? "PASS" : "FAIL");

    bool c2ok = true;
    bool c2ctl = true;
    const long L2 = 2 * BEAT;
    const long E2[2] = {12000, 47999};
    for (int i = 0; i < 2; i++) {
        const long E = E2[i];
        Cfg c = {6 * BEAT, 6.0f, 0.0f, L2, T0 + E, T0 + E + 1, true, 0, T0 + L2 + 10};
        Trace tr = run(c);
        long bad = 0;
        long firstBad = -1;
        for (long t = T0; t <= T0 + L2 + 2; t++) {
            const long want = std::min(t - T0, L2);
            if ((long)tr.widx[t] != want) {
                bad++;
                if (firstBad < 0) firstBad = t - T0;
            }
        }
        c2ok = c2ok && (bad == 0);
        std::printf("C2 early E=%ld target=%ld widx-mismatch=%ld first=%ld %s\n", E, L2, bad, firstBad,
                    bad == 0 ? "ok" : "bad");

        Cfg k = {6 * BEAT, 6.0f, 0.0f, L2, T0 + E, T0 + E + 1, false, 0, T0 + L2 + 10};
        Trace tk = run(k);
        bool constant = true;
        const long from = T0 + E + 2;
        for (long t = from; t < k.total; t++) {
            if (tk.widx[t] != tk.widx[from]) constant = false;
        }
        const bool ctlOk = constant && (tk.widx[k.total - 1] < (float)L2);
        c2ctl = c2ctl && ctlOk;
        std::printf("C2 control E=%ld no-finishreq widx-constant-after-release=%s widx_end=%g %s\n", E,
                    constant ? "yes" : "no", tk.widx[k.total - 1], ctlOk ? "valid" : "invalid");
    }
    if (!c2ctl) {
        std::printf("CHECK2 INCONCLUSIVE\n");
    } else {
        std::printf("CHECK2 %s\n", c2ok ? "PASS" : "FAIL");
    }

    bool c3ok = true;
    const long L3 = 2 * BEAT;
    const long N3[2] = {64, 259};
    for (int sc = 0; sc < 2; sc++) {
        const long M = (sc == 0) ? 6 * BEAT : L3;
        const float B = (sc == 0) ? 6.0f : 2.0f;
        const long total = T0 + 4 * L3 + 512;
        Cfg rc = {M, B, 0.0f, L3, T0 + L3 / 2, T0 + L3 / 2 + 1, true, 0, total};
        Trace R = run(rc);
        for (int j = 0; j < 2; j++) {
            const long N = N3[j];
            Cfg oc = {M, B, 0.0f, L3, T0 + L3 / 2, T0 + L3 / 2 + 1, true, N, total};
            Trace O = run(oc);
            long mA = 0;
            long mB = 0;
            long mC = 0;
            const long s3 = T0 + L3 + 1;
            const long e3 = T0 + 4 * L3 + 1;
            for (long t = s3; t < e3; t++) {
                if (O.y[t] != R.y[t + N]) mA++;
            }
            for (long t = 0; t < T0 + L3 + 1; t++) {
                if (O.y[t] != R.y[t]) mB++;
            }
            for (long t = 0; t < total; t++) {
                if (O.widx[t] != R.widx[t] || O.wlen[t] != R.wlen[t]) mC++;
            }
            const bool ok = (mA == 0) && (mB == 0) && (mC == 0);
            c3ok = c3ok && ok;
            std::printf("C3 scen=%c N=%ld shift-mism=%ld pre-region-mism=%ld state-mism=%ld %s\n",
                        sc == 0 ? 'A' : 'B', N, mA, mB, mC, ok ? "ok" : "bad");
        }
    }
    std::printf("CHECK3 %s\n", c3ok ? "PASS" : "FAIL");

    bool c4ok = true;
    const long P = 16 * BEAT;
    for (int k = 1; k <= 4; k++) {
        const long L = P >> k;
        for (int F = 0; F <= 1; F++) {
            Cfg c = {P, 16.0f, (float)F, L, T0 + L / 2, T0 + L / 2 + 1, true, 0, T0 + 4 * L + 16};
            Trace tr = run(c);
            Loop r = analyseLoop(tr, L);
            const bool ok = (r.wlenBad == 0) && (r.mism == 0);
            c4ok = c4ok && ok;
            std::printf("C4 k=%d L=%ld fold=%d mism=%ld first=%ld maxerr=%g wlen=[%g,%g] wlenBad=%ld %s\n", k, L, F,
                        r.mism, r.first, r.maxerr, r.wmin, r.wmax, r.wlenBad, ok ? "ok" : "bad");
        }
    }
    std::printf("CHECK4 %s\n", c4ok ? "PASS" : "FAIL");

    deleteDSPFactory(gFac);
    return 0;
}
