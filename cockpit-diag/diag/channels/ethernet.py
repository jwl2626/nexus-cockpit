"""以太网通道：ping / TCP 连通性 / UDP 探测。

座舱的以太网常见用途：DoIP 诊断（UDP 13400）、SOME/IP 服务、车内网关互通、
以及车机对外上网。诊断要看的是：通不通、丢不丢包、RTT 抖不抖、端口开不开。
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
from typing import Any

from ..types import ProbeResult, STATUS_ERROR, STATUS_FAIL, STATUS_OK, STATUS_TIMEOUT
from .base import Channel, _no_window


class EthernetChannel(Channel):
    name = "ethernet"

    def run(self, check: dict[str, Any]) -> ProbeResult:
        mode = check.get("mode", "tcp")
        if mode == "ping":
            return self._ping(check)
        if mode == "tcp":
            return self._tcp(check)
        if mode == "udp":
            return self._udp(check)
        return self._result(check, STATUS_ERROR, f"不支持的 mode: {mode}")

    # ------------------------------------------------------------------
    def _ping(self, check: dict[str, Any]) -> ProbeResult:
        target = check["target"]
        count = int(check.get("count", 4))
        timeout_ms = int(check.get("timeout_ms", 1000))
        argv = ["ping", target, "-n" if sys.platform == "win32" else "-c", str(count)]
        if sys.platform == "win32":
            argv += ["-w", str(timeout_ms)]

        started = time.perf_counter()
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=float(check.get("timeout_s", 30)),
                creationflags=_no_window(),
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - started) * 1000
            return self._result(check, STATUS_TIMEOUT, "ping 整体超时", duration_ms=elapsed)
        except OSError as exc:
            return self._result(check, STATUS_ERROR, f"无法执行 ping: {exc}")

        elapsed = (time.perf_counter() - started) * 1000
        text = (proc.stdout or "") + (proc.stderr or "")
        loss = _parse_loss(text)
        rtt = _parse_rtt(text)

        if proc.returncode != 0 or (loss is not None and loss >= 100):
            return self._result(
                check, STATUS_FAIL, "完全不通" if loss is None else f"丢包 {loss:.0f}%",
                value=_one_line(text), duration_ms=elapsed,
            )

        max_loss = float(check.get("max_loss_pct", 20))
        if loss is not None and loss > max_loss:
            return self._result(
                check, STATUS_FAIL, f"丢包 {loss:.0f}% 超过阈值 {max_loss:g}%",
                value=_one_line(text), duration_ms=elapsed,
            )
        detail = f"丢包 {loss:.0f}%" if loss is not None else "可达"
        if rtt is not None:
            detail += f"，RTT≈{rtt:.0f}ms"
        return self._result(check, STATUS_OK, detail, value=_one_line(text), duration_ms=elapsed)

    # ------------------------------------------------------------------
    def _tcp(self, check: dict[str, Any]) -> ProbeResult:
        target = check["target"]
        port = int(check["port"])
        timeout_s = float(check.get("timeout_s", 3))
        started = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        try:
            sock.connect((target, port))
        except socket.timeout:
            elapsed = (time.perf_counter() - started) * 1000
            return self._result(
                check, STATUS_TIMEOUT, f"连接 {target}:{port} 超时 {timeout_s:g}s",
                duration_ms=elapsed,
            )
        except OSError as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return self._result(
                check, STATUS_FAIL, f"连接 {target}:{port} 失败: {exc}", duration_ms=elapsed
            )
        finally:
            try:
                sock.close()
            except OSError:
                pass

        elapsed = (time.perf_counter() - started) * 1000
        max_ms = float(check.get("max_ms", 1500))
        if elapsed > max_ms:
            return self._result(
                check, STATUS_FAIL, f"握手 {elapsed:.0f}ms 超过 {max_ms:g}ms",
                value=f"{elapsed:.1f}ms", duration_ms=elapsed,
            )
        return self._result(
            check, STATUS_OK, f"TCP {target}:{port} 连通，{elapsed:.0f}ms",
            value=f"{elapsed:.1f}ms", duration_ms=elapsed,
        )

    # ------------------------------------------------------------------
    def _udp(self, check: dict[str, Any]) -> ProbeResult:
        """发一个探测包并等回包；适合 DoIP/SOME/IP 这类"有请求才有响应"的服务。"""
        target = check["target"]
        port = int(check["port"])
        payload = bytes.fromhex(str(check.get("payload_hex", "")).replace(" ", ""))
        timeout_s = float(check.get("timeout_s", 2))
        expect_reply = bool(check.get("expect_reply", True))

        started = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout_s)
        try:
            sock.sendto(payload, (target, port))
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            elapsed = (time.perf_counter() - started) * 1000
            status = STATUS_TIMEOUT if expect_reply else STATUS_OK
            return self._result(
                check, status, f"UDP {target}:{port} 无响应（{timeout_s:g}s）",
                duration_ms=elapsed,
            )
        except OSError as exc:
            return self._result(check, STATUS_FAIL, f"UDP 发送失败: {exc}")
        finally:
            try:
                sock.close()
            except OSError:
                pass

        elapsed = (time.perf_counter() - started) * 1000
        return self._result(
            check, STATUS_OK, f"UDP 回包 {len(data)} 字节，{elapsed:.0f}ms",
            value=data[:64].hex(), duration_ms=elapsed,
        )


def _parse_loss(text: str) -> float | None:
    match = re.search(r"(\d+)%\s*(?:loss|丢失)", text)
    if match:
        return float(match.group(1))
    match = re.search(r"Lost\s*=\s*(\d+)", text)
    if match:
        return float(match.group(1))
    return None


def _parse_rtt(text: str) -> float | None:
    match = re.search(r"(?:Average|平均)\s*=\s*(\d+)\s*ms", text)
    if match:
        return float(match.group(1))
    times = re.findall(r"time[=<]\s*(\d+)\s*ms", text)
    if times:
        return sum(float(t) for t in times) / len(times)
    return None


def _one_line(text: str, limit: int = 200) -> str:
    line = " ".join(text.split())
    return line[:limit]
