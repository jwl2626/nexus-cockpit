"""可视化：把样本和「判错的样本」拼成一张图存下来。

不依赖 matplotlib，只用 Pillow（torchvision 已经带了它）。
判错的样本图特别值得看——MNIST 上错的那 0.7%，基本是「人写得太像另一个数」，
你看一眼就知道模型是不是真的傻。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image

from .data import MNIST_MEAN, MNIST_STD


def _to_image(tensor, denormalize: bool = True, scale: int = 3) -> Image.Image:
    """把一个 (1,28,28) 或 (28,28) 张量转成放大的灰度图（不依赖 numpy）。"""
    data = tensor.detach().cpu()
    if data.dim() == 3:
        data = data[0]
    values = data.flatten().tolist()
    if denormalize:
        values = [v * MNIST_STD + MNIST_MEAN for v in values]
    pixels = bytes(max(0, min(255, int(round(v * 255)))) for v in values)
    image = Image.frombytes("L", (28, 28), pixels)
    if scale > 1:
        image = image.resize((28 * scale, 28 * scale), Image.NEAREST)
    return image


def save_grid(
    tensors: Sequence,
    path: str | Path,
    *,
    ncols: int = 8,
    scale: int = 3,
    title_marks: Sequence[str] | None = None,
) -> Path:
    tiles = [_to_image(t, scale=scale) for t in list(tensors)[: ncols * 8]]
    if not tiles:
        raise ValueError("没有可保存的图像")

    tile_w, tile_h = tiles[0].size
    ncols = min(ncols, len(tiles))
    nrows = (len(tiles) + ncols - 1) // ncols

    canvas = Image.new("L", (tile_w * ncols, tile_h * nrows), color=0)
    for index, tile in enumerate(tiles):
        row, col = divmod(index, ncols)
        canvas.paste(tile, (col * tile_w, row * tile_h))

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)
    return target


def save_misclassified(
    images,
    targets: Iterable[int],
    preds: Iterable[int],
    path: str | Path,
    *,
    limit: int = 32,
    scale: int = 3,
) -> Path | None:
    picked = []
    for image, truth, pred in zip(images, targets, preds):
        if int(truth) != int(pred):
            picked.append(image)
        if len(picked) >= limit:
            break
    if not picked:
        return None
    return save_grid(picked, path, ncols=8, scale=scale)
