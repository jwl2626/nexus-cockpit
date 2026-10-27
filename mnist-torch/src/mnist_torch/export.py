"""模型导出：TorchScript。

导出的意义：脱离训练代码也能跑（C++ / 移动端 / 服务端），而且能验证
「模型只依赖输入张量」——如果你 forward 里藏了全局状态，这里会立刻暴露。
"""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn


def export_torchscript(
    model: nn.Module,
    path: str | Path,
    *,
    example: torch.Tensor | None = None,
    device: str = "cpu",
) -> Path:
    model = model.to(device).eval()
    if example is None:
        example = torch.zeros(1, 1, 28, 28, device=device)

    with torch.no_grad():
        scripted = torch.jit.trace(model, example)

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    scripted.save(str(target))
    return target


def verify_export(
    path: str | Path,
    model: nn.Module,
    *,
    example: torch.Tensor | None = None,
    device: str = "cpu",
) -> float:
    """加载导出文件并与原模型对比，返回最大绝对误差。"""
    if example is None:
        example = torch.zeros(1, 1, 28, 28, device=device)
    loaded = torch.jit.load(str(path), map_location=device)
    loaded.eval()
    model = model.to(device).eval()
    with torch.no_grad():
        diff = (loaded(example) - model(example)).abs().max().item()
    return float(diff)
