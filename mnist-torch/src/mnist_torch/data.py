"""数据：MNIST 数据集、数据增强、DataLoader，以及无数据时的合成数据。

工程里最容易出问题的不是模型，是数据管道。这里有三个刻意的设计：

  1. 训练集和验证集用「两份 MNIST 实例」切分 —— 因为 torchvision 的 transform
     是绑在 Dataset 上的，用 Subset 切分会让验证集也带上数据增强。
  2. 切分用带种子的 randperm —— 保证每次运行的验证集完全相同。
  3. 数据下载失败时给出人话提示，而不是抛一个 URLError。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset, Subset, TensorDataset
from torchvision import datasets, transforms

from .config import Config

MNIST_MEAN = 0.1307
MNIST_STD = 0.3081

# torchvision 默认从 AWS 下载；国内网络常常不通。手动下载后放到这个目录即可：
RAW_NAMES = (
    "train-images-idx3-ubyte.gz",
    "train-labels-idx1-ubyte.gz",
    "t10k-images-idx3-ubyte.gz",
    "t10k-labels-idx1-ubyte.gz",
)


class DataError(RuntimeError):
    """数据相关的、可以给用户看懂的异常。"""


def build_transform(train: bool = False) -> transforms.Compose:
    ops: list = [transforms.ToTensor()]
    if train:
        # 轻微仿射：模拟「写得歪一点、大一点」，是提升泛化最便宜的手段
        ops.append(
            transforms.RandomAffine(degrees=8, translate=(0.06, 0.06), scale=(0.94, 1.06))
        )
    ops.append(transforms.Normalize((MNIST_MEAN,), (MNIST_STD,)))
    return transforms.Compose(ops)


@dataclass
class DataBundle:
    train: Dataset
    val: Dataset
    test: Dataset
    class_names: list[str]

    def loaders(self, cfg: Config) -> dict[str, DataLoader]:
        pin = cfg.resolve_device() == "cuda"
        common = dict(batch_size=cfg.batch_size, num_workers=cfg.num_workers, pin_memory=pin)
        return {
            "train": DataLoader(self.train, shuffle=True, drop_last=False, **common),
            "val": DataLoader(self.val, shuffle=False, **common),
            "test": DataLoader(self.test, shuffle=False, **common),
        }

    def summary(self) -> str:
        return (
            f"train={len(self.train)}  val={len(self.val)}  test={len(self.test)}  "
            f"classes={len(self.class_names)}"
        )


def build_data(cfg: Config) -> DataBundle:
    root = Path(cfg.data_dir)
    train_tf = build_transform(train=True)
    eval_tf = build_transform(train=False)

    full_aug = _mnist(root, train=True, transform=train_tf)
    full_plain = _mnist(root, train=True, transform=eval_tf)
    test_ds = _mnist(root, train=False, transform=eval_tf)

    if not 0 <= cfg.val_size < len(full_aug):
        raise DataError(f"val_size={cfg.val_size} 不合理，应在 0 到 {len(full_aug)} 之间")

    generator = torch.Generator().manual_seed(cfg.seed)
    perm = torch.randperm(len(full_aug), generator=generator)
    val_idx = perm[: cfg.val_size].tolist()
    train_idx = perm[cfg.val_size :].tolist()

    return DataBundle(
        train=Subset(full_aug, train_idx),
        val=Subset(full_plain, val_idx),
        test=test_ds,
        class_names=[str(i) for i in range(10)],
    )


def _mnist(root: Path, *, train: bool, transform) -> datasets.MNIST:
    try:
        return datasets.MNIST(root=str(root), train=train, download=True, transform=transform)
    except Exception as exc:  # noqa: BLE001 - 网络/文件问题都要翻译成人话
        raise DataError(_download_hint(root, exc)) from exc


def _download_hint(root: Path, exc: Exception) -> str:
    raw = root / "MNIST" / "raw"
    listing = "\n".join(f"    {raw / name}" for name in RAW_NAMES)
    return (
        f"MNIST 数据不可用：{exc}\n\n"
        f"torchvision 默认从 AWS 下载，国内网络经常被墙。两种解决办法：\n\n"
        f"  A. 手动下载下面 4 个文件，放到 {raw}\n"
        f"{listing}\n"
        f"     下载地址（任一镜像）：\n"
        f"       https://ossci-datasets.s3.amazonaws.com/mnist/\n"
        f"       https://huggingface.co/datasets/ylecun/mnist （需转换格式）\n\n"
        f"  B. 先跑自检，不依赖数据验证工程链路：\n"
        f"       python -m mnist_torch.cli smoke\n"
    )


# ----------------------------------------------------------------------
# 无网络/无数据时的自检数据：形状与真实 MNIST 完全一致，只是内容是随机的。
# 它的作用是验证「训练循环 / 评估 / 保存 / 导出」这条链路能跑通，不代表任何精度。
# ----------------------------------------------------------------------
def build_synthetic(cfg: Config, *, n_train: int = 512, n_val: int = 128, n_test: int = 128) -> DataBundle:
    generator = torch.Generator().manual_seed(cfg.seed)

    def make(n: int) -> TensorDataset:
        images = torch.randn(n, 1, 28, 28, generator=generator) * 0.3
        labels = torch.randint(0, 10, (n,), generator=generator)
        return TensorDataset(images, labels)

    return DataBundle(
        train=make(n_train),
        val=make(n_val),
        test=make(n_test),
        class_names=[str(i) for i in range(10)],
    )
