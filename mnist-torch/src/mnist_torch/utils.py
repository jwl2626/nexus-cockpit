"""通用工具：随机种子、日志、计时。"""

from __future__ import annotations

import logging
import os
import random
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def seed_everything(seed: int = 42) -> None:
    """把能固定的随机源全固定住，保证「同样的命令跑出同样的结果」。"""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        # 这两行会让训练变慢，但换来完全可复现（cuDNN 的某些算法不确定）
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass


def get_logger(name: str = "mnist", log_file: str | Path | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    return logger


def configure_stdio() -> None:
    """Windows 控制台默认 GBK，中文会乱码，这里强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


@contextmanager
def timer() -> Iterator[dict]:
    box: dict = {"seconds": 0.0}
    started = time.perf_counter()
    try:
        yield box
    finally:
        box["seconds"] = time.perf_counter() - started


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes)}m{rest:.0f}s"


def human_int(value: int) -> str:
    return f"{value:,}"
