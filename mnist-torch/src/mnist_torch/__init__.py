"""完整的 PyTorch MNIST 训练工程。

    train    训练 + 验证 + 测试 + 报告
    eval     用已有 checkpoint 在测试集上评估
    predict  单张图片推理
    export   导出 TorchScript
    smoke    无数据自检（随机张量跑通全流程）
    info     环境信息
"""

from __future__ import annotations

__version__ = "1.0.0"
