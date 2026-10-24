#include <faust/dsp/llvm-dsp.h>
#include <faust/gui/meta.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
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

int main(int argc, char** argv) {
  if (argc < 5) { fprintf(stderr, "usage: render_sweep dsp gain outdir wav...\n"); return 2; }
  const char* dspPath = argv[1];
  float gain = (float)atof(argv[2]);
  std::string outdir = argv[3];
  std::vector<std::string> store;
  if (const char* ff = std::getenv("FAUST_FLAGS")) {
    std::istringstream is(ff); std::string tok;
    while (is >> tok) store.push_back(tok);
  }
  if (const char* libDir = std::getenv("FAUST_LIBRARY_DIR")) {
    if (*libDir != '\0') { store.push_back("-I"); store.push_back(libDir); }
  }
  std::vector<const char*> flags;
  for (auto& s : store) flags.push_back(s.c_str());
  std::string err;
  llvm_dsp_factory* fac = createDSPFactoryFromFile(dspPath, (int)flags.size(), flags.data(), "", err, -1);
  if (!fac) { fprintf(stderr, "compile fail: %s\n", err.c_str()); return 4; }
  fprintf(stderr, "compiled %s with %zu flag tokens\n", dspPath, flags.size());
  const int B = 4800;
  for (int a = 4; a < argc; a++) {
    const char* wavPath = argv[a];
    std::string base = wavPath;
    size_t sl = base.find_last_of('/'); if (sl != std::string::npos) base = base.substr(sl+1);
    if (base.size() > 4) base = base.substr(0, base.size()-4);
    int sr = 48000;
    std::vector<float> in = loadWav(wavPath, sr);
    if (in.empty()) { fprintf(stderr, "wav load failed %s\n", wavPath); return 5; }
    for (auto& v : in) v *= gain;
    dsp* d = fac->createDSPInstance(); d->init(sr);
    int no = d->getNumOutputs();
    std::vector<std::vector<float>> ob(no, std::vector<float>(B, 0.0f));
    std::vector<float*> op(no);
    for (int i = 0; i < no; i++) op[i] = ob[i].data();
    std::vector<float> ibuf(B, 0.0f);
    float* ip[1] = { ibuf.data() };
    std::string outPath = outdir + "/" + base + ".txt";
    FILE* fo = fopen(outPath.c_str(), "w");
    if (!fo) { fprintf(stderr, "cannot open %s\n", outPath.c_str()); return 6; }
    long pos = 0, n = (long)in.size();
    while (pos < n) {
      long c = n - pos; if (c > B) c = B;
      std::fill(ibuf.begin(), ibuf.end(), 0.0f);
      memcpy(ibuf.data(), &in[pos], c*sizeof(float));
      d->compute(B, ip, op.data());
      fprintf(fo, "%.4f %.9g\n", (double)(pos+c)/sr, (double)ob[0][c-1]);
      pos += c;
    }
    fclose(fo);
    delete d;
    fprintf(stderr, "rendered %s blocks %ld\n", base.c_str(), (n + B - 1) / B);
  }
  deleteDSPFactory(fac);
  return 0;
}
