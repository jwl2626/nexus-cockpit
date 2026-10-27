"""合成数据：在没有真实不良机之前，先把整条训练/评估流水线跑通。

为什么值得做：你现在没有几十台坏机，但你需要先验证"特征定义对不对、
评估指标看什么、代码通不通"。合成数据能把这三件事先做掉，
等真实数据到了，只换数据源，流程一行不改。

它故意模拟了真实世界的四个特点：
  1. 类别极不平衡（不良率远低于正常）；
  2. 同一类故障表现不完全一样（概率性失败，不是每次都一样）；
  3. 存在"噪音失败"（好机偶尔也有检查项失败）；
  4. 耗时分布可分（超时 5~8s，正常失败 100~300ms）。
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .checks import load_checks
from .types import STATUS_FAIL, STATUS_OK, STATUS_TIMEOUT, ProbeResult, Sample

CLASSES = ["OK", "DISPLAY", "AUDIO", "CAN", "ETH", "SYS"]

# 真实产线上不良率通常在 2%~10%；这里放大到 45% 是为了让模型有足够样本可学。
PRIOR = {
    "OK": 0.55,
    "DISPLAY": 0.10,
    "AUDIO": 0.12,
    "CAN": 0.10,
    "ETH": 0.08,
    "SYS": 0.05,
}

# 每类故障"典型"打在哪些检查项上，以及打中的概率。
PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "OK": {},
    "DISPLAY": {
        "adb.display": {"p": 0.88, "statuses": [STATUS_FAIL, STATUS_TIMEOUT], "w": [0.85, 0.15]},
        "adb.crash_log": {"p": 0.35, "statuses": [STATUS_FAIL], "w": [1.0]},
    },
    "AUDIO": {
        "adb.audio": {"p": 0.88, "statuses": [STATUS_FAIL, STATUS_TIMEOUT], "w": [0.85, 0.15]},
        "adb.crash_log": {"p": 0.25, "statuses": [STATUS_FAIL], "w": [1.0]},
    },
    "CAN": {
        "can.heartbeat": {"p": 0.90, "statuses": [STATUS_TIMEOUT, STATUS_FAIL], "w": [0.7, 0.3]},
        "can.uds_session": {"p": 0.85, "statuses": [STATUS_TIMEOUT, STATUS_FAIL], "w": [0.6, 0.4]},
    },
    "ETH": {
        "eth.gateway_ping": {"p": 0.88, "statuses": [STATUS_FAIL, STATUS_TIMEOUT], "w": [0.8, 0.2]},
        "eth.doip_udp": {"p": 0.90, "statuses": [STATUS_TIMEOUT], "w": [1.0]},
        "eth.hmi_service": {"p": 0.60, "statuses": [STATUS_FAIL, STATUS_TIMEOUT], "w": [0.7, 0.3]},
    },
    "SYS": {
        "adb.get_state": {"p": 0.60, "statuses": [STATUS_TIMEOUT, STATUS_FAIL], "w": [0.8, 0.2]},
        "adb.boot_completed": {"p": 0.88, "statuses": [STATUS_FAIL], "w": [1.0]},
        "adb.storage": {"p": 0.45, "statuses": [STATUS_FAIL], "w": [1.0]},
    },
}

NOISE_RATE = 0.03


def generate(
    spec: dict[str, Any] | None = None,
    n: int = 1200,
    seed: int = 7,
) -> list[Sample]:
    spec = spec or load_checks()
    rng = random.Random(seed)
    checks = spec["checks"]
    classes = list(PRIOR.keys())
    weights = [PRIOR[c] for c in classes]

    samples: list[Sample] = []
    for index in range(n):
        label = rng.choices(classes, weights=weights, k=1)[0]
        results = [_make_result(rng, check, label) for check in checks]
        samples.append(
            Sample(
                unit_id=f"SYN-{index:05d}",
                label=label,
                results=results,
                meta={"source": "synthetic", "batch": f"B{index // 100:02d}"},
            )
        )
    return samples


def _make_result(rng: random.Random, check: dict[str, Any], label: str) -> ProbeResult:
    profile = PROFILES.get(label, {}).get(check["id"])
    status = STATUS_OK

    if profile and rng.random() < profile["p"]:
        status = rng.choices(profile["statuses"], weights=profile["w"], k=1)[0]
    elif rng.random() < NOISE_RATE:
        status = rng.choices([STATUS_FAIL, STATUS_TIMEOUT], weights=[0.8, 0.2], k=1)[0]

    duration = _duration(rng, status)
    detail = {
        STATUS_OK: "ok",
        STATUS_FAIL: "返回值/内容不符合预期",
        STATUS_TIMEOUT: "等待响应超时",
    }[status]
    return ProbeResult(
        check_id=check["id"],
        channel=check["channel"],
        status=status,
        duration_ms=duration,
        detail=detail,
    )


def _duration(rng: random.Random, status: str) -> float:
    if status == STATUS_TIMEOUT:
        return rng.uniform(5_000, 8_000)
    if status == STATUS_FAIL:
        return rng.uniform(100, 300)
    return rng.uniform(60, 220)


# ----------------------------------------------------------------------
def save(samples: list[Sample], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump([s.as_dict() for s in samples], fh, ensure_ascii=False, indent=1)
    return target


def load(path: str | Path) -> list[Sample]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return [Sample.from_dict(obj) for obj in json.load(fh)]
