# -*- coding: utf-8 -*-
"""周立功 CAN 桥接服务（USBCANFD-200U / CANFDNET-400U-TCP）。

浏览器不能直接加载 zlgcan.dll，所以由本进程做桥：
    网页  ──HTTP/SSE──▶  bridge.py  ──zlgcan(python)──▶  zlgcan.dll  ──▶  CAN 卡

硬件层使用 Python 生态的 `zlgcan` 包（底层为 zlgcan-driver-rs，与官方 C++ demo 同一套 DLL）：
    pip install zlgcan

无该包 / 无硬件时自动进入**模拟模式**（周期心跳 + 发送回显），页面无需改动。

启动：
    python bridge.py --port 8790          # 自动探测硬件
    python bridge.py --port 8790 --sim    # 强制模拟
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8790

# 页面型号 → zlgcan.ZCANDeviceType 常量名（数值以官方头文件为准：200U=41，400U-TCP=52）
DEVICE_CONST = {
    "USBCANFD-200U": "ZCAN_USBCANFD_200U",
    "USBCANFD-100U": "ZCAN_USBCANFD_100U",
    "USBCANFD-400U": "ZCAN_USBCANFD_400U",
    "CANFDNET-400U-TCP": "ZCAN_CANFDNET_400U_TCP",
    "CANFDNET-200U-TCP": "ZCAN_CANFDNET_200U_TCP",
}


class CanFrame:
    __slots__ = ("t", "dir", "channel", "can_id", "data", "ext", "fd")

    def __init__(self, t, direction, channel, can_id, data, ext=False, fd=False):
        self.t, self.dir, self.channel = t, direction, channel
        self.can_id, self.data, self.ext, self.fd = can_id, data, ext, fd

    def to_dict(self):
        return {
            "type": "frame", "t": round(self.t, 3), "dir": self.dir, "ch": self.channel,
            "id": f"0x{self.can_id:08X}" if self.ext else f"0x{self.can_id:03X}",
            "data": self.data.upper(), "ext": self.ext, "fd": self.fd,
            "brs": False, "remote": False, "dlc": len(self.data) // 2,
        }


DLL_CANDIDATES = [
    r"C:\Program Files (x86)\ZLG\CAN",
    r"C:\Program Files (x86)\ZLG\CAN\Windows",
    r"C:\Program Files\ZLG\CAN",
    r"C:\Windows\System32",
]


def find_dll_dir():
    """定位 zlgcan.dll 所在目录（周立功驱动安装后才有）。"""
    env = os.environ.get("ZLG_DLL_DIR")
    if env and os.path.isdir(env):
        return env
    for folder in DLL_CANDIDATES:
        try:
            if os.path.isdir(folder) and any(
                name.lower().startswith("zlgcan") and name.lower().endswith(".dll")
                for name in os.listdir(folder)
            ):
                return folder
        except OSError:
            continue
    return None


class Bus:
    def __init__(self, events: "queue.Queue"):
        self.events = events
        self.connected = False
        self.mode = "idle"
        self.device_info = {}
        self._stop = threading.Event()
        self._reader = None
        self._sim = None
        self._bus = None
        self._dll = None

    # ---------- 连接 ----------
    def open(self, cfg: dict):
        self.close(silent=True)
        self.device_info = cfg
        self._stop.clear()
        name = cfg.get("type", "USBCANFD-200U")

        if os.environ.get("ZLG_SIM") == "1" or cfg.get("sim"):
            self._start_sim(name)
            return

        if self._open_real(name, cfg):
            self.mode = "hw"
            self.connected = True
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            self._status()
            return

        self._start_sim(name, reason="未检测到 zlgcan 包或设备，已自动切换为模拟模式")

    def _start_sim(self, name, reason=None):
        self.mode = "sim"
        self.connected = True
        self._sim = threading.Thread(target=self._sim_loop, daemon=True)
        self._sim.start()
        self._log(reason or f"模拟模式已连接：{name} / CH{self._slot()}")
        self._status()

    def close(self, silent=False):
        self._stop.set()
        if self._dll is not None:
            try:
                self._dll.close_device()
            except Exception:
                pass
            self._dll = None
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None
        self.connected = False
        self.mode = "idle"
        if not silent:
            self._log("已断开")
            self._status()

    # ---------- 发送 ----------
    def send(self, frames: list):
        if not self.connected:
            self._log("未连接，无法发送")
            return
        for item in frames:
            can_id = int(str(item.get("id", "0x0")), 16)
            data = str(item.get("data", "")).replace(" ", "").upper()
            ext, fd = bool(item.get("ext")), bool(item.get("fd"))
            ok = self._hw_send(can_id, data, ext, fd) if self.mode == "hw" else True
            if not ok:
                continue
            self._emit(CanFrame(time.time(), "tx", self._slot(), can_id, data, ext, fd))
            if self.mode == "sim":
                time.sleep(0.02)
                self._emit(CanFrame(time.time(), "rx", self._slot(), can_id, data, ext, fd))

    # ---------- 硬件 ----------
    def _slot(self):
        return int(self.device_info.get("channel", 0))

    def _open_real(self, name: str, cfg: dict) -> bool:
        try:
            from zlgcan import ZCanBus, ZCANDeviceType
        except Exception as exc:
            self._log(f"未安装 zlgcan 包（pip install zlgcan）：{exc}")
            return False

        const_name = DEVICE_CONST.get(name, "ZCAN_USBCANFD_200U")
        dev_type = int(cfg.get("device_type") or getattr(ZCANDeviceType, const_name, 41))

        dll_dir = find_dll_dir()
        if dll_dir is None:
            self._log("未找到 zlgcan.dll：请安装周立功 CAN 驱动，或设置环境变量 ZLG_DLL_DIR 指向 DLL 目录")
            return False

        # TCP 型设备：需要 OpenDevice 后用 ZCAN_SetValue 写 IP/端口，
        # 高层包 zlgcan 不暴露句柄，这里直接走 ctypes
        if name.endswith("-TCP"):
            return self._open_ctypes(name, cfg, dll_dir)
        bitrate = int(cfg.get("nominal", 500000))
        dbitrate = int(cfg.get("data", 2000000)) if cfg.get("fd") else None
        ch = int(cfg.get("channel", 0))

        chl_cfg = {"bitrate": bitrate, "resistance": True}
        if dbitrate:
            chl_cfg["dbitrate"] = dbitrate
            chl_cfg["chl_type"] = 1  # CANFD_ISO

        try:
            self._bus = ZCanBus(
                channel=[ch],
                libpath=dll_dir.rstrip("\\/") + os.sep,
                device_type=dev_type,
                device_index=int(cfg.get("device_index", 0)),
                configs=[chl_cfg],
            )
        except Exception as exc:
            self._log(f"打开设备失败：{exc}")
            return False

        addr = f" @ {cfg.get('ip')}:{cfg.get('port', 8000)}" if name.endswith("-TCP") else ""
        self._log(f"硬件已连接：{name} CH{ch}{addr}")
        return True

    def _open_ctypes(self, name: str, cfg: dict, dll_dir: str) -> bool:
        try:
            from zlg_ctypes import ZCAN_CANFDNET_400U_TCP, ZCAN_USBCANFD_200U, ZlgDll
        except Exception as exc:
            self._log(f"加载 zlg_ctypes 失败：{exc}")
            return False

        try:
            dll = ZlgDll(dll_dir)
        except Exception as exc:
            self._log(f"加载 zlgcan.dll 失败：{exc}")
            return False

        dev_type = ZCAN_CANFDNET_400U_TCP if name.endswith("-TCP") else ZCAN_USBCANFD_200U
        if not dll.open_device(dev_type, int(cfg.get("device_index", 0))):
            self._log(f"打开设备失败（device_type={dev_type}），检查型号 / 网络 / 驱动")
            return False

        ip = str(cfg.get("ip") or "").strip()
        port = str(cfg.get("port") or 8000)
        if ip:
            # 设备侧参数：路径形如 "通道/参数名"，以官方手册为准
            for key, value in (("0/ip", ip), ("0/port", port), ("0/tcp_port", port)):
                rc = dll.set_value(key, value)
                self._log(f"SetValue {key}={value} -> {rc}")

        ch = int(cfg.get("channel", 0))
        abit = int(cfg.get("nominal", 500000))
        dbit = int(cfg.get("data", 2000000)) if cfg.get("fd") else 0
        if not dll.init_canfd(ch, abit, dbit):
            self._log("初始化 / 启动通道失败")
            dll.close_device()
            return False

        self._dll = dll
        self._log(f"硬件已连接（ctypes）：{name} CH{ch} @ {ip}:{port}")
        return True

    def _hw_send(self, can_id, data, ext, fd) -> bool:
        if self._dll is not None:
            try:
                payload = bytes.fromhex(data)
                return self._dll.transmit_fd(can_id, payload, ext, brs=fd) == 1
            except Exception as exc:
                self._log(f"发送失败（ctypes）：{exc}")
                return False
        try:
            import can
            msg = can.Message(
                arbitration_id=can_id,
                data=bytes.fromhex(data),
                is_extended_id=ext,
                is_fd=fd,
            )
            self._bus.send(msg, timeout=0.5)
            return True
        except Exception as exc:
            self._log(f"发送失败：{exc}")
            return False

    def _read_loop(self):
        if self._dll is not None:
            while not self._stop.is_set():
                try:
                    pending = self._dll.receive_num()
                    if pending <= 0:
                        time.sleep(0.02)
                        continue
                    for frame in self._dll.receive_fd(min(pending, 64), 50):
                        self._emit(CanFrame(
                            time.time(), "rx", self._slot(), frame["id"], frame["data"],
                            frame["ext"], frame["fd"],
                        ))
                except Exception as exc:
                    self._log(f"接收异常（ctypes）：{exc}")
                    time.sleep(0.5)
            return

        while not self._stop.is_set():
            try:
                msg = self._bus.recv(timeout=0.2)
            except Exception as exc:
                self._log(f"接收异常：{exc}")
                time.sleep(0.5)
                continue
            if msg is None:
                continue
            self._emit(CanFrame(
                time.time(), "rx", self._slot(), msg.arbitration_id,
                bytes(msg.data).hex().upper(), msg.is_extended_id,
                bool(getattr(msg, "is_fd", False)),
            ))

    # ---------- 模拟 ----------
    def _sim_loop(self):
        beats = [
            (0x18FF0102, "0102030405060708", True),
            (0x18DA0BF1, "3E00", True),
            (0x0C9, "00000000", False),
        ]
        i = 0
        while not self._stop.is_set():
            time.sleep(1.0)
            if not self.connected:
                break
            can_id, data, ext = beats[i % len(beats)]
            self._emit(CanFrame(time.time(), "rx", self._slot(), can_id, data, ext, False))
            i += 1

    # ---------- 事件 ----------
    def _emit(self, frame: CanFrame):
        self.events.put(json.dumps(frame.to_dict(), ensure_ascii=False))

    def _log(self, msg: str):
        self.events.put(json.dumps({"type": "log", "t": round(time.time(), 3), "msg": msg}, ensure_ascii=False))

    def _status(self):
        self.events.put(json.dumps({
            "type": "status", "connected": self.connected, "mode": self.mode,
            "device": self.device_info, "t": round(time.time(), 3),
        }, ensure_ascii=False))


BUS = Bus(queue.Queue())


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"ok": True, "connected": BUS.connected, "mode": BUS.mode}).encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/events":
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        payload = BUS.events.get(timeout=10)
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            return

        self.send_response(404)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.path != "/cmd":
            self.send_response(404)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception:
            req = {}

        cmd = req.get("cmd")
        if cmd == "open":
            threading.Thread(target=BUS.open, args=(req.get("device", {}),), daemon=True).start()
        elif cmd == "close":
            BUS.close(silent=bool(req.get("silent")))
        elif cmd == "send":
            threading.Thread(target=BUS.send, args=(req.get("frames", []),), daemon=True).start()
        elif cmd == "status":
            BUS._status()

        body = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--sim", action="store_true", help="强制模拟模式")
    args = parser.parse_args()
    if args.sim:
        os.environ["ZLG_SIM"] = "1"

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[zlg-bridge] http://127.0.0.1:{args.port}  sim={os.environ.get('ZLG_SIM') == '1'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
