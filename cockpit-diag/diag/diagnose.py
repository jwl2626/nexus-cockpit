"""诊断决策：规则 + 模型融合，并生成"为什么"和"下一步"。

融合方式（刻意做得简单，方便你以后改）：
    最终分数 = (1-α)·模型概率 + α·规则归一化得分
α 默认 0.35。规则是"硬证据"，模型是"整体像不像"，两者都强时结论最可信；
只有一边有信号时，另一边会把结果往中间拉，避免过度自信。
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .features import FeatureSpace
from .model import SoftmaxRegression
from .rules import RuleHit, evaluate, load_rules
from .types import Diagnosis, Sample

RULE_ALPHA = 0.35

DEFAULT_ADVICE = {
    "OK": ["无异常。如需提高置信度，可间隔 10 分钟复测一次。"],
    "DISPLAY": ["查屏线与背光供电", "导出 dumpsys display / SurfaceFlinger 日志"],
    "AUDIO": ["查功放供电与扬声器线束", "导出 dumpsys audio"],
    "CAN": ["查 CAN 线束、终端电阻与波特率", "用 CAN 分析仪抓 200ms 原始帧"],
    "ETH": ["查网线/连接器与 IP 配置", "抓包看 ARP / DoIP 是否发出"],
    "SYS": ["导出 logcat、dmesg 与最近 OTA 记录", "检查分区校验与启动耗时"],
    "UNKNOWN": ["证据不足，建议人工复核并补充一次采集"],
}


class Diagnoser:
    def __init__(
        self,
        model: SoftmaxRegression | None = None,
        space: FeatureSpace | None = None,
        rules: Sequence[dict[str, Any]] | None = None,
        alpha: float = RULE_ALPHA,
    ):
        self.model = model
        self.space = space
        self.rules = list(rules) if rules is not None else load_rules()
        self.alpha = alpha
        self.classes = list(model.classes_) if model is not None else ["OK", "DISPLAY", "AUDIO", "CAN", "ETH", "SYS"]

    # ------------------------------------------------------------------
    def diagnose(self, sample: Sample) -> Diagnosis:
        hits = evaluate(sample, self.rules)
        probs = self._model_probs(sample)
        scores = self._fuse(probs, hits)

        if not scores:
            return Diagnosis(
                unit_id=sample.unit_id,
                verdict="UNKNOWN",
                is_abnormal=False,
                confidence=0.0,
                ranking=[],
                reasons=["没有规则命中，也没有可用模型"],
                next_steps=DEFAULT_ADVICE["UNKNOWN"],
            )

        ranking = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        verdict, top_score = ranking[0]
        reasons = self._reasons(sample, verdict, hits, probs)
        steps = self._next_steps(verdict, hits)

        return Diagnosis(
            unit_id=sample.unit_id,
            verdict=verdict,
            is_abnormal=verdict != "OK",
            confidence=float(top_score),
            ranking=ranking,
            reasons=reasons,
            next_steps=steps,
        )

    # ------------------------------------------------------------------
    def _model_probs(self, sample: Sample) -> dict[str, float]:
        if self.model is None or self.space is None:
            return {}
        vector = self.space.vector(sample).reshape(1, -1)
        proba = self.model.predict_proba(vector)[0]
        return {cls: float(p) for cls, p in zip(self.model.classes_, proba)}

    def _fuse(self, probs: dict[str, float], hits: list[RuleHit]) -> dict[str, float]:
        rule_raw: dict[str, float] = {}
        for hit in hits:
            rule_raw[hit.vote] = rule_raw.get(hit.vote, 0.0) + hit.weight

        rule_norm: dict[str, float] = {}
        if rule_raw:
            peak = max(rule_raw.values())
            rule_norm = {k: v / peak for k, v in rule_raw.items()}

        classes = set(probs) | set(rule_norm)
        scores: dict[str, float] = {}
        for cls in classes:
            model_part = probs.get(cls, 0.0)
            rule_part = rule_norm.get(cls, 0.0)
            if not probs:
                scores[cls] = rule_part
            elif not rule_norm:
                scores[cls] = model_part
            else:
                scores[cls] = (1 - self.alpha) * model_part + self.alpha * rule_part

        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}
        return scores

    # ------------------------------------------------------------------
    def _reasons(
        self,
        sample: Sample,
        verdict: str,
        hits: list[RuleHit],
        probs: dict[str, float],
    ) -> list[str]:
        reasons: list[str] = []
        for hit in hits:
            if hit.vote == verdict:
                reasons.append(f"[规则] {hit.message}")

        if self.model is not None and self.space is not None:
            vector = self.space.vector(sample)
            std = self.model.std_
            x_std = (vector - self.model.mean_) / std
            cls_index = self.model.classes_.index(verdict) if verdict in self.model.classes_ else None
            if cls_index is not None:
                contrib = x_std * self.model.W_[:, cls_index]
                names = self.space.names()
                order = np.argsort(contrib)[::-1][:3]
                for idx in order:
                    if contrib[idx] <= 0.05:
                        continue
                    reasons.append(f"[模型] {names[idx]} 贡献 {contrib[idx]:+.2f}")
            if probs:
                reasons.append(f"[模型] 总体判为 {verdict} 的概率 {probs.get(verdict, 0.0):.1%}")

        if not reasons:
            reasons.append("无强信号，属于低置信度判定")
        return reasons[:6]

    def _next_steps(self, verdict: str, hits: list[RuleHit]) -> list[str]:
        steps: list[str] = []
        for hit in hits:
            if hit.vote == verdict:
                for item in hit.advice:
                    if item not in steps:
                        steps.append(item)
        if not steps:
            steps = list(DEFAULT_ADVICE.get(verdict, DEFAULT_ADVICE["UNKNOWN"]))
        return steps[:5]
