#include <faust/dsp/llvm-dsp.h>
#include <faust/gui/meta.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
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

int main(int argc, char** argv) {
  if (argc < 5) { fprintf(stderr, "usage: render_multi dsp gain outprefix wav...\n"); return 2; }
  const char* dspPath = argv[1];
  float gain = (float)atof(argv[2]); std::string pre = argv[3];
  std::string err;
  llvm_dsp_factory* fac = createDSPFactoryFromFile(dspPath, 0, nullptr, "", err, -1);
  if (!fac) { fprintf(stderr, "compile fail: %s\n", err.c_str()); return 4; }
  for (int a = 4; a < argc; a++) {
    const char* wavPath = argv[a];
    std::string base = wavPath;
    size_t sl = base.find_last_of('/'); if (sl != std::string::npos) base = base.substr(sl+1);
    if (base.size() > 4) base = base.substr(0, base.size()-4);
    int sr = 48000;
    std::vector<float> in = loadWav(wavPath, sr);
    if (in.empty()) { fprintf(stderr, "wav load failed %s\n", wavPath); continue; }
    for (auto& v : in) v *= gain;
    dsp* d = fac->createDSPInstance(); d->init(sr);
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
    fprintf(stderr, "render_multi: %s frames %zu\n", base.c_str(), full.size());
    delete d;
  }
  deleteDSPFactory(fac);
  return 0;
}
