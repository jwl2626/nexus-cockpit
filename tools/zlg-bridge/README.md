# ZLG CAN 桥接服务

给「周立功 CAN 工具」页面（`can.html`）提供本地硬件通道。

浏览器不能直接加载 `zlgcan.dll`，所以由本进程做桥：

```
can.html  ──HTTP/SSE──▶  bridge.py  ──zlgcan / ctypes──▶  zlgcan.dll  ──▶  CAN 卡
```

## 两条驱动路径

| 设备 | 实现 | 原因 |
| --- | --- | --- |
| USBCANFD-200U | `zlgcan` 包（`ZCanBus`） | 高层封装，CANFD 收发开箱可用 |
| CANFDNET-400U-TCP | `zlg_ctypes.py`（ctypes 直调 DLL） | 必须先 `ZCAN_OpenDevice` 再 `ZCAN_SetValue` 写 IP/端口，高层包不暴露设备句柄 |

TCP 连接流程（对应官方 C++ 例程）：

```python
dll.open_device(52, 0)                  # ZCAN_CANFDNET_400U_TCP
dll.set_value("0/ip", "192.168.1.100")  # 设备侧参数，键名以官方手册为准
dll.set_value("0/port", "8000")
dll.init_canfd(channel, 500000, 2000000)
dll.transmit_fd(0x18DA0BF1, bytes.fromhex("3E00"), ext=True)
```

每个 `SetValue` 的返回值都会打到页面日志（`SetValue 0/ip=... -> 1` 表示成功）。
接实机时看这一行就能判断参数名对不对；不对就改 `zlg_ctypes.py` / `_open_ctypes` 里的键名。

## 安装与启动

```bat
pip install -r requirements.txt

:: 有硬件（自动探测 DLL 与设备）
python tools\zlg-bridge\bridge.py --port 8790

:: 无硬件
python tools\zlg-bridge\bridge.py --port 8790 --sim
```

DLL 查找顺序：

```
%ZLG_DLL_DIR%
C:\Program Files (x86)\ZLG\CAN
C:\Program Files (x86)\ZLG\CAN\Windows
C:\Program Files\ZLG\CAN
C:\Windows\System32
```

找不到时页面提示「未找到 zlgcan.dll：请安装周立功 CAN 驱动，或设置 ZLG_DLL_DIR」，并回落模拟模式。

## 接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/health` | 健康检查（connected / mode） |
| GET | `/events` | SSE：`frame` / `status` / `log` |
| POST | `/cmd` | `{"cmd":"open|close|send|status"}` |

```json
{"cmd":"open","device":{"type":"CANFDNET-400U-TCP","ip":"192.168.1.100","port":8000,
  "channel":0,"nominal":500000,"data":2000000,"fd":true}}
```

## 已知限制

- **SetValue 键名**：`0/ip`、`0/port`、`0/tcp_port` 三个都试，以官方手册为准；
  本机未装驱动，只验证了「找不到 DLL → 提示 → 回落模拟」这条路径。
- **位时序**：用 `canfd_abit_baud_rate` / `canfd_dbit_baud_rate` 设置；实机异常时用 ZLG 工具
  生成的寄存器值覆盖。
- 官方 PDF 手册下载时被反爬拦截（返回 HTML），接口细节依据社区对官方 C++ 例程的 Python 移植。
