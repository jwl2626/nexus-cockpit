import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import torch

from mnist_torch.models import MLP, SmallCNN, build_model, count_parameters, describe_model


class ModelTests(unittest.TestCase):
    def test_forward_shape(self):
        batch = torch.zeros(4, 1, 28, 28)
        for name in ("mlp", "cnn"):
            with self.subTest(model=name):
                out = build_model(name)(batch)
                self.assertEqual(tuple(out.shape), (4, 10))

    def test_classes_are_registered(self):
        self.assertIsInstance(build_model("mlp"), MLP)
        self.assertIsInstance(build_model("cnn"), SmallCNN)

    def test_parameter_counts(self):
        self.assertGreater(count_parameters(build_model("mlp")), 0)
        self.assertGreater(count_parameters(build_model("cnn")), 0)

    def test_smaller_hidden_means_fewer_params(self):
        # 这是一个真实现象：去掉这一条就会踩坑
        # SmallCNN 的参数量主要由第一个全连接层决定（64*7*7 -> hidden），
        # 而不是卷积层。所以 hidden 从 256 降到 64，参数量会掉到 1/4 左右。
        big = count_parameters(build_model("cnn", hidden=256))
        small = count_parameters(build_model("cnn", hidden=64))
        self.assertLess(small, big)
        self.assertLess(small, big / 2)

    def test_cnn_parameters_below_budget(self):
        # 工程上的护栏：默认配置的模型不该超过 1M 参数，否则 CPU 工位机跑不动
        self.assertLess(count_parameters(build_model("cnn", hidden=128)), 1_000_000)

    def test_unknown_model_raises(self):
        with self.assertRaises(ValueError):
            build_model("resnet999")

    def test_describe(self):
        self.assertIn("参数量", describe_model(build_model("cnn")))

    def test_eval_mode_is_deterministic(self):
        model = build_model("cnn").eval()
        x = torch.randn(2, 1, 28, 28)
        with torch.no_grad():
            self.assertTrue(torch.allclose(model(x), model(x)))


if __name__ == "__main__":
    unittest.main()
