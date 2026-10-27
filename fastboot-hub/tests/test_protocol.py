import os
import tempfile
import unittest
from pathlib import Path

from fbhub.models import FastbootRemoteError, FastbootTimeout
from fbhub.protocol import FastbootClient
from fbhub.winusb import WinUsbTimeout


class FakeTransport:
    def __init__(self):
        self.pending: list[bytes] = []
        self.commands: list[bytes] = []
        self.payloads: list[bytes] = []
        self.expect_payload = 0
        self.payload = bytearray()
        self.max_download = 0x4000

    def write(self, data: bytes) -> int:
        if self.expect_payload:
            remaining = self.expect_payload - len(data)
            self.payload.extend(data)
            self.expect_payload = remaining
            if self.expect_payload == 0:
                self.payloads.append(bytes(self.payload))
                self.payload.clear()
                self.pending.append(b"OKAY")
            return len(data)

        if data.startswith(b"getvar:max-download-size"):
            self.pending.append(f"OKAY0x{self.max_download:x}".encode())
        elif data.startswith(b"download:"):
            self.commands.append(data)
            size = int(data.split(b":", 1)[1], 16)
            self.pending.append(f"DATA{size:08x}".encode())
            self.expect_payload = size
            self.payload.clear()
        elif data.startswith(b"flash:") or data.startswith(b"erase:"):
            self.commands.append(data)
            self.pending.append(b"OKAY")
        elif data.startswith(b"getvar:"):
            self.commands.append(data)
            self.pending.append(b"OKAYvalue")
        else:
            self.commands.append(data)
            self.pending.append(b"OKAY")
        return len(data)

    def read(self, size: int = 64, timeout_ms=None) -> bytes:
        if not self.pending:
            raise AssertionError(f"read without pending data; commands={self.commands}")
        return self.pending.pop(0)

    def close(self) -> None:
        pass


class TimeoutTransport(FakeTransport):
    def read(self, size: int = 64, timeout_ms=None) -> bytes:
        raise WinUsbTimeout("timeout")


class AvbClient(FastbootClient):
    def getvar(self, name, timeout=None):
        if name == "partition-size:boot":
            return "0x2000"
        if name == "is-logical:boot":
            return "no"
        if name == "max-download-size":
            return "0x10000"
        return "x"


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

    def test_getvar(self):
        transport = FakeTransport()
        client = FastbootClient(transport, command_timeout=1, response_timeout=1)
        self.assertEqual(client.getvar("current-slot"), "value")
        self.assertEqual(transport.commands, [b"getvar:current-slot"])

    def test_download_and_flash_raw(self):
        path = Path(self.tempdir.name) / "boot.img"
        path.write_bytes(b"A" * 8192)
        transport = FakeTransport()
        transport.max_download = 0x4000
        client = FastbootClient(transport, command_timeout=1, response_timeout=1)
        client.flash_file("boot", path)
        self.assertEqual(transport.payloads, [b"A" * 8192])
        self.assertEqual(transport.commands[-1], b"flash:boot")
        self.assertEqual(transport.commands.count(b"flash:boot"), 1)

    def test_large_raw_is_split(self):
        path = Path(self.tempdir.name) / "system.img"
        path.write_bytes(b"Z" * (8 * 4096))
        transport = FakeTransport()
        transport.max_download = 0x3000  # 12 KiB
        client = FastbootClient(transport, command_timeout=1, response_timeout=1)
        client.flash_file("system", path)
        self.assertGreater(transport.commands.count(b"flash:system"), 1)
        for payload in transport.payloads:
            self.assertLessEqual(len(payload), 0x3000)
            self.assertEqual(payload[:4], b"\x3a\xff\x26\xed")

    def test_remote_failure(self):
        transport = FakeTransport()
        transport.write = lambda data: transport.pending.append(b"FAILno such partition")
        client = FastbootClient(transport, command_timeout=1, response_timeout=1)
        with self.assertRaises(FastbootRemoteError):
            client.erase("misc")

    def test_reboot(self):
        transport = FakeTransport()
        client = FastbootClient(transport, command_timeout=1, response_timeout=1)
        client.reboot("bootloader")
        self.assertEqual(transport.commands[-1], b"reboot-bootloader")

    def test_reboot_timeout_is_success(self):
        transport = TimeoutTransport()
        client = FastbootClient(transport, command_timeout=1, response_timeout=1)
        client.reboot()

    def test_avb_footer_is_moved_to_partition_end(self):
        # 4096-byte payload + a 64-byte AVB footer at the end of the image.
        footer = b"AVBf" + b"F" * 60
        path = Path(self.tempdir.name) / "boot.img"
        path.write_bytes(b"B" * 4096 + footer)

        transport = FakeTransport()
        client = AvbClient(transport, command_timeout=1, response_timeout=1)
        client.flash_file("boot", path)

        self.assertEqual(len(transport.payloads), 1)
        payload = transport.payloads[0]
        self.assertEqual(len(payload), 0x2000)
        self.assertEqual(payload[4096:4160], footer)
        self.assertEqual(payload[-64:], footer)
        self.assertEqual(payload[4160:-64], b"\0" * (0x2000 - 4160 - 64))
        self.assertEqual(transport.commands[-1], b"flash:boot")

    def test_max_download_default(self):
        transport = FakeTransport()
        transport.write = lambda data: transport.pending.append(b"FAILnot supported")
        client = FastbootClient(transport, command_timeout=1, response_timeout=1,
                                default_max_download=12345)
        self.assertEqual(client.max_download_size(), 12345)


if __name__ == "__main__":
    unittest.main()
