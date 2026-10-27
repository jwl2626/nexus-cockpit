import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import torch
import torch.nn as nn
from PIL import Image

from mnist_torch.checkpoint import build_from_checkpoint, load_checkpoint
from mnist_torch.config import Config
from mnist_torch.data import build_synthetic
from mnist_torch.engine import evaluate, fit, train_one_epoch
from mnist_torch.export import export_torchscript, verify_export
from mnist_torch.models import build_model
from mnist_torch.predict import Predictor


def _quiet_logger() -> logging.Logger:
    logger = logging.getLogger("mnist-torch-test")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def _cfg(tmp: Path) -> Config:
    return Config(
        model="mlp",
        epochs=1,
        batch_size=16,
        val_size=0,
        amp=False,
        patience=0,
        scheduler="none",
        device="cpu",
        out_dir=str(tmp),
        run_name="unittest",
        num_workers=0,
    )


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.cfg = _cfg(self.tmp)
        self.bundle = build_synthetic(self.cfg, n_train=64, n_val=32, n_test=32)
        self.loaders = self.bundle.loaders(self.cfg)
        self.logger = _quiet_logger()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_train_one_epoch(self):
        model = build_model("mlp")
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        stats = train_one_epoch(
            model, self.loaders["train"], optimizer, nn.CrossEntropyLoss(), "cpu"
        )
        self.assertTrue(0.0 <= stats["acc"] <= 1.0)
        self.assertTrue(stats["loss"] < 1e9)
        self.assertGreater(stats["seconds"], 0)

    def test_evaluate_returns_predictions(self):
        model = build_model("mlp")
        result = evaluate(model, self.loaders["test"], nn.CrossEntropyLoss(), "cpu")
        self.assertEqual(len(result["preds"]), 32)
        self.assertEqual(len(result["targets"]), 32)
        self.assertTrue(0.0 <= result["acc"] <= 1.0)

    def test_fit_saves_checkpoints(self):
        history = fit(self.cfg, self.loaders, self.tmp, self.logger)
        self.assertTrue((self.tmp / "best.pt").is_file())
        self.assertTrue((self.tmp / "last.pt").is_file())
        self.assertIn("val_acc", history)
        self.assertEqual(len(history["train_loss"]), 1)

    def test_checkpoint_roundtrip(self):
        fit(self.cfg, self.loaders, self.tmp, self.logger)
        model, cfg, payload = build_from_checkpoint(self.tmp / "best.pt", device="cpu")
        self.assertEqual(cfg.model, self.cfg.model)
        self.assertIn("epoch", payload)
        x = torch.zeros(1, 1, 28, 28)
        with torch.no_grad():
            self.assertEqual(tuple(model(x).shape), (1, 10))

    def test_export_matches_original(self):
        fit(self.cfg, self.loaders, self.tmp, self.logger)
        model, _, _ = build_from_checkpoint(self.tmp / "best.pt", device="cpu")
        path = export_torchscript(model, self.tmp / "model.pt")
        self.assertTrue(path.is_file())
        self.assertLess(verify_export(path, model), 1e-4)

    def test_predictor_auto_invert(self):
        fit(self.cfg, self.loaders, self.tmp, self.logger)
        predictor = Predictor(self.tmp / "best.pt", device="cpu")
        # 纯白图：MNIST 是白字黑底，白底必须被取反，取反后整体应为负
        white = Image.new("L", (28, 28), color=255)
        tensor = predictor.preprocess(white, invert="auto")
        self.assertLess(float(tensor.mean()), 0.0)
        prediction = predictor.predict_tensor(tensor)
        self.assertIn(prediction.label, range(10))
        self.assertEqual(len(prediction.topk), 3)


class ConfigTests(unittest.TestCase):
    def test_from_dict_ignores_unknown(self):
        cfg = Config.from_dict({"epochs": "3", "unknown_key": 1, "amp": "false"})
        self.assertEqual(cfg.epochs, 3)
        self.assertFalse(cfg.amp)

    def test_update_does_not_mutate(self):
        base = Config()
        updated = base.update({"epochs": 9})
        self.assertEqual(base.epochs, 5)
        self.assertEqual(updated.epochs, 9)

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.json"
            Config(epochs=7).save(path)
            self.assertEqual(Config.load(path).epochs, 7)


if __name__ == "__main__":
    unittest.main()
