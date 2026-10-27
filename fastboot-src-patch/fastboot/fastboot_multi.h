#pragma once

#include <string>
#include <vector>

namespace fastboot_multi {

// True when a fastboot device path matches the optional --hub / --index
// filters.  Only the last two numeric components are used, so both
// "usb:1D00:0-1.3" and Linux's "usb:1-2.3" work.  -1 means "don't care".
bool PathMatches(const char* device_path, int hub, int index);

// Enumerate every fastboot device, preferring the USB path and falling back
// to the serial number.  The callback used by usb_open returns -1 so that the
// enumeration continues through all interfaces.
std::vector<std::string> ListUsbPaths();

// Run the same fastboot command line on every path, one child process per
// device, in parallel.  Returns 0 only if every child exits with 0.
int RunAll(const std::vector<std::string>& original_args,
           const std::vector<std::string>& paths);

}  // namespace fastboot_multi
