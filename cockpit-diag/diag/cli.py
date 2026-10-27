"""命令行入口。

    python -m diag.cli demo        # 合成数据 -> 训练 -> 评估 -> 出一份报告（先跑这个）
    python -m diag.cli probe       # 对真机跑一遍检查项，存成样本
    python -m diag.cli train       # 用你自己的样本训练
    python -m diag.cli diagnose    # 对一条样本出诊断结论
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np

from . import __version__, synth
from .checks import load_checks
from .diagnose import Diagnoser
from .features import FeatureSpace
from .metrics import confusion_matrix, format_confusion, format_report, report
from .model import SoftmaxRegression
from .probe import probe
from .rules import load_rules
from .types import Sample

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diag",
        description="座舱智能诊断（教学版）：ADB / Fastboot / CAN / 以太网",
    )
    parser.add_argument("--version", action="version", version=f"cockpit-diag {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="用合成数据跑通完整训练与评估流程")
    demo.add_argument("--n", type=int, default=1200, help="合成样本数")
    demo.add_argument("--epochs", type=int, default=300)
    demo.add_argument("--seed", type=int, default=7)

    train = sub.add_parser("train", help="用真实样本训练")
    train.add_argument("--data", required=True, help="样本 JSON（probe 產出的格式）")
    train.add_argument("--out", default=str(MODEL_DIR / "diag.npz"))
    train.add_argument("--epochs", type=int, default=400)

    probe_cmd = sub.add_parser("probe", help="对已连接的车机跑一遍检查项")
    probe_cmd.add_argument("--out", default=str(DATA_DIR / "latest.json"))
    probe_cmd.add_argument("--unit", default=None, help="车机编号")
    probe_cmd.add_argument("--label", default=None, help="已知故障类别（采集时就能打标签）")
    probe_cmd.add_argument("--only", default=None, help="只跑指定检查项，逗号分隔")
    probe_cmd.add_argument("--checks", default=None, help="检查项清单路径")

    diag = sub.add_parser("diagnose", help="对一条样本出诊断结论")
    diag.add_argument("--sample", required=True, help="样本 JSON")
    diag.add_argument("--model", default=str(MODEL_DIR / "diag.npz"))
    diag.add_argument("--json", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)

    if args.command == "demo":
        return _cmd_demo(args)
    if args.command == "train":
        return _cmd_train(args)
    if args.command == "probe":
        return _cmd_probe(args)
    if args.command == "diagnose":
        return _cmd_diagnose(args)
    return 2


# ----------------------------------------------------------------------
def _cmd_demo(args) -> int:
    spec = load_checks()
    space = FeatureSpace.from_spec(spec)
    print(f"检查项 {len(space.check_ids)} 个，通道 {space.channels}，特征 {space.dim} 维\n")
    print(f"[1/5] 生成合成数据 n={args.n} …")
    samples = synth.generate(spec, n=args.n, seed=args.seed)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    synth.save(samples, DATA_DIR / "synthetic.json")

    train_set, test_set = _split_by_batch(samples)
    print(f"      训练 {len(train_set)} / 测试 {len(test_set)}（按批次切分，避免同批泄漏）")
    print(f"      类别分布: {_class_counts(samples)}")

    print("\n[2/5] 训练 softmax 回归 …")
    X_train = space.matrix(train_set)
    y_train = [s.label for s in train_set]
    model = SoftmaxRegression(
        epochs=args.epochs, lr=0.08, l2=1e-3, verbose=True, log_every=max(1, args.epochs // 6)
    )
    model.fit(X_train, y_train)

    print("\n[3/5] 在测试批次上评估 …")
    X_test = space.matrix(test_set)
    y_test = [s.label for s in test_set]
    y_pred = model.predict(X_test)
    rep = report(y_test, y_pred, model.classes_)
    cm = confusion_matrix(y_test, y_pred, model.classes_)

    print()
    print(format_report(rep))
    print()
    print(format_confusion(cm, model.classes_))

    print("\n[4/5] 每类最关键的证据（线性模型的白盒收益）")
    importance = model.feature_importance(space.names(), top_k=3)
    for cls, items in importance.items():
        positives = [(n, w) for n, w in items if w > 0][:3]
        text = "，".join(f"{n} {w:+.2f}" for n, w in positives) or "—"
        print(f"  {cls:<8} {text}")

    print("\n[5/5] 保存模型并演示单机诊断")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "diag.npz"
    model.save(model_path, schema=space.to_dict())
    print(f"      模型 -> {_rel(model_path)}")

    diagnoser = Diagnoser(model=model, space=space, rules=load_rules())
    for sample in test_set[:3]:
        _print_diagnosis(diagnoser.diagnose(sample), truth=sample.label)

    _write_demo_report(rep, cm, model.classes_, importance, model, space)
    print(f"\n报告 -> {_rel(REPORT_DIR / 'demo-report.md')}")
    print("\n完成。下一步：把真实指令填进 checks/cockpit.json，然后用 probe 采真实样本。")
    return 0


def _cmd_train(args) -> int:
    spec = load_checks()
    space = FeatureSpace.from_spec(spec)
    samples = _load_samples(args.data)
    labeled = [s for s in samples if s.label]
    if len(labeled) < 20:
        print(f"带标签的样本只有 {len(labeled)} 条，先多采一些（建议每类 ≥ 30 条）。", file=sys.stderr)
        return 1

    print(f"样本 {len(labeled)} 条，特征 {space.dim} 维，类别 {_class_counts(labeled)}")
    model = SoftmaxRegression(epochs=args.epochs, verbose=True, log_every=max(1, args.epochs // 6))
    model.fit(space.matrix(labeled), [s.label for s in labeled])

    out = Path(args.out)
    model.save(out, schema=space.to_dict())
    print(f"\n已保存 -> {out}")
    return 0


def _cmd_probe(args) -> int:
    spec = load_checks(args.checks)
    only = [x.strip() for x in args.only.split(",")] if args.only else None

    def show(result):
        mark = {"ok": "OK  ", "fail": "FAIL", "timeout": "SLOW", "error": "ERR ", "skipped": "SKIP"}[
            result.status
        ]
        print(f"  [{mark}] {result.check_id:<20} {result.duration_ms:7.0f}ms  {result.detail[:70]}")

    sample = probe(spec, unit_id=args.unit, label=args.label, only=only, on_result=show)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump([sample.as_dict()], fh, ensure_ascii=False, indent=1)
    print(f"\n样本已保存 -> {out}")
    print(f"通道状态: {json.dumps(sample.meta.get('channels', {}), ensure_ascii=False)}")
    return 0


def _cmd_diagnose(args) -> int:
    samples = _load_samples(args.sample)
    if not samples:
        print("样本文件是空的", file=sys.stderr)
        return 1

    model_path = Path(args.model)
    model = None
    space = None
    if model_path.is_file():
        model = SoftmaxRegression.load(model_path)
        space = FeatureSpace.from_dict(SoftmaxRegression.load_schema(model_path))
    else:
        print(f"提示: 没找到模型 {model_path}，只用规则判定", file=sys.stderr)

    diagnoser = Diagnoser(model=model, space=space, rules=load_rules())
    results = [diagnoser.diagnose(s) for s in samples]

    if args.json:
        print(json.dumps([r.as_dict() for r in results], ensure_ascii=False, indent=2))
        return 0

    by_unit = {s.unit_id: s for s in samples}
    for diag in results:
        _print_diagnosis(diag, truth=by_unit[diag.unit_id].label)
    return 0


# ----------------------------------------------------------------------
def _split_by_batch(samples: list[Sample]) -> tuple[list[Sample], list[Sample]]:
    train, test = [], []
    for sample in samples:
        batch = str(sample.meta.get("batch", "B00"))
        number = int("".join(ch for ch in batch if ch.isdigit()) or 0)
        (test if number >= 10 else train).append(sample)
    if not test:
        cut = max(1, int(len(samples) * 0.8))
        return samples[:cut], samples[cut:]
    return train, test


def _class_counts(samples: Sequence[Sample]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        key = sample.label or "未标注"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def _load_samples(path: str | Path) -> list[Sample]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = [data]
    return [Sample.from_dict(obj) for obj in data]


def _print_diagnosis(diag, truth: str | None = None) -> None:
    tag = "" if truth is None else f"  真实={truth}"
    verdict = diag.verdict
    alert = "不良" if diag.is_abnormal else "正常"
    print(f"\n  {diag.unit_id}  判定={verdict}（{alert}）置信度 {diag.confidence:.1%}{tag}")
    print("  可能性: " + "  ".join(f"{c} {p:.0%}" for c, p in diag.ranking[:3]))
    for reason in diag.reasons[:4]:
        print(f"    · {reason}")
    for step in diag.next_steps[:3]:
        print(f"    -> {step}")


def _write_demo_report(rep, cm, classes, importance, model, space) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 训练演示报告",
        "",
        f"- 检查项：{len(space.check_ids)} 个；特征维度：{space.dim}",
        f"- 通道：{', '.join(space.channels)}",
        f"- 训练轮数：{model.epochs}；最终训练 loss：{model.history_[-1]:.4f}",
        "",
        "## 评估结果",
        "",
        "```text",
        format_report(rep),
        "```",
        "",
        "## 混淆矩阵",
        "",
        "```text",
        format_confusion(cm, classes),
        "```",
        "",
        "## 每类关键证据（权重）",
        "",
    ]
    for cls, items in importance.items():
        positives = [(n, w) for n, w in items if w > 0][:3]
        text = "，".join(f"`{n}` {w:+.2f}" for n, w in positives) or "—"
        lines.append(f"- **{cls}**：{text}")

    lines += [
        "",
        "## 怎么读这份报告",
        "",
        "- `漏检率` 是真实不良被判成 OK 的比例。**这是最贵的错误**，优先把它压下去。",
        "- `误报率` 是好机被判成不良的比例。高了产线会抱怨，但比漏检便宜。",
        "- 混淆矩阵里如果 `CAN` 和 `ETH` 互相串，说明这两类的特征还不够区分，",
        "  要加更有针对性的检查项（例如 CAN 只查总线、ETH 只查端口）。",
        "",
    ]
    (REPORT_DIR / "demo-report.md").write_text("\n".join(lines), encoding="utf-8")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
