import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mnist_torch.metrics import (
    accuracy,
    confusion_matrix,
    format_confusion,
    per_class_report,
    topk_accuracy,
)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        # 2 类：真实 0 有 4 个（抓对 3 个），真实 1 有 3 个（全抓对）
        self.matrix = [[3, 1], [0, 3]]

    def test_confusion_counts(self):
        matrix = confusion_matrix([0, 0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1, 1], 2)
        self.assertEqual(matrix, self.matrix)

    def test_accuracy(self):
        self.assertAlmostEqual(accuracy(self.matrix), 6 / 7)

    def test_per_class(self):
        report = per_class_report(self.matrix, ["0", "1"])
        self.assertAlmostEqual(report["0"]["precision"], 1.0)      # 预测为 0 的 3 个全对
        self.assertAlmostEqual(report["0"]["recall"], 0.75)        # 真实 0 有 4 个，抓到 3 个
        self.assertAlmostEqual(report["1"]["precision"], 0.75)     # 预测为 1 的 4 个里对了 3 个
        self.assertAlmostEqual(report["1"]["recall"], 1.0)         # 真实 1 全抓到

    def test_format_contains_all_labels(self):
        text = format_confusion(self.matrix, ["0", "1"])
        self.assertIn("真实\\预测", text)
        self.assertIn("0", text)

    def test_topk(self):
        logits = [[0.1, 0.9], [0.8, 0.2]]
        self.assertEqual(topk_accuracy(logits, [1, 0], k=1), 1.0)
        # 第二个样本正确答案 1 排第二，k=1 时算错
        self.assertAlmostEqual(topk_accuracy(logits, [1, 1], k=1), 0.5)
        self.assertAlmostEqual(topk_accuracy(logits, [1, 1], k=2), 1.0)

    def test_empty(self):
        self.assertEqual(accuracy([[0, 0], [0, 0]]), 0.0)
        self.assertEqual(topk_accuracy([], [], k=1), 0.0)


if __name__ == "__main__":
    unittest.main()
