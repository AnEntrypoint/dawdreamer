#include <faust/gui/meta.h>
#include <faust/gui/UI.h>
#include <faust/dsp/dsp.h>
#include "dsp.cpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static const char* NAMES[] = {"out", "heldFreq", "confident", "coarse", "refinedFreq", "refinedLag", "delta", "delta2",
                              "L0", "Lraw", "takeNew", "path", "dom2", "demoteNow", "ready"};
static const int NCH = 15;

static std::vector<float> loadWav(const char* p, int& sr) {
    FILE* f = fopen(p, "rb"); if (!f) return {};
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    std::vector<unsigned char> b(sz);
    if (fread(b.data(), 1, sz, f) != (size_t)sz) { fclose(f); return {}; }
    fclose(f);
    int ch = 1, bits = 16; long dpos = -1, dlen = 0, q = 12;
    while (q + 8 <= sz) {
        unsigned cl = b[q+4] | (b[q+5]<<8) | (b[q+6]<<16) | ((unsigned)b[q+7]<<24);
        if (!memcmp(&b[q], "fmt ", 4)) { ch = b[q+10] | (b[q+11]<<8); sr = b[q+12] | (b[q+13]<<8) | (b[q+14]<<16) | (b[q+15]<<24); bits = b[q+22] | (b[q+23]<<8); }
        if (!memcmp(&b[q], "data", 4)) { dpos = q+8; dlen = cl; if (dpos+dlen > sz) dlen = sz-dpos; break; }
        q += 8 + cl + (cl & 1);
    }
    if (dpos < 0 || bits != 16) return {};
    long n = dlen / (2L*ch); std::vector<float> o(n);
    for (long i = 0; i < n; i++) { short v = (short)(b[dpos+i*2*ch] | (b[dpos+i*2*ch+1]<<8)); o[i] = v/32768.0f; }
    return o;
}

static void writeF32(const std::string& p, const std::vector<float>& v) {
    FILE* f = fopen(p.c_str(), "wb");
    fwrite(v.data(), sizeof(float), v.size(), f);
    fclose(f);
}

int main(int argc, char** argv) {
    if (argc != 4) { fprintf(stderr, "usage: render_subblock gain outprefix wav\n"); return 2; }
    float gain = (float)atof(argv[1]);
    std::string pre = argv[2];
    int sr = 48000;
    std::vector<float> in = loadWav(argv[3], sr);
    if (in.empty()) { fprintf(stderr, "wav load failed %s\n", argv[3]); return 1; }
    for (auto& v : in) v *= gain;
    mydsp* d = new mydsp();
    d->init(sr);
    int no = d->getNumOutputs();
    if (no != 1 && no != NCH) { fprintf(stderr, "expected 1 or %d outputs, got %d\n", NCH, no); return 3; }
    const int B = 4800;
    static float ib[B];
    std::vector<std::vector<float>> ob(no, std::vector<float>(B, 0.0f));
    std::vector<float*> op(no);
    for (int i = 0; i < no; i++) op[i] = ob[i].data();
    float* ip[1] = { ib };
    std::vector<float> ch0;
    ch0.reserve(in.size());
    FILE* fo = nullptr;
    if (no == NCH) {
        fo = fopen((pre + ".tsv").c_str(), "w");
        fprintf(fo, "n\tt\tblk\tk");
        for (int i = 0; i < NCH; i++) fprintf(fo, "\t%s", NAMES[i]);
        fprintf(fo, "\n");
    }
    float prev[NCH];
    bool havePrev = false;
    long pos = 0, n = (long)in.size(), block = 0, rows = 0;
    while (pos < n) {
        long c = n - pos; if (c > B) c = B;
        memset(ib, 0, sizeof(ib));
        memcpy(ib, &in[pos], c * sizeof(float));
        d->compute(B, ip, op.data());
        for (long k = 0; k < c; k++) {
            ch0.push_back(ob[0][k]);
            if (no != NCH) continue;
            float cur[NCH];
            bool emit = !havePrev || k < 2;
            for (int i = 0; i < NCH; i++) {
                cur[i] = ob[i][k];
                if (!emit && std::memcmp(&cur[i], &prev[i], sizeof(float)) != 0) emit = true;
            }
            if (emit) {
                fprintf(fo, "%ld\t%.6f\t%ld\t%ld", pos + k, (double)(pos + k) / sr, block, k);
                for (int i = 0; i < NCH; i++) fprintf(fo, "\t%.9g", (double)cur[i]);
                fprintf(fo, "\n");
                rows++;
            }
            std::memcpy(prev, cur, sizeof(prev));
            havePrev = true;
        }
        pos += c; block++;
    }
    if (fo) fclose(fo);
    writeF32(pre + "_ch0.f32", ch0);
    fprintf(stderr, "render_subblock: outputs %d blocks %ld frames %zu rows %ld\n", no, block, ch0.size(), rows);
    delete d;
    return 0;
}
