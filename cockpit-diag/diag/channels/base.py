"""通道基类。

四个通道（ADB / Fastboot / CAN / 以太网）干的其实是同一件事：
    收到一个检查项定义 -> 发指令 -> 把"成没成、多久、返回了什么"记下来。

所以它们共享一个 run() 契约和一套子进程执行工具，差异只在"怎么发指令"。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any, Sequence

from ..types import (
    ProbeResult,
    STATUS_ERROR,
    STATUS_FAIL,
    STATUS_OK,
    STATUS_TIMEOUT,
)


class ChannelUnavailable(RuntimeError):
    """这台电脑上跑不了这个通道（缺驱动、缺工具、缺硬件）。"""


def _no_window() -> int:
    """Windows 下不要弹出黑窗口。"""
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return 0


class Channel:
    name = "base"

    def available(self) -> tuple[bool, str]:
        """返回 (能否使用, 原因)。真实采集前先问一句，避免一堆无意义的报错。"""
        return True, ""

    def run(self, check: dict[str, Any]) -> ProbeResult:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 子进程工具
    # ------------------------------------------------------------------
    def exec_check(self, check: dict[str, Any], argv: Sequence[str]) -> ProbeResult:
        """跑一条本地命令，把结果翻译成 ProbeResult。

        判定逻辑：返回码 0 = ok；有 expect_contains 时还要能匹配上；
        找不到程序算 error（环境问题），超时算 timeout（链路/对方问题）。
        """
        timeout_s = float(check.get("timeout_s", 8))
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                creationflags=_no_window(),
            )
        except FileNotFoundError:
            return self._result(
                check, STATUS_ERROR, f"找不到命令 {argv[0]}，请确认已安装并加入 PATH"
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - started) * 1000
            return self._result(
                check, STATUS_TIMEOUT, f"超时 {timeout_s:g}s 未返回", duration_ms=elapsed
            )
        except OSError as exc:
            return self._result(check, STATUS_ERROR, f"无法启动命令: {exc}")

        elapsed = (time.perf_counter() - started) * 1000
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        text = out or err

        expect = check.get("expect_contains")
        expect_missing = check.get("expect_missing")

        if proc.returncode != 0:
            return self._result(
                check, STATUS_FAIL, err or out or f"返回码 {proc.returncode}",
                value=text, duration_ms=elapsed,
            )
        if expect and expect not in text:
            return self._result(
                check, STATUS_FAIL, f"输出里没有期望的 {expect!r}",
                value=text, duration_ms=elapsed,
            )
        if expect_missing and expect_missing in text:
            return self._result(
                check, STATUS_FAIL, f"输出里出现了不该有的 {expect_missing!r}",
                value=text, duration_ms=elapsed,
            )
        return self._result(check, STATUS_OK, text, value=text, duration_ms=elapsed)

    def _result(
        self,
        check: dict[str, Any],
        status: str,
        detail: str = "",
        value: str = "",
        duration_ms: float = 0.0,
    ) -> ProbeResult:
        return ProbeResult(
            check_id=check["id"],
            channel=self.name,
            status=status,
            value=_clip(value),
            duration_ms=duration_ms,
            detail=_clip(detail),
        )


def _clip(text: str, limit: int = 400) -> str:
    """日志可能很长，截断后再进特征/报告，避免样本文件爆炸。"""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def which(name: str) -> str | None:
    """在 PATH 里找可执行文件。"""
    path = os.environ.get("PATH", "")
    exts = [""]
    if sys.platform == "win32":
        exts = [".exe", ".bat", ".cmd", ""]
    for directory in path.split(os.pathsep):
        if not directory:
            continue
        for ext in exts:
            candidate = os.path.join(directory, name + ext)
            if os.path.isfile(candidate):
                return candidate
    return None
