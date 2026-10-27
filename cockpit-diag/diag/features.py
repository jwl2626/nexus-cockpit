"""特征化：把一台机的诊断记录变成模型能吃的固定长度向量。

这是"手搓"里最关键、也最容易被低估的一步。MNIST 的输入天生就是 28x28 数字，
而你的原始数据是"变长的、多通道的、带文字的记录"，必须先翻译成数字。

这里用的编码（你可以直接背下来）：
  1. 每个检查项 × 5 种结局  -> one-hot   (N * 5 维)
  2. 全局各结局出现比例                  (5 维)
  3. 每个通道的"平均耗时"和"失败率"       (C * 2 维)

为什么要 3：两个通道都返回 fail 时，耗时 200ms 和 5000ms 的含义完全不同，
前者是"业务失败"，后者往往是链路卡死。
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from .checks import channels_in, check_ids as spec_check_ids
from .types import STATUSES, STATUS_OK, STATUS_SKIPPED, ProbeResult, Sample

MAX_DURATION_MS = 30_000.0


class FeatureSpace:
    """定义"第几列代表什么"，保证训练和推理时列顺序完全一致。"""

    def __init__(self, check_ids: Iterable[str], channels: Iterable[str]):
        self.check_ids = list(check_ids)
        self.channels = list(channels)
        self._status_index = {s: i for i, s in enumerate(STATUSES)}
        self._check_index = {c: i for i, c in enumerate(self.check_ids)}

    # ------------------------------------------------------------------
    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "FeatureSpace":
        return cls(spec_check_ids(spec), channels_in(spec))

    @property
    def dim(self) -> int:
        return len(self.check_ids) * len(STATUSES) + len(STATUSES) + 2 * len(self.channels)

    def names(self) -> list[str]:
        """每一列的人类可读名字，用来解释模型权重。"""
        names: list[str] = []
        for cid in self.check_ids:
            for status in STATUSES:
                names.append(f"{cid}={status}")
        for status in STATUSES:
            names.append(f"全局:{status}比例")
        for channel in self.channels:
            names.append(f"{channel}:平均耗时(s)")
            names.append(f"{channel}:失败率")
        return names

    # ------------------------------------------------------------------
    def vector(self, sample: Sample) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float64)
        by_id = {r.check_id: r for r in sample.results}
        cursor = 0

        counts = {status: 0 for status in STATUSES}
        for cid in self.check_ids:
            result = by_id.get(cid)
            status = result.status if result else STATUS_SKIPPED
            if status not in self._status_index:
                status = STATUS_SKIPPED
            vec[cursor + self._status_index[status]] = 1.0
            counts[status] += 1
            cursor += len(STATUSES)

        total = max(1, len(self.check_ids))
        for status in STATUSES:
            vec[cursor] = counts[status] / total
            cursor += 1

        for channel in self.channels:
            results = [r for r in sample.results if r.channel == channel]
            if results:
                durations = [min(max(r.duration_ms, 0.0), MAX_DURATION_MS) / 1000.0 for r in results]
                vec[cursor] = float(np.mean(durations))
                failures = sum(1 for r in results if r.status != STATUS_OK)
                vec[cursor + 1] = failures / len(results)
            cursor += 2

        return vec

    def matrix(self, samples: Iterable[Sample]) -> np.ndarray:
        rows = [self.vector(s) for s in samples]
        if not rows:
            return np.zeros((0, self.dim), dtype=np.float64)
        return np.vstack(rows)

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {"check_ids": self.check_ids, "channels": self.channels}

    @classmethod
    def from_dict(cls, obj: dict[str, Any]) -> "FeatureSpace":
        return cls(obj["check_ids"], obj["channels"])

    def __repr__(self) -> str:
        return f"FeatureSpace(checks={len(self.check_ids)}, channels={self.channels}, dim={self.dim})"


def single_result(sample: Sample, check_id: str) -> ProbeResult | None:
    for result in sample.results:
        if result.check_id == check_id:
            return result
    return None
