"""单张图片推理。

真实使用中 90% 的坑在这一步，而不是模型：
  - 手机拍的手写数字是「黑字白底」，MNIST 是「白字黑底」，必须取反；
  - 图片不是 28×28，要缩放并保持居中；
  - 必须用训练时完全相同的归一化参数。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image, ImageOps

from .checkpoint import build_from_checkpoint
from .data import MNIST_MEAN, MNIST_STD


@dataclass
class Prediction:
    label: int
    prob: float
    topk: list[tuple[int, float]]

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "prob": round(self.prob, 4),
            "top3": [(int(l), round(p, 4)) for l, p in self.topk],
        }


class Predictor:
    def __init__(self, checkpoint: str | Path, device: str = "auto"):
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model, self.cfg, self.payload = build_from_checkpoint(checkpoint, device=device)

    # ------------------------------------------------------------------
    def preprocess(self, image: Image.Image, invert: str = "auto") -> torch.Tensor:
        gray = image.convert("L")
        gray = ImageOps.fit(gray, (28, 28), method=Image.LANCZOS)

        # tobytes() 比 getdata() 快，而且没有被 Pillow 标记为弃用
        raw = gray.tobytes()

        should_invert = invert == "yes"
        if invert == "auto":
            # 白底黑字 -> 取反。用平均亮度判断，比要求用户手动指定友好
            should_invert = sum(raw) / len(raw) > 127
        if should_invert:
            gray = ImageOps.invert(gray)

        values = [v / 255.0 for v in gray.tobytes()]
        tensor = torch.tensor(values, dtype=torch.float32).view(1, 1, 28, 28)
        tensor = (tensor - MNIST_MEAN) / MNIST_STD
        return tensor.to(self.device)

    def predict_tensor(self, tensor: torch.Tensor, topk: int = 3) -> Prediction:
        self.model.eval()
        with torch.no_grad():
            logits = self.model(tensor.to(self.device))
            probs = torch.softmax(logits, dim=1)[0]
        values, indices = probs.topk(topk)
        pairs = [(int(i), float(v)) for i, v in zip(indices.tolist(), values.tolist())]
        return Prediction(label=pairs[0][0], prob=pairs[0][1], topk=pairs)

    def predict_image(self, path: str | Path, invert: str = "auto", topk: int = 3) -> Prediction:
        with Image.open(path) as image:
            tensor = self.preprocess(image, invert=invert)
        return self.predict_tensor(tensor, topk=topk)
