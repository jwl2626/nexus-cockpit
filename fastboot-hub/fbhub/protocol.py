"""Fastboot USB protocol implementation."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional, Protocol, Union

from .models import (
    FastbootError,
    FastbootProtocolError,
    FastbootRemoteError,
    FastbootTimeout,
    Response,
)
from .sparse import (
    ImageSource,
    SparseError,
    is_sparse_file,
    iter_sparse_parts,
    open_source,
)
from .winusb import WinUsbDevice, WinUsbError, WinUsbTimeout

AVB_FOOTER_SIZE = 64
AVB_FOOTER_MAGIC = b"AVBf"
MAX_COMMAND_LENGTH = 64
READ_PACKET_SIZE = 64
DEFAULT_MAX_DOWNLOAD = 256 * 1024 * 1024
DEFAULT_PART_SIZE = 32 * 1024 * 1024
TRANSFER_CHUNK = 1024 * 1024

ProgressCallback = Callable[[float, str], None]


class Transport(Protocol):
    def read(self, size: int = READ_PACKET_SIZE,
             timeout_ms: Optional[int] = None) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def close(self) -> None: ...


class FastbootClient:
    """A fastboot session with one physical device."""

    def __init__(
        self,
        transport: Transport,
        *,
        response_timeout: float = 180.0,
        command_timeout: float = 20.0,
        max_part_size: int = DEFAULT_PART_SIZE,
        default_max_download: int = DEFAULT_MAX_DOWNLOAD,
        label: str = "",
    ):
        self.transport = transport
        self.response_timeout = float(response_timeout)
        self.command_timeout = float(command_timeout)
        self.max_part_size = int(max_part_size)
        self.default_max_download = int(default_max_download)
        self.label = label
        self._max_download: Optional[int] = None
        self._closed = False

    # -- basic protocol ----------------------------------------------------
    def read_response(self, timeout: Optional[float] = None) -> Response:
        """Read one response, collecting INFO/TEXT packets as needed."""
        deadline = time.monotonic() + (self.response_timeout if timeout is None else timeout)
        infos: list[str] = []
        texts: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FastbootTimeout(
                    f"等待设备响应超时（{self.label or 'device'}）"
                )
            timeout_ms = max(1, min(30000, int(remaining * 1000)))
            try:
                packet = self.transport.read(READ_PACKET_SIZE, timeout_ms=timeout_ms)
            except WinUsbTimeout:
                # A bootloader may stay silent while erasing/programming slow
                # media.  Reset the pipe happened in WinUsbDevice.read(); retry
                # until the overall response deadline.
                if time.monotonic() >= deadline:
                    raise FastbootTimeout(
                        f"读取 USB 响应超时（{self.label or 'device'}）"
                    )
                continue
            except WinUsbError as exc:
                raise FastbootError(
                    f"读取 USB 响应失败（{self.label or 'device'}）: {exc}"
                ) from exc

            if not packet:
                continue
            text = packet.decode("ascii", errors="replace").rstrip("\x00")
            status = text[:4].upper()
            value = text[4:].rstrip("\x00\r\n")

            if status == "INFO":
                infos.append(value)
                deadline = time.monotonic() + (
                    self.response_timeout if timeout is None else timeout
                )
                continue
            if status == "TEXT":
                texts.append(value)
                deadline = time.monotonic() + (
                    self.response_timeout if timeout is None else timeout
                )
                continue
            if status == "OKAY":
                return Response("OKAY", value, infos, texts)
            if status == "FAIL":
                raise FastbootRemoteError(value, command="")
            if status == "DATA":
                return Response("DATA", value, infos, texts)
            raise FastbootProtocolError(
                f"设备返回未知状态 {status!r}（完整内容: {text!r}）"
            )

    def _send_command(self, command: str, timeout: Optional[float] = None) -> Response:
        encoded = command.encode("ascii", errors="strict")
        if len(encoded) > MAX_COMMAND_LENGTH:
            raise FastbootError(
                f"fastboot 命令过长（{len(encoded)} > {MAX_COMMAND_LENGTH}）: {command!r}"
            )
        try:
            self.transport.write(encoded)
        except WinUsbTimeout as exc:
            raise FastbootTimeout(f"发送命令超时: {command}") from exc
        except WinUsbError as exc:
            raise FastbootError(f"发送命令失败: {command}: {exc}") from exc
        return self.read_response(timeout if timeout is not None else self.command_timeout)

    def command(self, command: str, timeout: Optional[float] = None) -> Response:
        response = self._send_command(command, timeout)
        if response.status == "DATA":
            raise FastbootProtocolError(f"命令 {command!r} 返回了意外的 DATA 响应")
        return response

    # -- variables ---------------------------------------------------------
    def getvar(self, name: str, timeout: Optional[float] = None) -> str:
        response = self.command(f"getvar:{name}", timeout=timeout)
        return response.value.strip()

    def getvar_all(self) -> list[str]:
        response = self.command("getvar:all", timeout=self.response_timeout)
        lines = list(response.infos)
        if response.value:
            lines.append(response.value)
        return lines

    def max_download_size(self) -> int:
        if self._max_download is not None:
            return self._max_download
        value = ""
        try:
            value = self.getvar("max-download-size", timeout=self.command_timeout)
        except (FastbootError, ValueError):
            value = ""
        parsed = 0
        if value:
            try:
                parsed = int(value.strip(), 0)
            except ValueError:
                parsed = 0
        if parsed <= 0:
            parsed = self.default_max_download
        # uint32 protocol field
        self._max_download = min(parsed, 0xFFFFFFFF)
        return self._max_download

    # -- AVB footer relocation --------------------------------------------
    def _partition_size(self, partition: str) -> int:
        try:
            value = self.getvar(f"partition-size:{partition}", timeout=self.command_timeout)
        except FastbootError:
            return 0
        try:
            return int(value.strip(), 0)
        except ValueError:
            return 0

    def _is_logical(self, partition: str) -> bool:
        try:
            value = self.getvar(f"is-logical:{partition}", timeout=self.command_timeout)
        except FastbootError:
            return False
        return value.strip().lower() == "yes"

    def _prepare_avb_image(
        self, partition: str, path: Path, size: int
    ) -> tuple[Path, int, Optional[Path]]:
        """Move an AVB footer to the end of the partition, like fastboot does.

        Android boot images are often smaller than the partition.  The AVB
        footer must live at the very end of the partition for the bootloader to
        find it.  AOSP fastboot pads the image and copies the 64-byte footer.
        Sparse images and logical partitions are left untouched.
        """
        if size < AVB_FOOTER_SIZE:
            return path, size, None
        if is_sparse_file(path):
            return path, size, None
        try:
            with open(path, "rb") as handle:
                handle.seek(-AVB_FOOTER_SIZE, os.SEEK_END)
                footer = handle.read(AVB_FOOTER_SIZE)
        except OSError:
            return path, size, None
        if len(footer) != AVB_FOOTER_SIZE or footer[:4] != AVB_FOOTER_MAGIC:
            return path, size, None

        partition_size = self._partition_size(partition)
        if partition_size <= size or partition_size > 0xFFFFFFFF:
            return path, size, None
        if self._is_logical(partition):
            return path, size, None

        fd, temp_name = tempfile.mkstemp(prefix=f"fbhub-{partition}-", suffix=".img")
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as output, open(path, "rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
                output.truncate(partition_size)
                output.seek(partition_size - AVB_FOOTER_SIZE)
                output.write(footer)
        except Exception:
            try:
                temp_path.unlink()
            except OSError:
                pass
            raise
        return temp_path, partition_size, temp_path

    # -- data transfer -----------------------------------------------------
    def download_stream(
        self,
        size: int,
        reader: Callable[[int], bytes],
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        if size <= 0:
            raise FastbootError("下载长度为 0")
        if size > 0xFFFFFFFF:
            raise FastbootError("下载长度超过 fastboot 协议上限 (4 GiB)")

        response = self._send_command(f"download:{size:08x}", timeout=self.command_timeout)
        if response.status != "DATA":
            raise FastbootProtocolError(f"download 未返回 DATA: {response.status}")
        if response.value:
            try:
                expected = int(response.value.strip(), 16)
            except ValueError as exc:
                raise FastbootProtocolError(
                    f"download 返回了无效长度: {response.value!r}"
                ) from exc
            if expected != size:
                raise FastbootProtocolError(
                    f"设备要求 {expected} 字节，但准备发送 {size} 字节"
                )

        sent = 0
        while sent < size:
            chunk = reader(min(TRANSFER_CHUNK, size - sent))
            if not chunk:
                raise FastbootError(f"镜像在 {sent}/{size} 字节处提前结束")
            if len(chunk) > size - sent:
                raise FastbootError("读取镜像时返回了过多数据")
            self.transport.write(chunk)
            sent += len(chunk)
            if progress:
                progress(sent, size)

        response = self.read_response(self.response_timeout)
        if response.status != "OKAY":
            raise FastbootProtocolError(f"下载完成后设备未返回 OKAY: {response.status}")

    def download_file(
        self, path: Union[str, Path], progress: Optional[Callable[[int, int], None]] = None
    ) -> int:
        file_path = Path(path)
        size = file_path.stat().st_size
        with open(file_path, "rb") as handle:
            self.download_stream(size, handle.read, progress)
        return size

    def download_bytes(
        self, data: bytes, progress: Optional[Callable[[int, int], None]] = None
    ) -> None:
        view = memoryview(data)

        def reader(count: int) -> bytes:
            nonlocal view
            chunk = view[:count].tobytes()
            view = view[count:]
            return chunk

        self.download_stream(len(data), reader, progress)

    # -- flashing ----------------------------------------------------------
    def flash_file(
        self,
        partition: str,
        path: Union[str, Path],
        progress: Optional[ProgressCallback] = None,
        source: Optional[ImageSource] = None,
    ) -> None:
        file_path = Path(path)
        if not file_path.is_file():
            raise FastbootError(f"找不到镜像文件: {file_path}")
        size = file_path.stat().st_size
        if size <= 0:
            raise FastbootError(f"镜像为空: {file_path}")

        prepared_path = file_path
        temp_path: Optional[Path] = None
        if source is None:
            prepared_path, size, temp_path = self._prepare_avb_image(
                partition, file_path, size
            )

        try:
            max_download = self.max_download_size()
            part_limit = min(max_download, self.max_part_size)
            name = file_path.name

            if size <= max_download:
                def single_progress(sent: int, total: int) -> None:
                    if progress:
                        progress(min(1.0, sent / total if total else 1.0), f"发送 {name}")

                self.download_file(prepared_path, single_progress)
                self.flash_partition(partition)
                if progress:
                    progress(1.0, f"写入 {partition}")
                return

            # Large image: convert to sparse and split, exactly like the
            # Android fastboot implementation.
            owned_source = source is None
            image_source = source or open_source(prepared_path)
            try:
                total_hint = max(1, size)
                sent_hint = 0
                part_count = 0
                for index, part in enumerate(iter_sparse_parts(image_source, part_limit), 1):
                    part_count += 1
                    label = f"{name} 分片 {index}（{len(part) / (1024 * 1024):.1f} MiB）"

                    def part_progress(sent: int, total: int, *, _label: str = label,
                                      _base: int = sent_hint) -> None:
                        if progress:
                            progress(
                                min(0.99, (_base + sent) / total_hint),
                                f"发送 {_label}",
                            )

                    self.download_bytes(part, part_progress)
                    self.flash_partition(partition)
                    sent_hint += len(part)
                    if progress:
                        progress(min(0.99, sent_hint / total_hint), f"写入 {partition} 分片 {index}")
                if part_count == 0:
                    raise FastbootError("镜像没有可写入的数据（全是 DONTCARE）")
                if progress:
                    progress(1.0, f"写入 {partition}")
            finally:
                if owned_source:
                    image_source.close()
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def flash_partition(self, partition: str) -> None:
        if not partition or ":" in partition:
            raise FastbootError(f"无效的分区名: {partition!r}")
        self.command(f"flash:{partition}", timeout=self.response_timeout)

    def erase(self, partition: str) -> None:
        if not partition or ":" in partition:
            raise FastbootError(f"无效的分区名: {partition!r}")
        self.command(f"erase:{partition}", timeout=self.response_timeout)

    def boot_file(self, path: Union[str, Path],
                  progress: Optional[ProgressCallback] = None) -> None:
        file_path = Path(path)
        if not file_path.is_file():
            raise FastbootError(f"找不到镜像文件: {file_path}")
        name = file_path.name

        def cb(sent: int, total: int) -> None:
            if progress:
                progress(min(1.0, sent / total if total else 1.0), f"发送 {name}")

        self.download_file(file_path, cb)
        self.command("boot", timeout=self.response_timeout)
        if progress:
            progress(1.0, "启动")

    # -- commands ----------------------------------------------------------
    def oem(self, args: list[str] | str) -> Response:
        text = " ".join(args) if isinstance(args, list) else args
        return self.command(f"oem {text}".strip(), timeout=self.response_timeout)

    def flashing(self, action: str) -> Response:
        return self.command(f"flashing {action}", timeout=self.response_timeout)

    def set_active(self, slot: str) -> Response:
        return self.command(f"set_active:{slot}", timeout=self.command_timeout)

    def continue_boot(self) -> Response:
        return self.command("continue", timeout=self.command_timeout)

    def raw_command(self, command: str, timeout: Optional[float] = None) -> Response:
        return self.command(command, timeout=timeout)

    def reboot(self, target: Optional[str] = None) -> None:
        name = (target or "").strip().lower()
        if name in {"", "system", "normal", "os"}:
            command = "reboot"
        elif name in {"bootloader", "boot"}:
            command = "reboot-bootloader"
        elif name in {"fastboot", "fastbootd", "userspace"}:
            command = "reboot-fastboot"
        elif name == "recovery":
            command = "reboot-recovery"
        elif name in {"edl", "download", "9008"}:
            command = "reboot-edl"
        else:
            command = f"reboot-{name}"

        encoded = command.encode("ascii", errors="strict")
        try:
            self.transport.write(encoded)
        except WinUsbError as exc:
            # The device may reset the port immediately after receiving the
            # command; that is normal for a reboot.
            raise FastbootError(f"发送重启命令失败: {exc}") from exc

        try:
            self.read_response(timeout=2.0)
        except FastbootTimeout:
            return
        except FastbootRemoteError:
            # The bootloader explicitly rejected the reboot target.
            raise
        except FastbootError:
            # A disconnect while rebooting is expected.
            return

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.transport.close()
        except Exception:
            pass


def client_for_device(device: WinUsbDevice, *, label: str = "",
                      response_timeout: float = 180.0,
                      command_timeout: float = 20.0,
                      max_part_size: int = DEFAULT_PART_SIZE) -> FastbootClient:
    return FastbootClient(
        device,
        response_timeout=response_timeout,
        command_timeout=command_timeout,
        max_part_size=max_part_size,
        label=label or device.interface.location,
    )
