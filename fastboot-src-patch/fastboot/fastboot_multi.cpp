#include "fastboot_multi.h"

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#ifndef FBHUB_NO_USB
#include "usb.h"
#endif

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace fastboot_multi {
namespace {

std::vector<std::string> BuildChildArgs(const std::vector<std::string>& original,
                                        const std::string& path) {
    std::vector<std::string> result{"-s", path};
    bool literal = false;
    for (size_t i = 0; i < original.size(); ++i) {
        const std::string& arg = original[i];
        if (!literal && arg == "--") {
            literal = true;
            result.push_back(arg);
            continue;
        }
        if (!literal) {
            if (arg == "--all") continue;
            if (arg == "--hub" || arg == "--index" || arg == "-s") {
                // Skip the value as well.  getopt has already validated it.
                if (i + 1 < original.size()) ++i;
                continue;
            }
            if (arg.rfind("--hub=", 0) == 0 || arg.rfind("--index=", 0) == 0) {
                continue;
            }
            if (arg.rfind("-s", 0) == 0 && arg.size() > 2) {
                continue;
            }
        }
        result.push_back(arg);
    }
    return result;
}

#if defined(_WIN32)

std::wstring Utf8ToWide(const std::string& value) {
    if (value.empty()) return std::wstring();
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                                     static_cast<int>(value.size()), nullptr, 0);
    UINT code_page = CP_UTF8;
    if (length <= 0) {
        code_page = CP_ACP;
        length = MultiByteToWideChar(code_page, 0, value.data(),
                                     static_cast<int>(value.size()), nullptr, 0);
    }
    if (length <= 0) return std::wstring();
    std::wstring result(length, L'\0');
    MultiByteToWideChar(code_page, 0, value.data(), static_cast<int>(value.size()),
                        &result[0], length);
    return result;
}

std::wstring Quote(const std::wstring& arg) {
    if (arg.empty()) return L"\"\"";
    if (arg.find_first_of(L" \t\n\v\"") == std::wstring::npos) return arg;

    std::wstring result(1, L'"');
    int backslashes = 0;
    for (wchar_t ch : arg) {
        if (ch == L'\\') {
            ++backslashes;
            continue;
        }
        if (ch == L'"') {
            result.append(static_cast<size_t>(backslashes * 2 + 1), L'\\');
            result.push_back(L'"');
            backslashes = 0;
            continue;
        }
        result.append(static_cast<size_t>(backslashes), L'\\');
        backslashes = 0;
        result.push_back(ch);
    }
    result.append(static_cast<size_t>(backslashes * 2), L'\\');
    result.push_back(L'"');
    return result;
}

std::wstring ExecutablePath() {
    std::wstring buffer(32768, L'\0');
    DWORD length = GetModuleFileNameW(nullptr, &buffer[0],
                                      static_cast<DWORD>(buffer.size()));
    buffer.resize(length);
    return buffer;
}

HANDLE SpawnChild(const std::vector<std::string>& args) {
    std::wstring executable = ExecutablePath();
    if (executable.empty()) return nullptr;

    std::wstring command_line = Quote(executable);
    for (const auto& arg : args) {
        command_line.push_back(L' ');
        command_line += Quote(Utf8ToWide(arg));
    }

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process{};
    std::vector<wchar_t> mutable_command(command_line.begin(), command_line.end());
    mutable_command.push_back(L'\0');

    if (!CreateProcessW(executable.c_str(), mutable_command.data(), nullptr,
                        nullptr, TRUE, 0, nullptr, nullptr, &startup, &process)) {
        std::fprintf(stderr, "[multi] CreateProcess failed: %lu\n", GetLastError());
        return nullptr;
    }
    CloseHandle(process.hThread);
    return process.hProcess;
}

int WaitChild(HANDLE process) {
    if (process == nullptr) return 127;
    WaitForSingleObject(process, INFINITE);
    DWORD code = 127;
    GetExitCodeProcess(process, &code);
    CloseHandle(process);
    return static_cast<int>(code);
}

#else  // POSIX

std::string ExecutablePath() {
    char buffer[4096];
    ssize_t length = readlink("/proc/self/exe", buffer, sizeof(buffer) - 1);
    if (length > 0) {
        buffer[length] = '\0';
        return buffer;
    }
    return "fastboot";
}

pid_t SpawnChild(const std::vector<std::string>& args) {
    pid_t pid = fork();
    if (pid < 0) {
        std::fprintf(stderr, "[multi] fork failed: %s\n", std::strerror(errno));
        return -1;
    }
    if (pid == 0) {
        std::vector<char*> argv;
        argv.reserve(args.size() + 1);
        for (const auto& arg : args) {
            argv.push_back(const_cast<char*>(arg.c_str()));
        }
        argv.push_back(nullptr);
        std::string executable = ExecutablePath();
        if (executable.find('/') != std::string::npos) {
            execv(executable.c_str(), argv.data());
        }
        execvp(executable.c_str(), argv.data());
        _exit(127);
    }
    return pid;
}

int WaitChild(pid_t pid) {
    if (pid <= 0) return 127;
    int status = 0;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno != EINTR) return 127;
    }
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return 1;
}

