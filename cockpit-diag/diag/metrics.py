"""评估指标。

产线上只看 accuracy 会被坑死：不良率 5% 时，全判"正常"也能有 95% 准确率，
但一条坏机都抓不到。所以这里把三个指标拆开看：

    accuracy        整体准确率 —— 只用来横向比较模型
    漏检率(miss)    真实不良被判成 OK 的比例 —— 最贵的错误，越低越好
    误报率(false)   好机被判成不良的比例 —— 次要错误，高了产线会骂人
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def confusion_matrix(y_true: Sequence[str], y_pred: Sequence[str], classes: Sequence[str]) -> np.ndarray:
    index = {c: i for i, c in enumerate(classes)}
    cm = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for truth, pred in zip(y_true, y_pred):
        cm[index[truth], index[pred]] += 1
    return cm


def report(y_true: Sequence[str], y_pred: Sequence[str], classes: Sequence[str]) -> dict:
    cm = confusion_matrix(y_true, y_pred, classes)
    per_class = {}
    for i, name in enumerate(classes):
        tp = int(cm[i, i])
        fn = int(cm[i, :].sum() - tp)
        fp = int(cm[:, i].sum() - tp)
        support = int(cm[i, :].sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    total = int(cm.sum())
    accuracy = float(np.trace(cm) / total) if total else 0.0

    ok_index = classes.index("OK") if "OK" in classes else None
    if ok_index is not None:
        bad_true = total - int(cm[ok_index, :].sum())
        bad_missed = int(cm[:, ok_index].sum() - cm[ok_index, ok_index])
        miss_rate = bad_missed / bad_true if bad_true else 0.0
        good_true = int(cm[ok_index, :].sum())
        false_alarm = int(cm[ok_index, :].sum() - cm[ok_index, ok_index])
        false_alarm_rate = false_alarm / good_true if good_true else 0.0
    else:
        miss_rate = float("nan")
        false_alarm_rate = float("nan")

    return {
        "accuracy": round(accuracy, 4),
        "miss_rate": round(miss_rate, 4),
        "false_alarm_rate": round(false_alarm_rate, 4),
        "per_class": per_class,
        "support": total,
    }


def format_confusion(cm: np.ndarray, classes: Sequence[str]) -> str:
    width = max(len(c) for c in classes) + 2
    header = "真实\\预测".ljust(width) + "".join(c.rjust(width) for c in classes)
    lines = [header, "-" * len(header)]
    for i, name in enumerate(classes):
        row = name.ljust(width) + "".join(str(int(v)).rjust(width) for v in cm[i])
        lines.append(row)
    return "\n".join(lines)


def format_report(rep: dict) -> str:
    lines = [
        f"样本 {rep['support']}  准确率 {rep['accuracy']:.1%}  "
        f"漏检率 {rep['miss_rate']:.1%}  误报率 {rep['false_alarm_rate']:.1%}",
        "",
        f"{'类别':<10}{'精确率':>8}{'召回率':>8}{'F1':>8}{'样本':>8}",
        "-" * 42,
    ]
    for name, item in rep["per_class"].items():
        lines.append(
            f"{name:<10}{item['precision']:>8.1%}{item['recall']:>8.1%}"
            f"{item['f1']:>8.1%}{item['support']:>8d}"
        )
    return "\n".join(lines)
