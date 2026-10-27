"""Checkpoint 读写。

存的不只是权重，还有：配置、epoch、最好准确率、类别名。
少了任何一样，半年后你都没法复现这个结果。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

from .config import Config
from .models import build_model


def save_checkpoint(
    path: str | Path,
    *,
    model: nn.Module,
    cfg: Config,
    epoch: int,
    best_acc: float,
    extra: dict[str, Any] | None = None,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_state": model.state_dict(),
        "config": cfg.to_dict(),
        "epoch": epoch,
        "best_acc": best_acc,
        "class_names": [str(i) for i in range(10)],
    }
    if extra:
        payload.update(extra)
    torch.save(payload, target)
    return target


def load_checkpoint(path: str | Path, map_location: str = "cpu") -> dict:
    # weights_only=False：checkpoint 里含 dict/基础类型，且是我们自己写的文件
    try:
        return torch.load(str(path), map_location=map_location, weights_only=False)
    except TypeError:  # torch < 2.0 没有 weights_only 参数
        return torch.load(str(path), map_location=map_location)


def build_from_checkpoint(path: str | Path, device: str = "cpu") -> tuple[nn.Module, Config, dict]:
    """从 checkpoint 还原模型（结构由存进去的 config 决定，不用手填参数）。"""
    payload = load_checkpoint(path, map_location=device)
    cfg = Config.from_dict(payload.get("config", {}))
    model = build_model(cfg.model, hidden=cfg.hidden, dropout=cfg.dropout)
    model.load_state_dict(payload["model_state"])
    model.to(device)
    model.eval()
    return model, cfg, payload