#endif

}  // namespace

bool PathMatches(const char* device_path, int hub, int index) {
    if (hub < 0 && index < 0) return true;
    if (device_path == nullptr || device_path[0] == '\0') return false;

    std::string text(device_path);
    if (text.rfind("usb:", 0) == 0) text.erase(0, 4);

    std::vector<int> numbers;
    for (size_t i = 0; i < text.size();) {
        if (text[i] >= '0' && text[i] <= '9') {
            int value = 0;
            while (i < text.size() && text[i] >= '0' && text[i] <= '9') {
                value = value * 10 + (text[i] - '0');
                ++i;
            }
            numbers.push_back(value);
        } else {
            ++i;
        }
    }
    if (numbers.empty()) return false;
    if (index >= 0 && numbers.back() != index) return false;
    if (hub >= 0) {
        if (numbers.size() < 2) return false;
        if (numbers[numbers.size() - 2] != hub) return false;
    }
    return true;
}

std::vector<std::string> ListUsbPaths() {
    std::vector<std::string> paths;
#ifndef FBHUB_NO_USB
    usb_open([&paths](usb_ifc_info* info) {
        if (info->device_path[0] != '\0') {
            paths.emplace_back(info->device_path);
        } else if (info->serial_number[0] != '\0') {
            paths.emplace_back(info->serial_number);
        }
        return -1;  // continue enumerating
    });
#endif
    std::sort(paths.begin(), paths.end());
    paths.erase(std::unique(paths.begin(), paths.end()), paths.end());
    return paths;
}

int RunAll(const std::vector<std::string>& original_args,
           const std::vector<std::string>& paths) {
    if (paths.empty()) {
        std::fprintf(stderr, "[multi] no fastboot devices found\n");
        return 1;
    }

    std::vector<int> codes(paths.size(), 127);
#if defined(_WIN32)
    std::vector<HANDLE> children;
    children.reserve(paths.size());
    for (size_t i = 0; i < paths.size(); ++i) {
        std::fprintf(stderr, "[multi] %s: start\n", paths[i].c_str());
        HANDLE child = SpawnChild(BuildChildArgs(original_args, paths[i]));
        children.push_back(child);
    }
    for (size_t i = 0; i < children.size(); ++i) {
        codes[i] = WaitChild(children[i]);
        std::fprintf(stderr, "[multi] %s: exit %d\n", paths[i].c_str(), codes[i]);
    }
#else
    std::vector<pid_t> children;
    children.reserve(paths.size());
    for (size_t i = 0; i < paths.size(); ++i) {
        std::fprintf(stderr, "[multi] %s: start\n", paths[i].c_str());
        children.push_back(SpawnChild(BuildChildArgs(original_args, paths[i])));
    }
    for (size_t i = 0; i < children.size(); ++i) {
        codes[i] = WaitChild(children[i]);
        std::fprintf(stderr, "[multi] %s: exit %d\n", paths[i].c_str(), codes[i]);
    }
#endif

    size_t failed = 0;
    for (int code : codes) {
        if (code != 0) ++failed;
    }
    std::fprintf(stderr, "[multi] %zu device(s), %zu failed\n", paths.size(),
                 failed);
    return failed == 0 ? 0 : 1;
}

}  // namespace fastboot_multi
