# -*- coding: utf-8 -*-
"""台架测试桥接：外设自检 + SOC/DDR/UFS 应力。

    bench.html ──HTTP/SSE──▶ bridge.py ──▶ 外设通道

默认模拟模式；接真机后 adb / fastboot 走真实命令，其余通道留钩子。
启动： python bridge.py --port 8791 --sim
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import random
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8791
EVENTS: "queue.Queue[str]" = queue.Queue()
SIM = os.environ.get("BENCH_SIM") == "1"

STATE = {"running": False, "stop": threading.Event()}


def emit(payload: dict):
    EVENTS.put(json.dumps(payload, ensure_ascii=False))


def log(msg: str, level: str = "info"):
    emit({"type": "log", "level": level, "msg": msg, "t": round(time.time(), 3)})


def status():
    emit({
        "type": "status",
        "running": STATE["running"],
        "mode": "sim" if SIM else "hw",
        "t": round(time.time(), 3),
    })


# ---------------- 外设自检 ----------------
def run(cmd: list[str], timeout: float = 6.0):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.returncode == 0, (out.stdout or out.stderr or "").strip()
    except Exception as exc:
        return False, str(exc)


CHECKS = {
    "adb": lambda: run(["adb", "get-state"]),
    "fastboot": lambda: run(["fastboot", "devices"]),
    "pcui": lambda: (False, "串口未配置（等待 AT/MMI 指令清单）"),
    "can": lambda: (False, "CAN 通道由 can.html 的桥接管"),
    "eth": lambda: run(["ping", "-n", "1", "-w", "1000", "192.168.1.1"]),
    "ngx": lambda: (False, "NGX 板卡未接入（等待厂商 SDK）"),
    "audio": lambda: (False, "音频板卡未接入"),
    "rf": lambda: (False, "综测仪未接入（等待 SCPI 地址）"),
}


def selfcheck(channel: str):
    time.sleep(0.4)
    if SIM:
        ok, detail = True, "模拟自检通过"
        if channel in ("pcui", "ngx", "audio", "rf"):
            detail = "模拟通过（外设未接入）"
    else:
        fn = CHECKS.get(channel)
        ok, detail = fn() if fn else (False, "未知通道")
    emit({
        "type": "selfcheck", "channel": channel, "ok": ok,
        "detail": detail[:160], "t": round(time.time(), 3),
    })


def selfcheck_all():
    for ch in CHECKS:
        threading.Thread(target=selfcheck, args=(ch,), daemon=True).start()
        time.sleep(0.2)


# ---------------- 应力测试 ----------------
def soc_metrics(p):
    base = 2.4 - p * 1.1
    return {
        "频率": round(max(base, 1.2), 2),
        "结温": round(62 + p * 32, 1),
        "重启": 0,
    }


def ddr_metrics(p):
    return {
        "带宽": round(42 - p * 12, 1),
        "ECC CE": int(p * 9),
        "校验错": 0,
    }


def ufs_metrics(p):
    return {
        "写吞吐": round(620 - p * 240, 0),
        "延迟 P99": round(18 + p * 90, 1),
        "IO 错": 0,
    }


METRICS = {"soc": soc_metrics, "ddr": ddr_metrics, "ufs": ufs_metrics}


def stress_worker(duration: int):
    STATE["running"] = True
    STATE["stop"].clear()
    status()
    log(f"应力测试开始，时长 {duration}s")

    started = time.time()
    kinds = list(METRICS)
    while not STATE["stop"].is_set():
        elapsed = time.time() - started
        pct = min(int(elapsed / duration * 100), 100)
        for kind in kinds:
            metrics = METRICS[kind](pct / 100)
            emit({
                "type": "stress", "kind": kind, "pct": pct, "metrics": metrics,
                "done": pct >= 100,
                "ok": metrics.get("重启", 0) == 0 and metrics.get("校验错", 0) == 0 and metrics.get("IO 错", 0) == 0,
                "detail": f"{pct}% 运行中",
            })
        if pct >= 100:
            break
        time.sleep(1)

    finished_ok = not STATE["stop"].is_set()
    for kind in kinds:
        emit({
            "type": "stress", "kind": kind, "pct": 100 if finished_ok else 0,
            "metrics": METRICS[kind](1.0 if finished_ok else 0),
            "done": True, "ok": finished_ok,
            "detail": "完成" if finished_ok else "手动停止",
        })
    STATE["running"] = False
    status()
    log("应力测试结束" if finished_ok else "应力测试已停止")


def start_stress(duration: int):
    if STATE["running"]:
        log("已有测试在运行", "warn")
        return
    threading.Thread(target=stress_worker, args=(max(10, duration),), daemon=True).start()


def stop_stress():
    STATE["stop"].set()


# ---------------- HTTP / SSE ----------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "running": STATE["running"], "mode": "sim" if SIM else "hw"})
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
                status()
                while True:
                    try:
                        payload = EVENTS.get(timeout=10)
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/cmd":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            req = {}

        cmd = req.get("cmd")
        if cmd == "selfcheck":
            threading.Thread(target=selfcheck, args=(req.get("channel", ""),), daemon=True).start()
        elif cmd == "selfcheck_all":
            threading.Thread(target=selfcheck_all, daemon=True).start()
        elif cmd == "stress":
            if req.get("action") == "stop":
                stop_stress()
            else:
                start_stress(int(req.get("duration", 60)))
        elif cmd == "status":
            status()
        elif cmd == "hello":
            status()

        self._json(200, {"ok": True})

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--sim", action="store_true")
    args = parser.parse_args()
    if args.sim:
        global SIM
        SIM = True

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[bench-bridge] http://127.0.0.1:{args.port}  sim={SIM}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
