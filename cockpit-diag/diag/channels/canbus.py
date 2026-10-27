"""CAN 通道：通过周立功 USBCAN 收发报文，做"总线活不活、诊断有没有回"的判断。

座舱诊断里 CAN 的价值不在"发了什么"，而在：
  - 该周期性出现的报文到没到（心跳、状态帧）
  - 诊断请求（UDS，如 3E 00 会话保持、22 F1 90 读 VIN）有没有回 7F / 正响应
  - 帧间隔抖不抖、有没有错误帧

依赖：`pip install python-can`，再装周立功官方驱动 + ZLG 的 CAN 动态库。
python-can 的 zlgcan 后端会去调用 ZLG 的 DLL，驱动没装好会直接报错。
"""

from __future__ import annotations

import time
from typing import Any

from ..types import ProbeResult, STATUS_ERROR, STATUS_FAIL, STATUS_OK, STATUS_TIMEOUT
from .base import Channel


class CanChannel(Channel):
    name = "can"

    def available(self) -> tuple[bool, str]:
        try:
            import can  # noqa: F401
        except ImportError:
            return False, "未安装 python-can（pip install python-can）"
        try:
            import zlgcan  # noqa: F401
        except ImportError:
            # 没有 zlgcan 原生包也还能用 python-can 的 zlgcan 后端，取决于驱动
            return True, "python-can 可用；未检测到 zlgcan 原生包（使用 python-can 后端）"
        return True, "python-can + zlgcan 均可用"

    def run(self, check: dict[str, Any]) -> ProbeResult:
        try:
            import can
        except ImportError:
            return self._result(check, STATUS_ERROR, "未安装 python-can")

        interface = check.get("interface", "zlgcan")
        channel_index = int(check.get("channel", 0))
        bitrate = int(check.get("bitrate", 500000))
        listen_ms = float(check.get("listen_ms", 500))
        expect_ids = {_norm_id(x) for x in check.get("expect_ids", [])}
        timeout_s = float(check.get("timeout_s", 5))

        kwargs: dict[str, Any] = {
            "interface": interface,
            "channel": channel_index,
            "bitrate": bitrate,
        }
        for key in ("device", "port", "index", "fd", "receive_own_messages"):
            if key in check:
                kwargs[key] = check[key]

        started = time.perf_counter()
        bus = None
        try:
            bus = can.Bus(**kwargs)
        except Exception as exc:  # 驱动/DLL 问题都在这里暴露
            elapsed = (time.perf_counter() - started) * 1000
            return self._result(
                check, STATUS_ERROR, f"打开 CAN 通道失败: {exc}", duration_ms=elapsed
            )

        try:
            for frame in check.get("send", []):
                msg = can.Message(
                    arbitration_id=int(str(frame["id"]), 0),
                    data=bytes.fromhex(str(frame.get("data", "")).replace(" ", "")),
                    is_extended_id=bool(frame.get("extended", True)),
                )
                bus.send(msg)

            seen: set[int] = set()
            frames: list[Any] = []
            deadline = time.monotonic() + listen_ms / 1000
            while time.monotonic() < deadline:
                remaining = max(0.0, deadline - time.monotonic())
                msg = bus.recv(timeout=min(remaining, 0.1))
                if msg is None or msg.is_error_frame:
                    continue
                frames.append(msg)
                seen.add(int(msg.arbitration_id))
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return self._result(check, STATUS_ERROR, f"CAN 收发异常: {exc}", duration_ms=elapsed)
        finally:
            try:
                bus.shutdown()
            except Exception:
                pass

        elapsed = (time.perf_counter() - started) * 1000
        summary = f"{len(frames)} 帧 / {len(seen)} 个 ID"

        if not frames:
            return self._result(
                check, STATUS_TIMEOUT, f"{listen_ms:g}ms 内没有收到任何报文（总线静默/没接/波特率不对）",
                duration_ms=elapsed,
            )
        if expect_ids:
            missing = expect_ids - seen
            if missing:
                names = ", ".join(f"0x{i:X}" for i in sorted(missing))
                return self._result(
                    check, STATUS_FAIL, f"缺少期望报文: {names}（{summary}）",
                    value=summary, duration_ms=elapsed,
                )
        return self._result(check, STATUS_OK, summary, value=summary, duration_ms=elapsed)


def _norm_id(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 0)
