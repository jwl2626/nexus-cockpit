"""Shared data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .topology import parse_location


class FbhubError(Exception):
    """Base class for expected, user-facing errors."""


class DeviceNotFoundError(FbhubError):
    pass


class FastbootError(FbhubError):
    pass


class FastbootTimeout(FastbootError):
    pass


class FastbootRemoteError(FastbootError):
    def __init__(self, message: str, command: str = ""):
        self.command = command
        self.remote_message = message
        super().__init__(f"设备返回 FAIL: {message}" if message else "设备返回 FAIL")


class FastbootProtocolError(FastbootError):
    pass


class PlanError(FbhubError):
    pass


class ConfigError(FbhubError):
    pass


@dataclass
class Response:
    status: str
    value: str = ""
    infos: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)


@dataclass
class Device:
    """A fastboot device discovered through WinUSB."""

    location: str
    instance_id: str
    interface_path: str
    vendor_id: int
    product_id: int
    serial: Optional[str] = None
    product: Optional[str] = None
    manufacturer: Optional[str] = None
    interface_number: int = 0
    location_paths: tuple[str, ...] = ()
    alias: str = ""

    @property
    def path(self) -> str:
        return self.location

    @property
    def label(self) -> str:
        return self.alias or self.location

    @property
    def hub_port(self) -> Optional[int]:
        try:
            return parse_location(self.location).hub_port
        except ValueError:
            return None

    @property
    def index(self) -> Optional[int]:
        try:
            return parse_location(self.location).index
        except ValueError:
            return None

    @property
    def serial_display(self) -> str:
        return self.serial or "-"

    def as_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "alias": self.alias,
            "label": self.label,
            "serial": self.serial,
            "product": self.product,
            "manufacturer": self.manufacturer,
            "vendor_id": f"{self.vendor_id:04x}",
            "product_id": f"{self.product_id:04x}",
            "instance_id": self.instance_id,
            "interface_path": self.interface_path,
            "interface_number": self.interface_number,
            "hub_port": self.hub_port,
            "index": self.index,
            "location_paths": list(self.location_paths),
        }


@dataclass
class DeviceResult:
    location: str
    label: str
    ok: bool
    message: str
    duration: float = 0.0
    output: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "label": self.label,
            "ok": self.ok,
            "message": self.message,
            "duration": round(self.duration, 3),
            "output": self.output,
        }
