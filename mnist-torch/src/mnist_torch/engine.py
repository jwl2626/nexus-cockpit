"""训练与评估循环。

一个「完整工程」和一段教学代码的差别，几乎全在这个文件里：
  - 训练/验证分离，按验证集选最优，而不是按训练集
  - 学习率调度、梯度裁剪、混合精度
  - 早停
  - 每轮都存 checkpoint（断电可续）
  - 返回结构化 history，方便以后画曲线
"""

from __future__ import annotations

import time
from contextlib import nullcontext
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from .checkpoint import save_checkpoint
from .config import Config
from .models import describe_model, build_model
from .utils import format_duration

MAX_LOSS = 1e9


def _autocast(use_amp: bool):
    if not use_amp:
        return nullcontext()
    try:
        return torch.autocast(device_type="cuda", dtype=torch.float16)
    except Exception:  # 老版本 torch
        return nullcontext()


def _make_scaler(use_amp: bool):
    try:
        return torch.amp.GradScaler("cuda", enabled=use_amp)
    except Exception:
        try:
            return torch.cuda.amp.GradScaler(enabled=use_amp)
        except Exception:
            return None


def build_optimizer(cfg: Config, model: nn.Module) -> torch.optim.Optimizer:
    if cfg.optimizer.lower() == "sgd":
        return torch.optim.SGD(
            model.parameters(), lr=cfg.lr, momentum=cfg.momentum, weight_decay=cfg.weight_decay
        )
    return torch.optim.Adam(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)


def build_scheduler(cfg: Config, optimizer: torch.optim.Optimizer):
    name = cfg.scheduler.lower()
    if name == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, cfg.epochs))
    if name == "step":
        return torch.optim.lr_scheduler.StepLR(optimizer, step_size=max(1, cfg.epochs // 3), gamma=0.5)
    return None


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, criterion, device: str) -> dict:
    """在一份数据上跑一遍，返回 loss / 准确率 / 逐样本预测。"""
    model.eval()
    total_loss = 0.0
    total = 0
    correct = 0
    preds: list[int] = []
    targets: list[int] = []

    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        logits = model(images)
        loss = criterion(logits, labels)

        total_loss += float(loss.item()) * labels.size(0)
        total += labels.size(0)
        batch_preds = logits.argmax(dim=1)
        correct += int((batch_preds == labels).sum().item())
        preds.extend(batch_preds.detach().cpu().tolist())
        targets.extend(labels.detach().cpu().tolist())

    return {
        "loss": total_loss / total if total else MAX_LOSS,
        "acc": correct / total if total else 0.0,
        "preds": preds,
        "targets": targets,
    }


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion,
    device: str,
    *,
    scaler=None,
    use_amp: bool = False,
    grad_clip: float = 0.0,
) -> dict:
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    started = time.perf_counter()

    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        with _autocast(use_amp):
            logits = model(images)
            loss = criterion(logits, labels)

        if scaler is not None and use_amp:
            scaler.scale(loss).backward()
            if grad_clip > 0:
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            if grad_clip > 0:
                nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()

        total_loss += float(loss.item()) * labels.size(0)
        total += labels.size(0)
        correct += int((logits.argmax(dim=1) == labels).sum().item())

    return {
        "loss": total_loss / total if total else MAX_LOSS,
        "acc": correct / total if total else 0.0,
        "seconds": time.perf_counter() - started,
    }


def fit(
    cfg: Config,
    loaders: dict[str, DataLoader],
    run_dir: Path,
    logger,
    *,
    model: nn.Module | None = None,
) -> dict:
    """完整训练流程，返回 history。"""
    device = cfg.resolve_device()
    model = model or build_model(cfg.model, hidden=cfg.hidden, dropout=cfg.dropout)
    model.to(device)

    logger.info(f"设备 {device}" + (f"（{torch.cuda.get_device_name(0)}）" if device == "cuda" else ""))
    logger.info(describe_model(model))
    logger.info(
        f"训练配置 model={cfg.model} epochs={cfg.epochs} lr={cfg.lr:g} "
        f"bs={cfg.batch_size} opt={cfg.optimizer} sched={cfg.scheduler}"
    )

    criterion = nn.CrossEntropyLoss()
    optimizer = build_optimizer(cfg, model)
    scheduler = build_scheduler(cfg, optimizer)
    use_amp = cfg.amp and device == "cuda"
    scaler = _make_scaler(use_amp) if use_amp else None
    if use_amp:
        logger.info("已开启混合精度 (AMP)")

    history: dict[str, list] = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    best_acc = -1.0
    best_epoch = 0
    bad_epochs = 0
    started = time.perf_counter()

    for epoch in range(1, cfg.epochs + 1):
        train_metrics = train_one_epoch(
            model, loaders["train"], optimizer, criterion, device,
            scaler=scaler, use_amp=use_amp, grad_clip=cfg.grad_clip,
        )
        val_metrics = evaluate(model, loaders["val"], criterion, device)
        if scheduler is not None:
            scheduler.step()

        history["train_loss"].append(train_metrics["loss"])
        history["train_acc"].append(train_metrics["acc"])
        history["val_loss"].append(val_metrics["loss"])
        history["val_acc"].append(val_metrics["acc"])

        improved = val_metrics["acc"] > best_acc
        marker = "  ★ best" if improved else ""
        lr_now = optimizer.param_groups[0]["lr"]
        logger.info(
            f"epoch {epoch:>2}/{cfg.epochs}  "
            f"train loss={train_metrics['loss']:.4f} acc={train_metrics['acc']:.2%}  |  "
            f"val loss={val_metrics['loss']:.4f} acc={val_metrics['acc']:.2%}  "
            f"lr={lr_now:.2e}  {format_duration(train_metrics['seconds'])}{marker}"
        )

        if improved:
            best_acc = val_metrics["acc"]
            best_epoch = epoch
            bad_epochs = 0
            save_checkpoint(
                run_dir / "best.pt",
                model=model,
                cfg=cfg,
                epoch=epoch,
                best_acc=best_acc,
                extra={"val_loss": val_metrics["loss"]},
            )
        else:
            bad_epochs += 1
            if cfg.patience > 0 and bad_epochs >= cfg.patience:
                logger.info(f"验证集 {cfg.patience} 轮没提升，早停（最好 epoch={best_epoch}）")
                break

        save_checkpoint(run_dir / "last.pt", model=model, cfg=cfg, epoch=epoch, best_acc=best_acc)

    total_seconds = time.perf_counter() - started
    history["best_acc"] = best_acc
    history["best_epoch"] = best_epoch
    history["seconds"] = total_seconds
    logger.info(
        f"训练完成：最好验证准确率 {best_acc:.2%}（epoch {best_epoch}），"
        f"总耗时 {format_duration(total_seconds)}"
    )
    return history
