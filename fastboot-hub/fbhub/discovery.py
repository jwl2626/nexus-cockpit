"""Device discovery and connection setup."""

from __future__ import annotations

import time
from typing import Iterable, Optional

from .config import Config
from .models import Device, DeviceNotFoundError, FastbootError
from .protocol import FastbootClient, client_for_device
from .winusb import (
    UsbInterface,
    WinUsbDevice,
    WinUsbError,
    enumerate_usb_interfaces,
)


def list_devices(config: Optional[Config] = None, *, retries: int = 2) -> list[Device]:
    """Return every USB device that exposes the fastboot interface."""
    cfg = config or Config()
    last_error: Optional[Exception] = None
    for attempt in range(max(1, retries)):
        try:
            devices: list[Device] = []
            seen: set[str] = set()
            for interface in enumerate_usb_interfaces():
                try:
                    usb_device = WinUsbDevice(interface)
                except (WinUsbError, OSError) as exc:
                    last_error = exc
                    continue
                try:
                    if not usb_device.is_fastboot:
                        continue
                    key = interface.location
                    if key in seen:
                        continue
                    seen.add(key)
                    serial = _clean_serial(usb_device.serial)
                    devices.append(
                        Device(
                            location=interface.location,
                            instance_id=interface.instance_id,
                            interface_path=interface.path,
                            vendor_id=usb_device.vendor_id,
                            product_id=usb_device.product_id,
                            serial=serial,
                            product=usb_device.product,
                            manufacturer=usb_device.manufacturer,
                            interface_number=(
                                usb_device.interface_descriptor.bInterfaceNumber
                                if usb_device.interface_descriptor
                                else 0
                            ),
                            location_paths=interface.location_paths,
                            alias=cfg.alias_for(interface.location),
                        )
                    )
                finally:
                    usb_device.close()
            devices.sort(key=lambda item: item.location)
            return devices
        except Exception as exc:  # SetupAPI failures are rare but transient
            last_error = exc
            if attempt + 1 >= retries:
                break
            time.sleep(0.25)

    if last_error:
        raise FastbootError(f"枚举 USB 设备失败: {last_error}") from last_error
    return []


def _clean_serial(serial: Optional[str]) -> Optional[str]:
    if not serial:
        return None
    value = serial.strip("\x00 \t\r\n")
    if not value:
        return None
    # Some bootloaders report a placeholder when no serial is programmed.
    if set(value) <= {"0"}:
        return None
    return value


def open_client(device: Device, config: Optional[Config] = None,
                *, retries: int = 3) -> FastbootClient:
    """Open a fresh fastboot session for ``device``."""
    cfg = config or Config()
    max_part = max(1024 * 1024, int(cfg.max_part_size_mb) * 1024 * 1024)
    last_error: Optional[Exception] = None

    for attempt in range(max(1, retries)):
        interfaces = list(enumerate_usb_interfaces())
        # Prefer the exact instance id (stable for the same VID/PID on the same
        # port), then fall back to the physical location (the device may have
        # re-enumerated with a different PID after a reboot).
        for interface in _candidate_interfaces(device, interfaces):
            try:
                usb_device = WinUsbDevice(interface)
            except (WinUsbError, OSError) as exc:
                last_error = exc
                continue
            if not usb_device.is_fastboot:
                last_error = FastbootError(f"{interface.location} 不是 fastboot 接口")
                usb_device.close()
                continue
            if device.vendor_id and usb_device.vendor_id not in (0, device.vendor_id):
                last_error = FastbootError("设备 VID 已变化，可能已拔出")
                usb_device.close()
                continue
            try:
                return client_for_device(
                    usb_device,
                    label=device.label,
                    response_timeout=cfg.response_timeout_s,
                    command_timeout=cfg.command_timeout_s,
                    max_part_size=max_part,
                )
            except Exception:
                usb_device.close()
                raise

        if attempt + 1 < retries:
            time.sleep(0.2)

    detail = f"（{last_error}）" if last_error else ""
    raise DeviceNotFoundError(
        f"无法打开设备 {device.label} [{device.location}]{detail}\n"
        "请确认设备仍在 fastboot 模式，并且没有被其他刷机工具占用。"
    )


def _candidate_interfaces(device: Device, interfaces: Iterable[UsbInterface]) -> list[UsbInterface]:
    exact = [item for item in interfaces if item.instance_id == device.instance_id]
    by_location = [item for item in interfaces if item.location == device.location]
    result: list[UsbInterface] = []
    seen: set[str] = set()
    for item in exact + by_location:
        if item.path in seen:
            continue
        seen.add(item.path)
        result.append(item)
    return result


def diagnose() -> dict:
    """Collect information useful when no device is detected."""
    interfaces: list[dict] = []
    errors: list[str] = []
    for interface in enumerate_usb_interfaces():
        item = {
            "location": interface.location,
            "instance_id": interface.instance_id,
            "path": interface.path,
            "location_paths": list(interface.location_paths),
            "opened": False,
            "fastboot": False,
        }
        try:
            usb_device = WinUsbDevice(interface)
            try:
                item["opened"] = True
                item["fastboot"] = usb_device.is_fastboot
                item["interface_class"] = (
                    usb_device.interface_descriptor.bInterfaceClass
                    if usb_device.interface_descriptor
                    else None
                )
                item["serial"] = usb_device.serial
                item["product"] = usb_device.product
                item["vendor_id"] = f"{usb_device.vendor_id:04x}"
                item["product_id"] = f"{usb_device.product_id:04x}"
            finally:
                usb_device.close()
        except (WinUsbError, OSError) as exc:
            item["error"] = str(exc)
            errors.append(f"{interface.location}: {exc}")
        interfaces.append(item)
    return {"interfaces": interfaces, "errors": errors}


def list_fastboot_exe(fastboot_exe: str = "fastboot") -> tuple[bool, str]:
    """Run ``fastboot devices -l`` for diagnostics."""
    import subprocess

    try:
        completed = subprocess.run(
            [fastboot_exe, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode == 0, output.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
