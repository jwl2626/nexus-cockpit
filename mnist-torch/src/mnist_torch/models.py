"""模型：MLP 和一个小 CNN，用注册表按名字取。

刻意只放两个：一个是「最朴素的基线」，一个是「够用的小卷积」。
工程上的经验是——先把基线跑通，再换复杂模型，否则出错分不清是模型问题还是数据问题。
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

NUM_CLASSES = 10


class MLP(nn.Module):
    """784 -> hidden -> 10。MNIST 上大约 97~98%。"""

    def __init__(self, hidden: int = 256, dropout: float = 0.25):
        super().__init__()
        self.fc1 = nn.Linear(28 * 28, hidden)
        self.drop = nn.Dropout(dropout)
        self.fc2 = nn.Linear(hidden, NUM_CLASSES)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.flatten(1)
        x = self.drop(F.relu(self.fc1(x)))
        return self.fc2(x)


class SmallCNN(nn.Module):
    """两层卷积 + 两层全连接。MNIST 上大约 99.0~99.3%。"""

    def __init__(self, hidden: int = 128, dropout: float = 0.25):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2)
        self.drop = nn.Dropout(dropout)
        self.fc1 = nn.Linear(64 * 7 * 7, hidden)
        self.fc2 = nn.Linear(hidden, NUM_CLASSES)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(F.relu(self.conv1(x)))   # 32x14x14
        x = self.pool(F.relu(self.conv2(x)))   # 64x7x7
        x = x.flatten(1)
        x = self.drop(F.relu(self.fc1(x)))
        return self.fc2(x)


MODELS: dict[str, type[nn.Module]] = {"mlp": MLP, "cnn": SmallCNN}


def build_model(name: str, *, hidden: int = 256, dropout: float = 0.25) -> nn.Module:
    key = name.lower()
    if key not in MODELS:
        raise ValueError(f"未知模型 {name!r}，可选 {sorted(MODELS)}")
    return MODELS[key](hidden=hidden, dropout=dropout)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def describe_model(model: nn.Module) -> str:
    return f"{type(model).__name__}  参数量 {count_parameters(model):,}"
