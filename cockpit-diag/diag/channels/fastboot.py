"""Fastboot 通道：通过 fastboot.exe 读变量 / 执行 bootloader 层命令。

注意：这台机器能用的 fbhub（工作区里的 fastboot-hub 项目）是按 USB 物理路径
选设备的，适合"没有 SN 的多台设备"。这里为了教学先用官方 fastboot.exe，
等你把产线指令给我，可以换成直接调用 fbhub 的协议层（见 docs/02）。
"""

from __future__ import annotations

from typing import Any

from ..types import ProbeResult
from .base import Channel, which

# 只读命令白名单：诊断默认不应该改设备状态。
READONLY = {
    "getvar", "devices", "version", "help", "oem",
}


class FastbootChannel(Channel):
    name = "fastboot"

    def __init__(self, exe: str = "fastboot", serial: str | None = None):
        self.exe = exe
        self.serial = serial

    def available(self) -> tuple[bool, str]:
        found = which(self.exe) or which(self.exe + ".exe")
        if not found:
            return False, f"PATH 里找不到 {self.exe}，请安装 platform-tools 或指定路径"
        return True, found

    def run(self, check: dict[str, Any]) -> ProbeResult:
        args = [str(a) for a in check.get("args", [])]
        if not args:
            return self._result(check, "error", "检查项缺少 args")
        argv: list[str] = [self.exe]
        serial = check.get("serial") or self.serial
        if serial and check.get("use_serial", True):
            argv += ["-s", str(serial)]
        argv += args
        return self.exec_check(check, argv)
