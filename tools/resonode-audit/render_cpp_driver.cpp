#include <faust/gui/meta.h>
#include <faust/gui/UI.h>
#include <faust/gui/MapUI.h>
#include <faust/dsp/dsp.h>
#include "dsp.cpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

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

static void writeNpy(const char* p, const std::vector<float>& v) {
    char dict[256];
    snprintf(dict, sizeof(dict), "{'descr': '<f4', 'fortran_order': False, 'shape': (%zu,), }", v.size());
    std::string h(dict);
    size_t want = 64 - 10;
    while (h.size() + 1 < want) h.push_back(' ');
    h.push_back('\n');
    FILE* f = fopen(p, "wb");
    const unsigned char magic[6] = {0x93,'N','U','M','P','Y'};
    fwrite(magic, 1, 6, f);
    unsigned char ver[2] = {1, 0}; fwrite(ver, 1, 2, f);
    unsigned short hl = (unsigned short)h.size();
    fwrite(&hl, 2, 1, f);
    fwrite(h.data(), 1, h.size(), f);
    fwrite(v.data(), sizeof(float), v.size(), f);
    fclose(f);
}

struct CtlEvent { long frame; std::string path; float value; };

struct CtlJob {
    std::string name;
    long len;
    long pre;
    std::string inPath;
    std::vector<CtlEvent> events;
    CtlJob() : len(0), pre(0), inPath("-") {}
};

struct ResolvedEvent { long frame; std::string addr; float value; };

static std::vector<CtlJob> readJobs(const char* path) {
    std::vector<CtlJob> jobs;
    std::ifstream f(path);
    std::string line;
    while (std::getline(f, line)) {
        std::istringstream s(line);
        std::string op;
        if (!(s >> op)) continue;
        if (op == "job") { jobs.push_back(CtlJob()); s >> jobs.back().name; }
        else if (jobs.empty()) continue;
        else if (op == "len") s >> jobs.back().len;
        else if (op == "pre") s >> jobs.back().pre;
        else if (op == "in") s >> jobs.back().inPath;
        else if (op == "set") { CtlEvent e; s >> e.frame >> e.path >> e.value; jobs.back().events.push_back(e); }
    }
    return jobs;
}

static bool resolveAddress(MapUI& ui, const std::string& path, std::string& out) {
    int hits = 0;
    std::string hit;
    size_t n = path.size();
    for (int i = 0; i < ui.getParamsCount(); i++) {
        std::string a = ui.getParamAddress(i);
        if (a == path) { out = a; return true; }
        if (a.size() > n && a.compare(a.size() - n, n, path) == 0 && a[a.size() - n - 1] == '/') { hit = a; hits++; }
    }
    if (hits == 1) { out = hit; return true; }
    return false;
}

