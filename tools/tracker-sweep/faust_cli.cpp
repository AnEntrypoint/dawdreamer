// faust_cli: the faust 2.85.9 command line rebuilt from its own entry point.
// compiler/main.cpp is `createFactory("FaustDSP", "", argc, argv, error_msg, true)` with the
// arguments unchanged. The libfaust C API (generateAuxFilesFromFile) strips -vec from argv before
// compiling (compiler/libcode.cpp path via generateAuxFilesFromString), so it cannot produce the
// pinned-flag output; this program calls the same function the CLI calls, with the flags intact.
// Link against the 2.85.9 release lib/libfaustwithllvm.a.
#include <cstdlib>
#include <iostream>
#include <string>

class dsp_factory_base;
dsp_factory_base* createFactory(const std::string& name_app, const std::string& dsp_content,
                                int argc, const char* argv[], std::string& error_msg, bool generate);

int main(int argc, const char* argv[])
{
    std::string error_msg;
    createFactory("FaustDSP", "", argc, argv, error_msg, true);
    if (error_msg == "") {
        return EXIT_SUCCESS;
    }
    std::cerr << error_msg;
    return EXIT_FAILURE;
}
