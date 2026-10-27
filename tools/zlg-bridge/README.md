# ZLG CAN 桥接服务

给「周立功 CAN 工具」页面（`can.html`）提供本地硬件通道。

浏览器不能直接加载 `zlgcan.dll`，所以由本进程做桥：

```
can.html  ──HTTP/SSE──▶  bridge.py  ──ctypes──▶  zlgcan.dll  ──▶  CAN 卡
```

## 支持设备

| 型号 | 接口 | 说明 |
| --- | --- | --- |
| USBCANFD-200U | USB | 需装周立功官方驱动 + zlgcan.dll |
| CANFDNET-400U-TCP | 以太网 | 同一 DLL，按 IP 寻址 |

型号 → 设备类型编号见 `bridge.py` 的 `DEVICE_TYPES`，与官方 `zlgcan.h` 的 `ZCAN_DEVICE_TYPE` 对齐；若有偏差可在页面/环境变量里覆盖。

## 启动

```bat
:: 有硬件
python tools\zlg-bridge\bridge.py --port 8790

:: 无硬件（模拟：每秒发 3 帧心跳，发送回显）
python tools\zlg-bridge\bridge.py --port 8790 --sim
```

打开 `can.html`（建议用本地静态服务，避免 `file://` 下 SSE 被浏览器拦截）：

```bat
python -m http.server 8080
:: 浏览器访问 http://127.0.0.1:8080/can.html
```

## 接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/events` | SSE：`frame` / `status` / `log` 三类事件 |
| POST | `/cmd` | `{"cmd":"open|close|send|status"}` |

`open` 参数：

```json
{"cmd":"open","device":{"type":"USBCANFD-200U","channel":0,"nominal":500000,"data":2000000,"fd":true}}
```

`send` 参数：

```json
{"cmd":"send","frames":[{"id":"0x18DA0BF1","data":"3E00","ext":true,"fd":false}]}
```

## 已知限制

- 位时序寄存器当前用默认值，接入实机需按 500k/2M 等组合填入 ZLG 工具生成的参数；
- 只实现了 `ZCAN_Transmit` 的标准帧发送，CAN FD 帧（`ZCAN_TransmitFD`）与接收循环（`ZCAN_Receive`）待按实机补全；
- 模拟模式与硬件模式对外接口一致，页面无需改动即可切换。
