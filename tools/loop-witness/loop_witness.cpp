#include <faust/gui/meta.h>
#include <faust/gui/UI.h>
#include <faust/gui/MapUI.h>
#include <faust/dsp/dsp.h>
#include "dsp.cpp"
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
const int PAD = 64;
const char* LOOPER = "/loop/looper_0/";

std::vector<float> gX;
long gNz = 0;

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
    long nz;
    float wrapStep;
    float otherMax;
    bool wrapOk;
};

std::string path(const char* name)
{
    return std::string(LOOPER) + name;
}

float* zone(std::map<std::string, FAUSTFLOAT*>& zm, const std::string& p)
{
    std::map<std::string, FAUSTFLOAT*>::iterator it = zm.find(p);
    if (it == zm.end()) {
        std::printf("INCONCLUSIVE control path missing: %s\n", p.c_str());
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

    mydsp* d = new mydsp();
    d->init((int)SR);
    if (d->getNumInputs() != NIN || d->getNumOutputs() != NOUT) {
        std::printf("INCONCLUSIVE io mismatch inputs=%d outputs=%d\n", d->getNumInputs(), d->getNumOutputs());
        std::exit(6);
    }
    std::printf("io inputs=%d outputs=%d\n", d->getNumInputs(), d->getNumOutputs());

    MapUI ui;
    d->buildUserInterface(&ui);
    std::map<std::string, FAUSTFLOAT*>& zm = ui.getFullpathMap();
    float* zRec = zone(zm, path("rec"));
    float* zFin = zone(zm, path("finishreq"));
    float* zTarget = zone(zm, path("finishtarget"));
    float* zBias = zone(zm, path("latencybias"));
    float* zPlay = zone(zm, path("play"));
    float* zVol = zone(zm, path("vol"));
    float* zErase = zone(zm, path("erase"));
    float* zSide = zone(zm, path("sidechainsrc"));
    float* zWidx = zone(zm, path("writeidx"));
    float* zWlen = zone(zm, path("wraplen"));

    *zPlay = 1.0f;
    *zVol = 1.0f;
    *zErase = 0.0f;
    *zSide = 0.0f;
    *zTarget = (float)c.L;
    *zBias = (float)c.bias;

    float ibuf[NIN * PAD];
    float obuf[NOUT * PAD];
    float* inp[NIN];
    float* outp[NOUT];
    for (int i = 0; i < NIN * PAD; i++) ibuf[i] = 0.0f;
    for (int j = 0; j < NOUT * PAD; j++) obuf[j] = 0.0f;
    for (int i = 0; i < NIN; i++) inp[i] = &ibuf[i * PAD];
    for (int j = 0; j < NOUT; j++) outp[j] = &obuf[j * PAD];

    for (long t = 0; t < c.total; t++) {
        *zRec = (t >= T0 && t < c.relAt) ? 1.0f : 0.0f;
        *zFin = (c.press && t == c.finAt) ? 1.0f : 0.0f;
        ibuf[0 * PAD] = 0.0f;
        ibuf[1 * PAD] = gX[t];
        ibuf[2 * PAD] = 0.0f;
        ibuf[3 * PAD] = 1.0f;
        ibuf[4 * PAD] = 1.0f;
        ibuf[5 * PAD] = (float)(t % c.M);
        ibuf[6 * PAD] = (float)c.M;
        ibuf[7 * PAD] = 0.0f;
        ibuf[8 * PAD] = c.B;
        ibuf[9 * PAD] = c.F;
        d->compute(1, inp, outp);
        tr.y[t] = obuf[LOOPER_OUT * PAD];
        tr.widx[t] = *zWidx;
        tr.wlen[t] = *zWlen;
        if (tr.y[t] != 0.0f) gNz++;
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
    r.nz = 0;
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
        if (y != 0.0f) r.nz++;
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
    if (argc > 1 && std::string(argv[1]) == "--dump") {
        mydsp* d = new mydsp();
        d->init((int)SR);
        MapUI ui;
        d->buildUserInterface(&ui);
        std::map<std::string, FAUSTFLOAT*>& zm = ui.getFullpathMap();
        for (std::map<std::string, FAUSTFLOAT*>::iterator it = zm.begin(); it != zm.end(); ++it) {
            std::printf("UIPATH %s\n", it->first.c_str());
        }
        delete d;
        return 0;
    }
    std::printf("backend cpp (generated mydsp, dsp.cpp from faust_cli, flags -lang cpp -vec -fun -dfs -vs 32 -nvi -ct 0)\n");

    gX.assign(1000000, 0.0f);
    unsigned int seed = 12345u;
    for (size_t i = 0; i < gX.size(); i++) {
        seed = seed * 1664525u + 1013904223u;
        gX[i] = (float)(seed >> 8) * (1.0f / 16777216.0f) - 0.5f;
    }

    bool c1ok = true;
    const long takes[7] = {BEAT, 2 * BEAT, 3 * BEAT, 84000, 4 * BEAT, 5 * BEAT, 6 * BEAT};
    const char* takeName[7] = {"1", "2", "3", "3.5", "4", "5", "6"};
    for (int sc = 0; sc < 2; sc++) {
        for (int i = 0; i < 7; i++) {
            const long L = takes[i];
            const long M = (sc == 0) ? 6 * BEAT : L;
            const float B = (sc == 0) ? 6.0f : (float)L / (float)BEAT;
            Cfg c = {M, B, 0.0f, L, T0 + L / 2, T0 + L / 2 + 1, true, 0, T0 + 4 * L + 16};
            Trace tr = run(c);
            Loop r = analyseLoop(tr, L);
            const bool ok = (r.mism == 0) && r.wrapOk;
            c1ok = c1ok && ok;
            std::printf("C1 scen=%c take=%s beats L=%ld mism=%ld first=%ld maxerr=%g nz=%ld wlen=[%g,%g] wrapstep=%g other=%g %s\n",
                        sc == 0 ? 'A' : 'B', takeName[i], L, r.mism, r.first, r.maxerr, r.nz, r.wmin, r.wmax,
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
            std::printf("C4 k=%d L=%ld fold=%d mism=%ld first=%ld maxerr=%g nz=%ld wlen=[%g,%g] wlenBad=%ld %s\n", k, L, F,
                        r.mism, r.first, r.maxerr, r.nz, r.wmin, r.wmax, r.wlenBad, ok ? "ok" : "bad");
        }
    }
    std::printf("CHECK4 %s\n", c4ok ? "PASS" : "FAIL");
    std::printf("HARNESS nonzero-output-samples=%ld\n", gNz);
    if (gNz == 0) std::printf("HARNESS SILENT\n");
    return 0;
}
