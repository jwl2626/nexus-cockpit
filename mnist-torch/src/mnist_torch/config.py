"""配置：一个 dataclass 管住所有超参。

优先级：代码默认值 < JSON 配置文件 < 命令行参数。
这样「实验可复现」和「临时调一下」两件事都不耽误。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, get_type_hints


@dataclass
class Config:
    # ---------------- 数据 ----------------
    data_dir: str = "data"
    batch_size: int = 128
    num_workers: int = 0          # Windows 上建议 0，避免多进程启动开销
    val_size: int = 5000          # 从训练集切出来做验证

    # ---------------- 模型 ----------------
    model: str = "cnn"            # mlp | cnn
    hidden: int = 256
    dropout: float = 0.25

    # ---------------- 训练 ----------------
    epochs: int = 5
    lr: float = 1e-3
    weight_decay: float = 0.0
    optimizer: str = "adam"       # adam | sgd
    momentum: float = 0.9
    scheduler: str = "cosine"     # none | cosine | step
    seed: int = 42
    device: str = "auto"          # auto | cpu | cuda
    amp: bool = True              # 混合精度（仅 CUDA 生效）
    patience: int = 3             # 验证集连续多少轮不涨就早停
    grad_clip: float = 0.0        # >0 时裁剪梯度

    # ---------------- 输出 ----------------
    out_dir: str = "runs"
    run_name: str = "exp"

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        hints = get_type_hints(cls)
        known = {f.name for f in fields(cls)}
        cleaned: dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                continue
            cleaned[key] = _coerce(hints[key], value)
        return cls(**cleaned)

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        with Path(path).open("r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)
        return target

    def update(self, overrides: dict[str, Any]) -> "Config":
        """用命令行参数覆盖当前配置，返回新对象（不改原对象）。"""
        merged = self.to_dict()
        merged.update({k: v for k, v in overrides.items() if v is not None})
        return Config.from_dict(merged)

    def run_dir(self) -> Path:
        path = Path(self.out_dir) / self.run_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_device(self) -> str:
        import torch

        if self.device in {"cpu", "cuda"}:
            return self.device
        return "cuda" if torch.cuda.is_available() else "cpu"


def _coerce(target_type: Any, value: Any) -> Any:
    """把 JSON / 命令行里的字符串转成字段声明的类型。"""
    if value is None:
        return None
    if target_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    if target_type is str:
        return str(value)
    return value
