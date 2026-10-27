# ZLG CAN 桥接服务

给「周立功 CAN 工具」页面（`can.html`）提供本地硬件通道。

浏览器不能直接加载 `zlgcan.dll`，所以由本进程做桥：

```
can.html  ──HTTP/SSE──▶  bridge.py  ──zlgcan(python)──▶  zlgcan.dll  ──▶  CAN 卡
```

## 为什么用 Python 的 `zlgcan` 包

周立功官方 demo 是 C++（`ZCAN_OpenDevice` → `ZCAN_InitCAN` → `ZCAN_TransmitFD`），
Python 侧成熟的做法是 [`zlgcan`](https://pypi.org/project/zlgcan/) 这个包：
底层是 `zlgcan-driver-rs`，调用的仍是同一个 `zlgcan.dll`，但把结构体、位时序、FD 收发都封装好了。

```bat
pip install -r requirements.txt
```

## 支持设备

| 型号 | 接口 | 通道 | zlgcan 常量 | 值 |
| --- | --- | --- | --- | --- |
| USBCANFD-200U | USB | 2 | `ZCAN_USBCANFD_200U` | 41 |
| CANFDNET-400U-TCP | 以太网 | 4 | `ZCAN_CANFDNET_400U_TCP` | 52 |

## 启动

```bat
:: 有硬件（自动探测 zlgcan.dll 与设备）
python tools\zlg-bridge\bridge.py --port 8790

:: 无硬件（模拟：每秒 3 帧心跳，发送回显）
python tools\zlg-bridge\bridge.py --port 8790 --sim
```

DLL 位置默认按顺序查找：

```
%ZLG_DLL_DIR%
C:\Program Files (x86)\ZLG\CAN
C:\Program Files (x86)\ZLG\CAN\Windows
C:\Program Files\ZLG\CAN
C:\Windows\System32
```

找不到时会在页面里提示「未找到 zlgcan.dll：请安装周立功 CAN 驱动，或设置环境变量 ZLG_DLL_DIR」，
并自动回落到模拟模式，页面其他功能不受影响。

## 接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/health` | 健康检查（connected / mode） |
| GET | `/events` | SSE：`frame` / `status` / `log` 三类事件 |
| POST | `/cmd` | `{"cmd":"open|close|send|status"}` |

```json
{"cmd":"open","device":{"type":"CANFDNET-400U-TCP","ip":"192.168.1.100","port":8000,
  "channel":0,"nominal":500000,"data":2000000,"fd":true}}
```

```json
{"cmd":"send","frames":[{"id":"0x18DA0BF1","data":"3E00","ext":true,"fd":false}]}
```

## 已知限制

- **TCP 设备的 IP/端口**：当前只记录并打印，尚未写入驱动。`zlgcan` 包对 NET 设备的寻址方式
  需对照官方 demo 的 `ZCAN_SetValue("0/ip", ...)` 补一次封装。
- **位时序**：由 `zlgcan` 包按 `bitrate/dbitrate` 计算，若实机通信异常，需要用 ZLG 工具
  生成的寄存器值覆盖。
- 本机未安装周立功驱动，硬件路径只做了「探测 → 明确报错 → 回落模拟」的验证。
