"""命令行入口。

    python -m mnist_torch.cli train --config configs/cnn.json
    python -m mnist_torch.cli smoke
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .checkpoint import build_from_checkpoint
from .config import Config
from .data import DataError, build_data, build_synthetic
from .engine import evaluate, fit
from .export import export_torchscript, verify_export
from .metrics import confusion_matrix, format_confusion, format_report, per_class_report
from .models import describe_model
from .predict import Predictor
from .utils import configure_stdio, get_logger, seed_everything


# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mnist-torch",
        description="完整的 PyTorch MNIST 工程：训练 / 评估 / 推理 / 导出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python -m mnist_torch.cli smoke\n"
            "  python -m mnist_torch.cli train --config configs/cnn.json --epochs 5\n"
            "  python -m mnist_torch.cli eval --checkpoint runs/exp/best.pt\n"
            "  python -m mnist_torch.cli predict --checkpoint runs/exp/best.pt --image 3.png\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"mnist-torch {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser("train", help="训练模型")
    _add_common(train)
    train.add_argument("--optimizer", choices=["adam", "sgd"], default=None)
    train.add_argument("--scheduler", choices=["none", "cosine", "step"], default=None)
    train.add_argument("--patience", type=int, default=None)
    train.add_argument("--model", choices=["mlp", "cnn"], default=None)

    ev = sub.add_parser("eval", help="在测试集上评估")
    ev.add_argument("--checkpoint", required=True)
    ev.add_argument("--data-dir", default=None)
    ev.add_argument("--batch-size", type=int, default=None)
    ev.add_argument("--device", default=None)
    ev.add_argument("--misclassified", default=None, help="把判错的样本拼图保存到该路径")

    pred = sub.add_parser("predict", help="单张图片推理")
    pred.add_argument("--checkpoint", required=True)
    pred.add_argument("--image", required=True)
    pred.add_argument("--device", default=None)
    pred.add_argument("--invert", choices=["auto", "yes", "no"], default="auto")

    exp = sub.add_parser("export", help="导出 TorchScript")
    exp.add_argument("--checkpoint", required=True)
    exp.add_argument("--out", default="model.pt")
    exp.add_argument("--device", default="cpu")

    smoke = sub.add_parser("smoke", help="无数据自检：随机张量跑通全流程")
    smoke.add_argument("--device", default="cpu")
    smoke.add_argument("--epochs", type=int, default=2)

    sub.add_parser("info", help="环境信息")
    return parser


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=None, help="JSON 配置文件")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--hidden", type=int, default=None)
    parser.add_argument("--dropout", type=float, default=None)
    parser.add_argument("--val-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=None)


# ----------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = build_parser().parse_args(argv)

    try:
        if args.command == "train":
            return _cmd_train(args)
        if args.command == "eval":
            return _cmd_eval(args)
        if args.command == "predict":
            return _cmd_predict(args)
        if args.command == "export":
            return _cmd_export(args)
        if args.command == "smoke":
            return _cmd_smoke(args)
        if args.command == "info":
            return _cmd_info()
    except DataError as exc:
        print(f"\n[数据错误]\n{exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"\n[文件不存在] {exc}", file=sys.stderr)
        return 2

    return 2


# ----------------------------------------------------------------------
def _cmd_train(args) -> int:
    cfg = _load_cfg(args)
    run_dir = cfg.run_dir()
    logger = get_logger("mnist", run_dir / "train.log")

    seed_everything(cfg.seed)
    logger.info(f"mnist-torch {__version__} | run={cfg.run_name} | seed={cfg.seed}")
    cfg.save(run_dir / "config.json")

    bundle = build_data(cfg)
    loaders = bundle.loaders(cfg)
    logger.info(bundle.summary())

    history = fit(cfg, loaders, run_dir, logger)
    (run_dir / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _report_test(run_dir / "best.pt", loaders["test"], cfg, logger, run_dir)
    logger.info(f"产物目录：{run_dir}")
    return 0


def _cmd_eval(args) -> int:
    device = args.device or ("cuda" if _cuda_ok() else "cpu")
    model, cfg, payload = build_from_checkpoint(args.checkpoint, device=device)
    if args.data_dir:
        cfg.data_dir = args.data_dir
    if args.batch_size:
        cfg.batch_size = args.batch_size

    logger = get_logger("mnist")
    logger.info(f"checkpoint epoch={payload.get('epoch')} best_val={payload.get('best_acc', 0):.2%}")
    logger.info(describe_model(model))

    bundle = build_data(cfg)
    loaders = bundle.loaders(cfg)
    _report_test(
        args.checkpoint, loaders["test"], cfg, logger, None,
        misclassified_path=args.misclassified,
    )
    return 0


def _cmd_predict(args) -> int:
    predictor = Predictor(args.checkpoint, device=args.device or "auto")
    prediction = predictor.predict_image(args.image, invert=args.invert)
    print(f"文件     : {args.image}")
    print(f"判定     : {prediction.label}   (置信度 {prediction.prob:.2%})")
    print("Top-3    : " + "  ".join(f"{l} {p:.1%}" for l, p in prediction.topk))
    return 0


def _cmd_export(args) -> int:
    device = args.device
    model, cfg, payload = build_from_checkpoint(args.checkpoint, device=device)
    path = export_torchscript(model, args.out, device=device)
    diff = verify_export(path, model, device=device)
    print(f"已导出 {path}  ({path.stat().st_size / 1024:.0f} KB)")
    print(f"校验通过：与原模型最大误差 {diff:.2e}")
    return 0 if diff < 1e-4 else 1


def _cmd_smoke(args) -> int:
    """无数据自检：用随机张量走完 训练 -> 评估 -> 存盘 -> 导出 -> 推理。"""
    cfg = Config(
        model="cnn",
        epochs=args.epochs,
        batch_size=32,
        lr=1e-3,
        amp=False,
        scheduler="none",
        patience=0,
        device=args.device,
        out_dir="runs",
        run_name="smoke",
        num_workers=0,
    )
    run_dir = cfg.run_dir()
    logger = get_logger("smoke", run_dir / "smoke.log")
    seed_everything(cfg.seed)

    print("=" * 60)
    print("SMOKE TEST：随机张量，只验证工程链路，不代表任何精度")
    print("=" * 60)

    bundle = build_synthetic(cfg, n_train=256, n_val=64, n_test=64)
    loaders = bundle.loaders(cfg)
    logger.info(bundle.summary())

    history = fit(cfg, loaders, run_dir, logger)
    assert (run_dir / "best.pt").is_file(), "best.pt 没生成"

    _report_test(run_dir / "best.pt", loaders["test"], cfg, logger, run_dir, compact=True)

    model, _, _ = build_from_checkpoint(run_dir / "best.pt", device=cfg.device)
    export_path = export_torchscript(model, run_dir / "model.pt", device=cfg.device)
    diff = verify_export(export_path, model, device=cfg.device)
    logger.info(f"TorchScript 导出校验：最大误差 {diff:.2e}")
    assert diff < 1e-4, "导出后的模型输出不一致"

    predictor = Predictor(run_dir / "best.pt", device=cfg.device)
    import torch

    pred = predictor.predict_tensor(torch.zeros(1, 1, 28, 28))
    logger.info(f"推理链路：随机输入 -> {pred.label} ({pred.prob:.2%})")

    print("\nSMOKE OK —— 训练/评估/保存/导出/推理 全链路通过")
    return 0


def _cmd_info() -> int:
    import torch
    import torchvision

    print(f"mnist-torch {__version__}")
    print(f"Python      {platform.python_version()}  ({platform.platform()})")
    print(f"PyTorch     {torch.__version__}")
    print(f"torchvision {torchvision.__version__}")
    print(f"CUDA 可用   {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU         {torch.cuda.get_device_name(0)}")
        print(f"显存        {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    return 0


# ----------------------------------------------------------------------
def _report_test(checkpoint, test_loader, cfg: Config, logger, run_dir: Path | None,
                 misclassified_path: str | None = None, compact: bool = False) -> dict:
    """在测试集上评估最优模型，打印并保存混淆矩阵与每类指标。"""
    import torch.nn as nn

    device = cfg.resolve_device()
    model, _, payload = build_from_checkpoint(checkpoint, device=device)
    result = evaluate(model, test_loader, nn.CrossEntropyLoss(), device)
    matrix = confusion_matrix(result["targets"], result["preds"], 10)
    report = per_class_report(matrix, [str(i) for i in range(10)])

    if compact:
        # 自检用的是随机数据，逐类指标没有意义，只会制造噪音
        logger.info(f"测试集准确率 {result['acc']:.2%}（随机数据，仅验证链路，不代表精度）")
        return {"acc": result["acc"], "matrix": matrix, "report": report}

    text = "\n".join([
        "",
        "=" * 60,
        f"测试集评估  checkpoint={Path(checkpoint).name}  "
        f"(epoch {payload.get('epoch')}, val {payload.get('best_acc', 0):.2%})",
        "=" * 60,
        format_report(report, matrix),
        "",
        "混淆矩阵（行=真实，列=预测）",
        format_confusion(matrix, [str(i) for i in range(10)]),
        "",
    ])
    logger.info(text)

    if run_dir is not None:
        (run_dir / "report.txt").write_text(text, encoding="utf-8")
        target = run_dir / "misclassified.png"
    elif misclassified_path:
        target = Path(misclassified_path)
    else:
        target = None

    if target is not None:
        saved = _save_misclassified(test_loader, result["preds"], target)
        logger.info(f"判错样本拼图 -> {saved}" if saved else "没有判错的样本")

    return {"acc": result["acc"], "matrix": matrix, "report": report}


def _save_misclassified(loader, preds: list[int], path: Path, limit: int = 32) -> Path | None:
    from .visualize import save_grid

    collected = []
    index = 0
    for images, labels in loader:
        for i in range(images.size(0)):
            if index >= len(preds):
                break
            if int(preds[index]) != int(labels[i]):
                collected.append(images[i])
                if len(collected) >= limit:
                    break
            index += 1
        if len(collected) >= limit:
            break
    if not collected:
        return None
    return save_grid(collected, path, ncols=8)


def _load_cfg(args) -> Config:
    cfg = Config.load(args.config) if getattr(args, "config", None) else Config()
    overrides: dict[str, Any] = {
        key: getattr(args, key, None)
        for key in (
            "data_dir", "epochs", "batch_size", "lr", "hidden", "dropout",
            "val_size", "seed", "device", "run_name", "out_dir", "amp",
            "optimizer", "scheduler", "patience", "model",
        )
    }
    return cfg.update(overrides)


def _cuda_ok() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
