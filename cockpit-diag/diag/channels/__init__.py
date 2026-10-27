"""通道注册表。"""

from __future__ import annotations

from typing import Any

from .adb import AdbChannel
from .base import Channel, ChannelUnavailable
from .canbus import CanChannel
from .ethernet import EthernetChannel
from .fastboot import FastbootChannel

__all__ = [
    "Channel",
    "ChannelUnavailable",
    "AdbChannel",
    "FastbootChannel",
    "CanChannel",
    "EthernetChannel",
    "build_channels",
]

_REGISTRY = {
    "adb": AdbChannel,
    "fastboot": FastbootChannel,
    "can": CanChannel,
    "ethernet": EthernetChannel,
}


def build_channels(config: dict[str, Any] | None = None) -> dict[str, Channel]:
    """按配置建出所有通道实例。配置里没写的通道用默认参数。"""
    config = config or {}
    channels: dict[str, Channel] = {}
    for name, cls in _REGISTRY.items():
        opts = dict(config.get(name) or {})
        try:
            channels[name] = cls(**opts)
        except TypeError:
            # 配置里多写了不认识的键，退化成默认构造，不让整条流程挂掉
            channels[name] = cls()
    return channels
