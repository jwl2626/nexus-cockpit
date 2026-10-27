"""评估指标：混淆矩阵、每类精确率/召回率/F1、Top-K 准确率。

为什么不用现成的库：这几个函数加起来不到 100 行，而且报错时你能立刻定位。
顺便说一句，accuracy 在 MNIST 这种均衡数据集上够用，但在真实业务里
（比如不良品检测）必须看每类指标，否则会被「全判成多数类」骗过去。
"""

from __future__ import annotations

from typing import Sequence


def confusion_matrix(y_true: Sequence[int], y_pred: Sequence[int], num_classes: int) -> list[list[int]]:
    matrix = [[0] * num_classes for _ in range(num_classes)]
    for truth, pred in zip(y_true, y_pred):
        if 0 <= truth < num_classes and 0 <= pred < num_classes:
            matrix[truth][pred] += 1
    return matrix


def per_class_report(matrix: list[list[int]], class_names: Sequence[str]) -> dict[str, dict]:
    report: dict[str, dict] = {}
    for index, name in enumerate(class_names):
        tp = matrix[index][index]
        support = sum(matrix[index])
        predicted = sum(matrix[row][index] for row in range(len(matrix)))
        fn = support - tp
        fp = predicted - tp
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    return report


def accuracy(matrix: list[list[int]]) -> float:
    total = sum(sum(row) for row in matrix)
    if not total:
        return 0.0
    return sum(matrix[i][i] for i in range(len(matrix))) / total


def topk_accuracy(logits, targets, k: int = 3) -> float:
    """Top-K：只要正确答案在前 K 个预测里就算对。"""
    if len(targets) == 0:
        return 0.0
    correct = 0
    for row, target in zip(logits, targets):
        top = sorted(range(len(row)), key=lambda i: float(row[i]), reverse=True)[:k]
        if int(target) in top:
            correct += 1
    return correct / len(targets)


def format_confusion(matrix: list[list[int]], class_names: Sequence[str]) -> str:
    width = max(4, max(len(str(n)) for n in class_names) + 1)
    header = "真实\\预测".ljust(width) + "".join(str(n).rjust(width) for n in class_names)
    lines = [header, "-" * len(header)]
    for index, name in enumerate(class_names):
        lines.append(str(name).ljust(width) + "".join(str(v).rjust(width) for v in matrix[index]))
    return "\n".join(lines)


def format_report(report: dict[str, dict], matrix: list[list[int]]) -> str:
    lines = [
        f"准确率 {accuracy(matrix):.2%}",
        "",
        f"{'数字':<6}{'精确率':>9}{'召回率':>9}{'F1':>9}{'样本':>8}",
        "-" * 42,
    ]
    for name, item in report.items():
        lines.append(
            f"{name:<6}{item['precision']:>9.2%}{item['recall']:>9.2%}"
            f"{item['f1']:>9.2%}{item['support']:>8d}"
        )
    return "\n".join(lines)
