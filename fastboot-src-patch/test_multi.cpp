#include "fastboot/fastboot_multi.h"

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc > 1) {
        std::printf("child:");
        for (int i = 1; i < argc; ++i) std::printf(" [%s]", argv[i]);
        std::printf("\n");
        for (int i = 1; i < argc; ++i) {
            if (std::strcmp(argv[i], "--fail") == 0) return 3;
        }
        return 0;
    }

    if (!fastboot_multi::PathMatches("usb:1D00:0-1.3", 1, 3)) return 10;
    if (fastboot_multi::PathMatches("usb:1D00:0-1.3", 2, 3)) return 11;
    if (!fastboot_multi::PathMatches("usb:1-2.3", 2, 3)) return 12;
    if (!fastboot_multi::PathMatches("usb:h4p3", 4, 3)) return 13;
    if (fastboot_multi::PathMatches("1234567890", -1, 3)) return 14;

    std::vector<std::string> args{"--message", "hello world"};
    std::vector<std::string> paths{"usb:1D00:0-1.3", "usb:1D00:0-1.4"};
    int code = fastboot_multi::RunAll(args, paths);
    std::printf("RunAll success cases => %d\n", code);
    if (code != 0) return 20;

    std::vector<std::string> fail_args{"--fail"};
    code = fastboot_multi::RunAll(fail_args, paths);
    std::printf("RunAll failure cases => %d\n", code);
    if (code == 0) return 21;
    return 0;
}
