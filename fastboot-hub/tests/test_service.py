import unittest
from unittest import mock

from fbhub.config import Config
from fbhub.models import Device, FastbootError
from fbhub.plan import Step
from fbhub.service import run_on_devices, select_devices


def make_device(location: str, serial=None, alias="") -> Device:
    return Device(
        location=location,
        instance_id=f"USB\\VID_18D1&PID_4EE0\\{location}",
        interface_path=f"\\\\?\\usb#{location}",
        vendor_id=0x18D1,
        product_id=0x4EE0,
        serial=serial,
        alias=alias,
    )


class FakeClient:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.response_timeout = 5
        self.calls = []
        self.closed = False

    def flash_file(self, partition, image, progress=None):
        self.calls.append(("flash", partition, image))
        if progress:
            progress(0.5, "half")
        if self.fail:
            raise FastbootError("flash failed")

    def erase(self, partition):
        self.calls.append(("erase", partition))

    def reboot(self, target=None):
        self.calls.append(("reboot", target))

    def getvar(self, name, timeout=None):
        self.calls.append(("getvar", name))
        return "a"

    def oem(self, args):
        self.calls.append(("oem", list(args)))
        return None

    def flashing(self, action):
        self.calls.append(("flashing", action))
        return None

    def set_active(self, slot):
        self.calls.append(("set_active", slot))
        return None

    def boot_file(self, image, progress=None):
        self.calls.append(("boot", image))

    def continue_boot(self):
        self.calls.append(("continue",))

    def raw_command(self, command, timeout=None):
        self.calls.append(("raw", command))
        return None

    def close(self):
        self.closed = True


class ServiceTests(unittest.TestCase):
    def test_select_all_and_filters(self):
        devices = [
            make_device("1D00:0-1.3", alias="A"),
            make_device("1D00:0-1.4", alias="B"),
            make_device("1A00:0-1.2"),
        ]
        self.assertEqual(len(select_devices(devices, select_all=True)), 3)
        selected = select_devices(devices, paths=["1D00:0-1.3"])
        self.assertEqual([item.location for item in selected], ["1D00:0-1.3"])
        selected = select_devices(devices, aliases=["b"])
        self.assertEqual([item.location for item in selected], ["1D00:0-1.4"])
        selected = select_devices(devices, select_all=True, index=3)
        self.assertEqual([item.location for item in selected], ["1D00:0-1.3"])

    def test_parallel_execution_and_events(self):
        devices = [make_device("1D00:0-1.3"), make_device("1D00:0-1.4")]
        events = []
        created = []

        def opener(device, config):
            client = FakeClient()
            created.append(client)
            return client

        with mock.patch("fbhub.service.open_client", side_effect=opener):
            results = run_on_devices(
                devices,
                [Step("getvar", name="current-slot")],
                Config(),
                jobs=2,
                on_event=events.append,
            )

        self.assertTrue(all(item.ok for item in results))
        self.assertEqual(len(results), 2)
        self.assertTrue(all(client.closed for client in created))
        self.assertIn("log", [event.kind for event in events])

    def test_failure_does_not_stop_other_devices(self):
        devices = [make_device("1D00:0-1.3"), make_device("1D00:0-1.4")]

        def opener(device, config):
            return FakeClient(fail=device.location.endswith(".3"))

        with mock.patch("fbhub.service.open_client", side_effect=opener):
            results = run_on_devices(
                devices, [Step("flash", partition="boot", image="x.img")], Config()
            )

        status = {item.location: item.ok for item in results}
        self.assertFalse(status["1D00:0-1.3"])
        self.assertTrue(status["1D00:0-1.4"])

    def test_dry_run_does_not_connect(self):
        devices = [make_device("1D00:0-1.3")]
        with mock.patch("fbhub.service.open_client") as opener:
            results = run_on_devices(
                devices,
                [Step("reboot", target="bootloader")],
                Config(),
                dry_run=True,
            )
        opener.assert_not_called()
        self.assertTrue(results[0].ok)
        self.assertTrue(results[0].output)

    def test_reboot_stops_following_steps(self):
        devices = [make_device("1D00:0-1.3")]
        client = FakeClient()

        with mock.patch("fbhub.service.open_client", return_value=client):
            run_on_devices(
                devices,
                [Step("reboot"), Step("erase", partition="misc")],
                Config(),
            )

        self.assertEqual(client.calls, [("reboot", None)])


if __name__ == "__main__":
    unittest.main()
