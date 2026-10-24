#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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
  if (argc < 4) { fprintf(stderr, "usage: driver gain outdir wav...\n"); return 2; }
  float gain = (float)atof(argv[1]);
  std::string outdir = argv[2];
  const int B = 4800;
  for (int a = 3; a < argc; a++) {
    const char* wavPath = argv[a];
    std::string base = wavPath;
    size_t sl = base.find_last_of('/'); if (sl != std::string::npos) base = base.substr(sl+1);
    if (base.size() > 4) base = base.substr(0, base.size()-4);
    int sr = 48000;
    std::vector<float> in = loadWav(wavPath, sr);
    if (in.empty()) { fprintf(stderr, "wav load failed %s\n", wavPath); return 5; }
    for (auto& v : in) v *= gain;
    mydsp d;
    d.init(sr);
    std::vector<float> ibuf(B, 0.0f), obuf(B, 0.0f);
    FAUSTFLOAT* ip[1] = { ibuf.data() };
    FAUSTFLOAT* op[1] = { obuf.data() };
    std::string outPath = outdir + "/" + base + ".txt";
    FILE* fo = fopen(outPath.c_str(), "w");
    if (!fo) { fprintf(stderr, "cannot open %s\n", outPath.c_str()); return 6; }
    long pos = 0, n = (long)in.size();
    while (pos < n) {
      long c = n - pos; if (c > B) c = B;
      std::fill(ibuf.begin(), ibuf.end(), 0.0f);
      memcpy(ibuf.data(), &in[pos], c*sizeof(float));
      d.compute(B, ip, op);
      fprintf(fo, "%.4f %.9g\n", (double)(pos+c)/sr, (double)obuf[c-1]);
      pos += c;
    }
    fclose(fo);
    fprintf(stderr, "rendered %s blocks %ld\n", base.c_str(), (n + B - 1) / B);
  }
  return 0;
}
