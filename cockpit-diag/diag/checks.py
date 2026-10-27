"""检查项定义与加载。

检查项清单是整个系统的"源头活水"：你以后把真实指令给我，改的就是这个文件，
训练代码、特征代码都不用动。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "checks" / "cockpit.json"

KNOWN_CHANNELS = {"adb", "fastboot", "can", "ethernet"}


class CheckSpecError(ValueError):
    pass


def load_checks(path: str | Path | None = None) -> dict[str, Any]:
    """读取检查项配置文件并做基本校验。"""
    target = Path(path) if path else DEFAULT_PATH
    if not target.is_file():
        raise CheckSpecError(f"找不到检查项文件: {target}")
    with target.open("r", encoding="utf-8") as fh:
        spec = json.load(fh)
    validate(spec)
    return spec


def validate(spec: dict[str, Any]) -> None:
    checks = spec.get("checks")
    if not isinstance(checks, list) or not checks:
        raise CheckSpecError("配置里必须有非空的 checks 列表")

    seen: set[str] = set()
    for index, check in enumerate(checks):
        cid = check.get("id")
        if not cid:
            raise CheckSpecError(f"第 {index} 个检查项缺少 id")
        if cid in seen:
            raise CheckSpecError(f"检查项 id 重复: {cid}")
        seen.add(cid)
        channel = check.get("channel")
        if channel not in KNOWN_CHANNELS:
            raise CheckSpecError(f"{cid}: 未知通道 {channel!r}，可选 {sorted(KNOWN_CHANNELS)}")


def channel_config(spec: dict[str, Any]) -> dict[str, Any]:
    return spec.get("channels") or {}


def check_ids(spec: dict[str, Any]) -> list[str]:
    return [c["id"] for c in spec["checks"]]


def channels_in(spec: dict[str, Any]) -> list[str]:
    """按出现顺序返回用到的通道，保证特征列顺序稳定。"""
    result: list[str] = []
    for check in spec["checks"]:
        if check["channel"] not in result:
            result.append(check["channel"])
    return result
