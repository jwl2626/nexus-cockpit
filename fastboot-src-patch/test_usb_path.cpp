#include "usb_path_windows.h"

#include <windows.h>
#include <setupapi.h>

#include <cstdio>
#include <string>
#include <vector>

static const GUID kUsbDeviceInterface = {
    0xA5DCBF10, 0x6530, 0x11D2,
    {0x90, 0x1F, 0x00, 0xC0, 0x4F, 0xB9, 0x51, 0xED}};

static int CheckMatches() {
    struct Case {
        const char* path;
        int hub;
        int index;
        bool expected;
    } cases[] = {
        {"usb:1D00:0-1.3", 1, 3, true},
        {"usb:1D00:0-1.3", 2, 3, false},
        {"usb:1D00:0-1.3", -1, 3, true},
        {"usb:1D00:0-1.3", 1, -1, true},
        {"usb:1D00:0-1.4", 1, 3, false},
        {"usb:1-3", 1, 3, true},
        {"usb:h4p3", -1, 3, true},
        {"usb:h4p3", 4, 3, true},
        {"usb:h4p3", 3, 3, false},
        {"1234567890", -1, 3, false},
    };
    int failures = 0;
    for (const auto& item : cases) {
        bool actual = fastboot::UsbPathMatches(item.path, item.hub, item.index);
        if (actual != item.expected) {
            std::printf("MATCH FAIL: %s hub=%d index=%d => %d (want %d)\n",
                        item.path, item.hub, item.index, actual, item.expected);
            ++failures;
        }
    }
    std::printf("match tests: %d failures\n", failures);
    return failures;
}

int main() {
    int failures = CheckMatches();
    HDEVINFO handles = SetupDiGetClassDevsW(
        &kUsbDeviceInterface, nullptr, nullptr,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (handles == INVALID_HANDLE_VALUE) {
        std::printf("SetupDiGetClassDevs failed: %lu\n", GetLastError());
        return 1;
    }

    for (DWORD index = 0;; ++index) {
        SP_DEVICE_INTERFACE_DATA interface_data{};
        interface_data.cbSize = sizeof(interface_data);
        if (!SetupDiEnumDeviceInterfaces(
                handles, nullptr, &kUsbDeviceInterface, index, &interface_data)) {
            break;
        }
        DWORD required = 0;
        SP_DEVINFO_DATA device_info{};
        device_info.cbSize = sizeof(device_info);
        SetupDiGetDeviceInterfaceDetailW(
            handles, &interface_data, nullptr, 0, &required, &device_info);
        if (required == 0) continue;

        std::vector<unsigned char> buffer(required);
        auto detail = reinterpret_cast<SP_DEVICE_INTERFACE_DETAIL_DATA_W*>(
            buffer.data());
#ifdef _WIN64
        detail->cbSize = 8;
#else
        detail->cbSize = 6;
#endif
        if (!SetupDiGetDeviceInterfaceDetailW(
                handles, &interface_data, detail, required, nullptr, &device_info)) {
            continue;
        }

        char path[256] = {0};
        bool ok = fastboot::UsbPathFromInterfaceName(detail->DevicePath, path,
                                                     sizeof(path));
        std::wprintf(L"%ls\n  -> %hs (ok=%d)\n", detail->DevicePath, path, ok);
    }
    SetupDiDestroyDeviceInfoList(handles);
    return failures == 0 ? 0 : 1;
}
