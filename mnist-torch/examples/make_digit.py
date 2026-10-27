"""生成一张测试用的数字图片（七段数码管风格）。

用途：没有 MNIST 数据时，也能验证 predict 这条链路是通的。
注意：这是"印刷体"，不是手写体，用 MNIST 训出来的模型认它可能不准——
      这个脚本验证的是「图片 -> 张量 -> 推理」的管道，不是模型精度。

    python examples/make_digit.py examples/digit7.png 7
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

# 七段数码管：a 上横 / b 右上 / c 右下 / d 下横 / e 左下 / f 左上 / g 中横
SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}

WIDTH, MARGIN, THICK = 10, 6, 4


def draw_digit(digit: str, size: int = 28) -> Image.Image:
    scale = size / 28
    w, m, t = WIDTH * scale, MARGIN * scale, THICK * scale
    height = w * 2 + m * 2
    canvas = Image.new("L", (int(w + m * 2), int(height)), color=0)
    draw = ImageDraw.Draw(canvas)

    left, right = m, m + w
    top, mid, bottom = m, m + w, m + w * 2
    segs = {
        "a": (left, top, right, top),
        "b": (right, top, right, mid),
        "c": (right, mid, right, bottom),
        "d": (left, bottom, right, bottom),
        "e": (left, mid, left, bottom),
        "f": (left, top, left, mid),
        "g": (left, mid, right, mid),
    }
    for name in SEGMENTS.get(digit, "abcdefg"):
        draw.line(segs[name], fill=255, width=int(t))

    # MNIST 是白字黑底，这里保持一致，predict 就不会触发反转
    return canvas.resize((size, size), Image.LANCZOS)


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    out = Path(argv[1] if len(argv) > 1 else "digit.png")
    digit = argv[2] if len(argv) > 2 else "7"
    out.parent.mkdir(parents=True, exist_ok=True)
    draw_digit(digit).save(out)
    print(f"已生成 {out}（数字 {digit}，28x28）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
