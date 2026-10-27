# -*- coding: utf-8 -*-
"""zlgcan.dll 的最小 ctypes 封装（只覆盖本工具用到的接口）。

用途：TCP 型设备（CANFDNET 系列）需要在 OpenDevice 之后用 ZCAN_SetValue 写入 IP/端口，
而高层包 `zlgcan` 没有暴露设备句柄，所以这里直接对 DLL 调用。

结构体定义参考周立功官方 C++ 例程的 Python 移植（社区版本），字段顺序与 zlgcan.h 一致。
"""

from __future__ import annotations

import ctypes
from ctypes import POINTER, Structure, byref, c_char_p, c_ubyte, c_uint, c_ulonglong, c_ushort

# ---- 设备类型（与 zlgcan.h 对齐）----
ZCAN_USBCANFD_200U = 41
ZCAN_CANFDNET_400U_TCP = 52

CANFD_ISO = 0

ZCAN_TYPE_CAN = 0
ZCAN_TYPE_CANFD = 1


class _CanInit(Structure):
    _fields_ = [
        ("acc_code", c_uint), ("acc_mask", c_uint), ("reserved", c_uint),
        ("filter", c_ubyte), ("timing0", c_ubyte), ("timing1", c_ubyte), ("mode", c_ubyte),
    ]


class _CanfdInit(Structure):
    _fields_ = [
        ("acc_code", c_uint), ("acc_mask", c_uint),
        ("abit_timing", c_uint), ("dbit_timing", c_uint), ("brp", c_uint),
        ("filter", c_ubyte), ("mode", c_ubyte), ("pad", c_ushort), ("reserved", c_uint),
    ]


class _InitUnion(ctypes.Union):
    _fields_ = [("can", _CanInit), ("canfd", _CanfdInit)]


class ChannelInitConfig(Structure):
    _fields_ = [("can_type", c_uint), ("config", _InitUnion)]


class CanFrame(Structure):
    _fields_ = [
        ("can_id", c_uint, 29), ("err", c_uint, 1), ("rtr", c_uint, 1), ("eff", c_uint, 1),
        ("can_dlc", c_ubyte), ("__pad", c_ubyte), ("__res0", c_ubyte), ("__res1", c_ubyte),
        ("data", c_ubyte * 8),
    ]


class CanFdFrame(Structure):
    _fields_ = [
        ("can_id", c_uint, 29), ("err", c_uint, 1), ("rtr", c_uint, 1), ("eff", c_uint, 1),
        ("len", c_ubyte), ("brs", c_ubyte, 1), ("esi", c_ubyte, 1), ("__res", c_ubyte, 6),
        ("__res0", c_ubyte), ("__res1", c_ubyte), ("data", c_ubyte * 64),
    ]


class TransmitFd(Structure):
    _fields_ = [("frame", CanFdFrame), ("transmit_type", c_uint)]


class ReceiveFd(Structure):
    _fields_ = [("frame", CanFdFrame), ("timestamp", c_ulonglong)]


class ZlgDll:
    """薄封装：只暴露桥接需要的六个函数。"""

    def __init__(self, dll_dir: str):
        import os

        path = os.path.join(dll_dir, "zlgcan.dll")
        self.dll = ctypes.WinDLL(path)
        self.dll.ZCAN_OpenDevice.restype = c_ulonglong
        self.dll.ZCAN_InitCAN.restype = c_ulonglong
        self.dll.ZCAN_StartCAN.argtypes = [c_ulonglong]
        self.dll.ZCAN_TransmitFD.restype = c_uint
        self.dll.ZCAN_GetReceiveNum.restype = c_uint
        self.dev = 0
        self.ch = 0

    # ---- 设备 ----
    def open_device(self, dev_type: int, index: int = 0) -> bool:
        self.dev = self.dll.ZCAN_OpenDevice(c_uint(dev_type), c_uint(index), c_uint(0))
        return self.dev not in (0, 0xFFFFFFFFFFFFFFFF)

    def close_device(self):
        if self.dev:
            self.dll.ZCAN_CloseDevice(c_ulonglong(self.dev))

    def set_value(self, path: str, value: str) -> int:
        """例如 set_value("0/ip", "192.168.1.100")、set_value("0/canfd_abit_baud_rate", "500000")"""
        try:
            return self.dll.ZCAN_SetValue(
                c_ulonglong(self.dev), c_char_p(path.encode()), c_char_p(str(value).encode())
            )
        except Exception:
            return 0

    # ---- 通道 ----
    def init_canfd(self, channel: int, abit: int, dbit: int) -> bool:
        cfg = ChannelInitConfig()
        cfg.can_type = ZCAN_TYPE_CANFD
        cfg.config.canfd.filter = 0
        cfg.config.canfd.acc_code = 0
        cfg.config.canfd.acc_mask = 0xFFFFFFFF
        cfg.config.canfd.mode = CANFD_ISO

        # 键名与官方例程一致（0/ 前缀是通道号）
        self.set_value("0/canfd_standard", "0")
        self.set_value(f"{channel}/canfd_abit_baud_rate", str(abit))
        self.set_value(f"{channel}/canfd_dbit_baud_rate", str(dbit))
        self.set_value(f"{channel}/filter_clear", "0")

        self.ch = self.dll.ZCAN_InitCAN(c_ulonglong(self.dev), c_uint(channel), byref(cfg))
        if not self.ch:
            return False
        return self.dll.ZCAN_StartCAN(c_ulonglong(self.ch)) == 1

    def receive_num(self) -> int:
        """待接收帧数（CANFD 类型），先查数量再收，避免 ReceiveFD 阻塞。"""
        try:
            return int(self.dll.ZCAN_GetReceiveNum(c_ulonglong(self.ch), c_uint(ZCAN_TYPE_CANFD)))
        except Exception:
            return 0

    def transmit_fd(self, can_id: int, data: bytes, ext: bool, brs: bool = True) -> int:
        msg = TransmitFd()
        msg.transmit_type = 0
        msg.frame.can_id = can_id
        msg.frame.eff = 1 if ext else 0
        msg.frame.rtr = 0
        msg.frame.brs = 1 if brs else 0
        msg.frame.len = len(data)
        for i, b in enumerate(data[:64]):
            msg.frame.data[i] = b
        return self.dll.ZCAN_TransmitFD(c_ulonglong(self.ch), byref(msg), c_uint(1))

    def receive_fd(self, count: int = 64, wait_ms: int = 100):
        buf = (ReceiveFd * count)()
        n = self.dll.ZCAN_ReceiveFD(c_ulonglong(self.ch), byref(buf), c_uint(count), c_uint(wait_ms))
        out = []
        for i in range(int(n)):
            f = buf[i].frame
            data = bytes(f.data[j] for j in range(f.len))
            out.append({
                "id": f.can_id,
                "data": data.hex().upper(),
                "ext": bool(f.eff),
                "fd": True,
                "brs": bool(f.brs),
                "ts": buf[i].timestamp,
            })
        return out
