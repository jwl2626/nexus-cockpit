"""ADB 通道：通过 adb.exe 给座舱发 Android 层命令。"""

from __future__ import annotations

from typing import Any

from ..types import ProbeResult
from .base import Channel, which


class AdbChannel(Channel):
    name = "adb"

    def __init__(self, exe: str = "adb", serial: str | None = None):
        self.exe = exe
        self.serial = serial

    def available(self) -> tuple[bool, str]:
        found = which(self.exe) or which(self.exe + ".exe")
        if not found:
            return False, f"PATH 里找不到 {self.exe}，请安装 platform-tools 或指定路径"
        return True, found

    def run(self, check: dict[str, Any]) -> ProbeResult:
        argv: list[str] = [self.exe]
        serial = check.get("serial") or self.serial
        if check.get("use_serial", True) and serial:
            argv += ["-s", str(serial)]
        argv += [str(a) for a in check.get("args", [])]
        if not check.get("args"):
            return self._result(check, "error", "检查项缺少 args")
        return self.exec_check(check, argv)
