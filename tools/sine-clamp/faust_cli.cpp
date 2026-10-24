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
