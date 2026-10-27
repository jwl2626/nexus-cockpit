"""采集器：按检查项清单跑一遍，产出一个 Sample。

设计要点：
  - 通道不可用时整条通道记 skipped，而不是逐条报 error —— 否则"没插 CAN 卡"
    会被模型学成"故障"，这是新手最容易踩的坑（特征泄漏）。
  - 单条检查项崩了不影响整机采集。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Iterable

from .channels import build_channels
from .checks import channels_in, load_checks
from .types import ProbeResult, Sample, STATUS_SKIPPED


def probe(
    spec: dict[str, Any] | None = None,
    *,
    unit_id: str | None = None,
    label: str | None = None,
    only: Iterable[str] | None = None,
    on_result: Callable[[ProbeResult], None] | None = None,
) -> Sample:
    """对一台车机跑完整检查。"""
    spec = spec or load_checks()
    checks = list(spec["checks"])
    if only:
        wanted = set(only)
        checks = [c for c in checks if c["id"] in wanted]

    channels = build_channels(spec.get("channels"))
    available: dict[str, tuple[bool, str]] = {}
    for name in channels_in(spec):
        if name not in channels:
            available[name] = (False, "未知通道")
            continue
        try:
            available[name] = channels[name].available()
        except Exception as exc:  # 通道自检本身也可能炸
            available[name] = (False, f"自检失败: {exc}")

    results: list[ProbeResult] = []
    started = time.perf_counter()

    for check in checks:
        channel_name = check["channel"]
        ok, reason = available.get(channel_name, (False, "未知通道"))
        if not ok:
            result = ProbeResult(
                check_id=check["id"],
                channel=channel_name,
                status=STATUS_SKIPPED,
                detail=f"通道不可用: {reason}",
            )
        else:
            try:
                result = channels[channel_name].run(check)
            except Exception as exc:
                result = ProbeResult(
                    check_id=check["id"],
                    channel=channel_name,
                    status="error",
                    detail=f"检查项异常: {exc}",
                )
        results.append(result)
        if on_result:
            on_result(result)

    unit_id = unit_id or f"unit-{uuid.uuid4().hex[:8]}"
    return Sample(
        unit_id=unit_id,
        label=label,
        results=results,
        meta={
            "taken_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "elapsed_s": round(time.perf_counter() - started, 2),
            "channels": {name: {"available": v[0], "reason": v[1]} for name, v in available.items()},
        },
    )
