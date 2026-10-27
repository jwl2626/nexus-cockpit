"""规则引擎。

规则的价值：模型没见过的情况，规则还能兜底；产线质疑问"凭什么判坏"时，
规则给出的是一句人话，而不是一个概率。

条件语法（JSON 里写）：
    {"check": "can.heartbeat", "status": ["timeout", "fail"], "min_duration_ms": 1000}
所有条件都满足才算命中。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import Sample

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "checks" / "rules.json"


@dataclass
class RuleHit:
    rule_id: str
    vote: str
    weight: float
    message: str
    advice: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "vote": self.vote,
            "weight": self.weight,
            "message": self.message,
            "advice": self.advice,
        }


def load_rules(path: str | Path | None = None) -> list[dict[str, Any]]:
    target = Path(path) if path else DEFAULT_PATH
    if not target.is_file():
        return []
    with target.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data.get("rules", []))


def evaluate(sample: Sample, rules: list[dict[str, Any]]) -> list[RuleHit]:
    by_id = {r.check_id: r for r in sample.results}
    hits: list[RuleHit] = []

    for rule in rules:
        conditions = rule.get("when") or []
        if not conditions:
            continue
        if all(_match(by_id, cond) for cond in conditions):
            hits.append(
                RuleHit(
                    rule_id=rule["id"],
                    vote=rule.get("vote", "UNKNOWN"),
                    weight=float(rule.get("weight", 1.0)),
                    message=rule.get("message", rule["id"]),
                    advice=list(rule.get("advice") or []),
                )
            )
    return sorted(hits, key=lambda h: h.weight, reverse=True)


def _match(by_id: dict, cond: dict[str, Any]) -> bool:
    result = by_id.get(cond["check"])
    if result is None:
        return False
    statuses = cond.get("status")
    if statuses and result.status not in statuses:
        return False
    min_ms = cond.get("min_duration_ms")
    if min_ms is not None and result.duration_ms < float(min_ms):
        return False
    return True