static int runCtl(const char* jobPath, const char* outDir) {
    std::vector<CtlJob> jobs = readJobs(jobPath);
    if (jobs.empty()) { fprintf(stderr, "no jobs in %s\n", jobPath); return 2; }
    const int B = 64;
    for (size_t j = 0; j < jobs.size(); j++) {
        CtlJob& job = jobs[j];
        std::vector<float> in((size_t)job.len, 0.0f);
        if (job.inPath != "-") {
            int sr = 48000;
            std::vector<float> w = loadWav(job.inPath.c_str(), sr);
            if (w.empty() || sr != 48000) { fprintf(stderr, "input load failed %s\n", job.inPath.c_str()); return 3; }
            for (size_t i = 0; i < w.size() && (long)(job.pre + (long)i) < job.len; i++) in[job.pre + i] = w[i];
        }
        mydsp* d = new mydsp();
        d->init(48000);
        MapUI ui;
        d->buildUserInterface(&ui);
        std::vector<ResolvedEvent> evs;
        for (size_t k = 0; k < job.events.size(); k++) {
            std::string addr;
            if (!resolveAddress(ui, job.events[k].path, addr)) { fprintf(stderr, "unknown parameter %s\n", job.events[k].path.c_str()); return 4; }
            ResolvedEvent r; r.frame = job.events[k].frame; r.addr = addr; r.value = job.events[k].value;
            evs.push_back(r);
        }
        std::stable_sort(evs.begin(), evs.end(), [](const ResolvedEvent& a, const ResolvedEvent& b) { return a.frame < b.frame; });
        std::vector<float> out((size_t)job.len, 0.0f);
        float ib[B], ob[B];
        float* ip[1] = { ib };
        float* op[1] = { ob };
        size_t e = 0;
        long pos = 0;
        while (pos < job.len) {
            while (e < evs.size() && evs[e].frame <= pos) { ui.setParamValue(evs[e].addr, evs[e].value); e++; }
            long limit = (e < evs.size()) ? std::min<long>(evs[e].frame, job.len) : job.len;
            long c = std::min<long>(B, limit - pos);
            memcpy(ib, &in[pos], c * sizeof(float));
            d->compute((int)c, ip, op);
            memcpy(&out[pos], ob, c * sizeof(float));
            pos += c;
        }
        std::string outPath = std::string(outDir) + "/" + job.name + ".f32";
        FILE* fo = fopen(outPath.c_str(), "wb");
        if (!fo) { fprintf(stderr, "cannot write %s\n", outPath.c_str()); return 5; }
        fwrite(out.data(), sizeof(float), out.size(), fo);
        fclose(fo);
        delete d;
        fprintf(stderr, "ctl: %s frames %ld events %zu\n", job.name.c_str(), job.len, evs.size());
    }
    return 0;
}

int main(int argc, char** argv) {
    if (argc >= 2 && std::strcmp(argv[1], "--ctl") == 0) {
        if (argc != 4) { fprintf(stderr, "usage: render_cpp --ctl <jobfile> <outdir>\n"); return 2; }
        return runCtl(argv[2], argv[3]);
    }
    if (argc < 5) { fprintf(stderr, "usage: render_cpp dsp gain outprefix wav...\n"); return 2; }
    float gain = (float)atof(argv[2]);
    std::string pre = argv[3];
    for (int a = 4; a < argc; a++) {
        const char* wavPath = argv[a];
        std::string base = wavPath;
        size_t sl = base.find_last_of('/'); if (sl != std::string::npos) base = base.substr(sl+1);
        if (base.size() > 4) base = base.substr(0, base.size()-4);
        int sr = 48000;
        std::vector<float> in = loadWav(wavPath, sr);
        if (in.empty()) { fprintf(stderr, "wav load failed %s\n", wavPath); continue; }
        for (auto& v : in) v *= gain;
        mydsp* d = new mydsp();
        d->init(sr);
        int no = d->getNumOutputs();
        const int B = 4800;
        static float ib[B];
        std::vector<std::vector<float>> ob(no, std::vector<float>(B, 0.0f));
        std::vector<float*> op(no);
        for (int i = 0; i < no; i++) op[i] = ob[i].data();
        float* ip[1] = { ib };
        std::vector<float> full;
        FILE* fo = fopen((pre + "_" + base + ".txt").c_str(), "w");
        long pos = 0, n = (long)in.size();
        while (pos < n) {
            long c = n - pos; if (c > B) c = B;
            memset(ib, 0, sizeof(ib));
            memcpy(ib, &in[pos], c*sizeof(float));
            d->compute(B, ip, op.data());
            for (long k = 0; k < c; k++) full.push_back(ob[0][k]);
            fprintf(fo, "%.4f %.4f\n", (double)(pos+c)/sr, ob[0][c-1]);
            pos += c;
        }
        fclose(fo);
        writeNpy((pre + "_" + base + ".npy").c_str(), full);
        fprintf(stderr, "render_cpp: %s frames %zu\n", base.c_str(), full.size());
        delete d;
    }
    return 0;
}
