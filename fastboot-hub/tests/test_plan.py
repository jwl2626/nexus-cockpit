import json
import tempfile
import unittest
from pathlib import Path

from fbhub.models import PlanError
from fbhub.plan import load_plan, step_from_tokens


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        (self.root / "boot.img").write_bytes(b"boot")
        (self.root / "system.img").write_bytes(b"system")

    def write_plan(self, payload) -> Path:
        path = self.root / "plan.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_load_relative_images(self):
        path = self.write_plan(
            {
                "name": "factory",
                "steps": [
                    {"action": "flash", "partition": "boot", "image": "boot.img"},
                    {"action": "erase", "partition": "misc"},
                    {"action": "reboot", "target": "bootloader"},
                ],
            }
        )
        plan = load_plan(path)
        self.assertEqual(plan.name, "factory")
        self.assertEqual(plan.steps[0].image, str((self.root / "boot.img").resolve()))
        self.assertEqual(plan.steps[1].action, "erase")

    def test_unsupported_action(self):
        path = self.write_plan({"steps": [{"action": "format", "partition": "userdata"}]})
        with self.assertRaises(PlanError):
            load_plan(path)

    def test_missing_image_key(self):
        path = self.write_plan({"steps": [{"action": "flash", "partition": "boot"}]})
        with self.assertRaises(PlanError):
            load_plan(path)

    def test_cli_tokens(self):
        step = step_from_tokens(["flash", "boot", str(self.root / "boot.img")])
        self.assertEqual(step.action, "flash")
        self.assertEqual(step.partition, "boot")

        step = step_from_tokens(["reboot", "fastboot"])
        self.assertEqual(step.target, "fastboot")

        step = step_from_tokens(["getvar", "current-slot"])
        self.assertEqual(step.name, "current-slot")

        step = step_from_tokens(["oem", "edl"])
        self.assertEqual(step.args, ["edl"])

    def test_unsupported_cli(self):
        with self.assertRaises(PlanError):
            step_from_tokens(["format", "userdata"])


if __name__ == "__main__":
    unittest.main()
