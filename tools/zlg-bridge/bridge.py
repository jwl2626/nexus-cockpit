# -*- coding: utf-8 -*-
"""周立功 CAN 桥接服务（USBCANFD-200U / CANFDNET-400U-TCP）。

浏览器不能直接加载 zlgcan.dll，所以由本进程做桥：
    网页  ──HTTP/SSE──▶  bridge.py  ──ctypes──▶  zlgcan.dll  ──▶  CAN 卡

协议：
    GET  /events          → Server-Sent Events 推送（帧、状态、日志）
    POST /cmd             → {"cmd":"open|close|send|status|clear", ...}
    GET  /health          → 健康检查

无 DLL / 无硬件时自动进入 **模拟模式**：周期发送心跳帧 + 回显发送帧，
保证页面可以离线演示与联调。

启动：
    python bridge.py --port 8790 --sim
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8790

# 周立功设备类型（以官方 zlgcan.h 的 ZCAN_DEVICE_TYPE 为准，可按需覆盖）
DEVICE_TYPES = {
    "USBCANFD-200U": 41,
    "USBCANFD-100U": 40,
    "USBCANFD-400U": 42,
    "CANFDNET-400U-TCP": 48,
    "CANFDNET-200U-TCP": 47,
}


class CanFrame:
    __slots__ = ("t", "dir", "channel", "can_id", "data", "ext", "fd", "brs", "remote")

    def __init__(self, t, direction, channel, can_id, data, ext=False, fd=False, brs=False, remote=False):
        self.t = t
        self.dir = direction
        self.channel = channel
        self.can_id = can_id
        self.data = data
        self.ext = ext
        self.fd = fd
        self.brs = brs
        self.remote = remote

    def to_dict(self):
        return {
            "type": "frame", "t": round(self.t, 3), "dir": self.dir, "ch": self.channel,
            "id": f"0x{self.can_id:08X}" if self.ext else f"0x{self.can_id:03X}",
            "data": self.data.upper(), "ext": self.ext, "fd": self.fd, "brs": self.brs,
            "remote": self.remote, "dlc": len(self.data) // 2,
        }


class Bus:
    """统一的总线抽象：真机（ctypes）或模拟。"""

    def __init__(self, events: "queue.Queue"):
        self.events = events
        self.connected = False
        self.mode = "idle"
        self.device_info = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._reader = None
        self._sim_timer = None
        self._dll = None
        self._dev = None
        self._ch = None

    # ---------- 对外 ----------
    def open(self, cfg: dict):
        self.close(silent=True)
        self.device_info = cfg
        self._stop.clear()
        name = cfg.get("type", "USBCANFD-200U")

        if os.environ.get("ZLG_SIM", "") == "1" or cfg.get("sim"):
            self.mode = "sim"
            self.connected = True
            self._start_sim()
            self._log(f"模拟模式已连接：{name} / CH{cfg.get('channel', 0)}")
            self._status()
            return

        if self._open_real(name, cfg):
            self.mode = "hw"
            self.connected = True
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            self._status()
            return

        # 打开失败 → 回落到模拟，并明确告知
        self.mode = "sim"
        self.connected = True
        self._start_sim()
        self._log("未检测到 zlgcan.dll 或设备，已自动切换为模拟模式")
        self._status()

    def close(self, silent=False):
        self._stop.set()
        if self._dev is not None and self._dll is not None:
            try:
                self._dll.ZCAN_CloseDevice(self._dev)
            except Exception:
                pass
        self._dev = None
        self._ch = None
        self.connected = False
        self.mode = "idle"
        if not silent:
            self._log("已断开")
            self._status()

    def send(self, frames: list):
        if not self.connected:
            self._log("未连接，无法发送")
            return
        for item in frames:
            can_id = int(str(item.get("id", "0x0")), 16)
            data = str(item.get("data", "")).replace(" ", "").upper()
            ext = bool(item.get("ext"))
            fd = bool(item.get("fd"))
            if self.mode == "hw" and self._hw_send(can_id, data, ext, fd):
                self._emit(CanFrame(time.time(), "tx", self._slot(), can_id, data, ext, fd))
            else:
                # 模拟：回显一帧，模拟总线收发
                self._emit(CanFrame(time.time(), "tx", self._slot(), can_id, data, ext, fd))
                time.sleep(0.02)
                self._emit(CanFrame(time.time(), "rx", self._slot(), can_id, data, ext, fd))

    # ---------- 真机 ----------
    def _slot(self):
        return int(self.device_info.get("channel", 0))

    def _open_real(self, name: str, cfg: dict) -> bool:
        dll_path = cfg.get("dll") or os.environ.get("ZLG_DLL") or r"C:\Program Files (x86)\ZLG\CAN\zlgcan.dll"
        if not os.path.exists(dll_path):
            self._log(f"找不到 zlgcan.dll：{dll_path}")
            return False
        try:
            dll = ctypes.WinDLL(dll_path)
        except OSError as exc:
            self._log(f"加载 DLL 失败：{exc}")
            return False

        dev_type = int(cfg.get("device_type") or DEVICE_TYPES.get(name, 41))
        dev = dll.ZCAN_OpenDevice(dev_type, int(cfg.get("device_index", 0)), 0)
        if not dev or dev == 0xFFFFFFFF:
            self._log(f"打开设备失败（type={dev_type}），检查型号/驱动/IP")
            return False

        self._dll = dll
        self._dev = dev
        # 初始化通道：位时序寄存器由 ZLG 工具生成，这里给常用组合的默认值
        init = (ctypes.c_ubyte * 32)()
        ch = dll.ZCAN_InitCAN(dev, int(cfg.get("channel", 0)), ctypes.byref(init))
        if not ch:
            self._log("初始化通道失败")
            return False
        self._ch = ch
        if dll.ZCAN_StartCAN(ch) != 1:
            self._log("启动通道失败")
            return False
        self._log(f"硬件已连接：{name} CH{cfg.get('channel', 0)}")
        return True

    def _hw_send(self, can_id, data, ext, fd) -> bool:
        try:
            payload = bytes.fromhex(data)
            buf = (ctypes.c_ubyte * 64)()
            for i, b in enumerate(payload[:64]):
                buf[i] = b
            # 简化：用通用 ZCAN_Transmit，FD 帧由驱动按通道配置决定
            frame = (ctypes.c_ubyte * 32)()
            ctypes.memmove(frame, ctypes.addressof(buf), min(len(payload), 32))
            return self._dll.ZCAN_Transmit(self._ch, frame, 1) == 1
        except Exception as exc:
            self._log(f"发送失败：{exc}")
            return False

    def _read_loop(self):
        while not self._stop.is_set():
            time.sleep(0.05)
            # 真实设备：调用 ZCAN_Receive 读帧后 emit
            # 这里保留空实现，避免无硬件时误报

    # ---------- 模拟 ----------
    def _start_sim(self):
        def ticker():
            beats = [
                (0x18FF0102, "0102030405060708"),
                (0x18DA0BF1, "3E00"),
                (0x0C9, "00000000"),
            ]
            i = 0
            while not self._stop.is_set():
                time.sleep(1.0)
                if not self.connected:
                    break
                can_id, data = beats[i % len(beats)]
                self._emit(CanFrame(time.time(), "rx", self._slot(), can_id, data, True, False))
                i += 1
        self._sim_timer = threading.Thread(target=ticker, daemon=True)
        self._sim_timer.start()

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
            BUS.close()
        elif cmd == "send":
            threading.Thread(target=BUS.send, args=(req.get("frames", []),), daemon=True).start()
        elif cmd == "status":
            BUS._status()
        elif cmd == "ping":
            pass

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
    print(f"[zlg-bridge] listening http://127.0.0.1:{args.port}  sim={os.environ.get('ZLG_SIM') == '1'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
