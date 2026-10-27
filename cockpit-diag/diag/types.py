"""统一的数据类型。

一台车机的诊断过程 = 跑一串"检查项" -> 每个检查项产出一个 ProbeResult
-> 所有结果打包成一个 Sample -> Sample 特征化成向量 -> 模型/规则给结论。

这个文件只放结构，不放逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# 一个检查项只有这 5 种结局。把"失败"拆成 fail / timeout / error 很重要：
# 超时通常意味着链路或对方进程卡死，和"命令执行了但结果不对"是两种故障。
STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_TIMEOUT = "timeout"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

STATUSES = (STATUS_OK, STATUS_FAIL, STATUS_TIMEOUT, STATUS_ERROR, STATUS_SKIPPED)


@dataclass
class ProbeResult:
    """一个检查项的执行结果。"""

    check_id: str
    channel: str
    status: str
    value: str = ""
    duration_ms: float = 0.0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "channel": self.channel,
            "status": self.status,
            "value": self.value,
            "duration_ms": round(self.duration_ms, 1),
            "detail": self.detail,
        }


@dataclass
class Sample:
    """一台车机的一次完整诊断记录。这就是"一行训练数据"的前身。"""

    unit_id: str
    results: list[ProbeResult] = field(default_factory=list)
    label: Optional[str] = None       # 人工确认的故障类别；只有带标签的样本能用来训练
    meta: dict[str, Any] = field(default_factory=dict)  # 固件版本、批次、工位、日期等

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "label": self.label,
            "meta": self.meta,
            "results": [r.as_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, obj: dict[str, Any]) -> "Sample":
        return cls(
            unit_id=obj["unit_id"],
            label=obj.get("label"),
            meta=obj.get("meta") or {},
            results=[
                ProbeResult(
                    check_id=r["check_id"],
                    channel=r["channel"],
                    status=r["status"],
                    value=r.get("value", ""),
                    duration_ms=float(r.get("duration_ms", 0.0)),
                    detail=r.get("detail", ""),
                )
                for r in obj.get("results", [])
            ],
        )


@dataclass
class Diagnosis:
    """给一台机的最终结论。"""

    unit_id: str
    verdict: str                      # 判定的故障类别
    is_abnormal: bool
    confidence: float
    ranking: list[tuple[str, float]]  # [(类别, 概率)] 降序
    reasons: list[str] = field(default_factory=list)   # 为什么这么判
    next_steps: list[str] = field(default_factory=list)  # 建议下一步查什么

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "verdict": self.verdict,
            "is_abnormal": self.is_abnormal,
            "confidence": round(self.confidence, 4),
            "ranking": [(c, round(p, 4)) for c, p in self.ranking],
            "reasons": self.reasons,
            "next_steps": self.next_steps,
        }
