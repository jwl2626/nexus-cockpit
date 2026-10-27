# 座舱诊断台架 · 外设与通道方案

> 目标：把「一个网页」变成「一台诊断仪的界面」。PC 侧挂 6 类外设，每类抽象成一条**通道**，
> 通道统一上报「测量值 / 事件 / 原始证据」，诊断网站只认通道，不认具体硬件。

---

## 一、总体拓扑

```
                        ┌──────────────────────── PC（诊断台架）────────────────────────┐
                        │                                                              │
   座舱域控 ──USB──────▶ │ adb      调试 / logcat / dumpsys / 文件拉取                    │
            ──USB──────▶ │ fastboot 刷机 / 读写 NV / 分区备份                             │
            ──PCUI─────▶ │ 串口     AT 指令 / MMI 指令 / 底层日志（UART）                  │
            ──CAN──────▶ │ CAN      UDS 诊断 → MCU → 透传 SOC / MCU 直接动作（复位等）     │
            ──以太─────▶ │ ETH      打流 / 抓包 / PTP / DoIP                             │
   屏/摄像头 ──TI 解串─▶ │ NGX      解串器出图抓取与图像质量分析                          │
   音响系统 ──音频线───▶ │ AUDIO    MIC 采集 / 喇叭回放 / THD+N / 通道识别                │
                        │                                                              │
                        │  channel bus（统一 JSON）→ 诊断网站 / 8D 报告                  │
                        └──────────────────────────────────────────────────────────────┘
```

---

## 二、通道抽象

所有外设实现同一个接口，网页与规则引擎只依赖它：

```json
{
  "channel": "adb",
  "device": "NEXUS-E7-0A1B",
  "cmd": "shell logcat -d -b crash -t 200",
  "t": 1793123371.877,
  "ok": true,
  "raw": "...",
  "parsed": { "fatal": 0, "anr": 1 },
  "cost_ms": 213
}
```

六条通道的差异只在「怎么连、怎么发、怎么解析」，上层（页面 / 规则 / 8D）完全一致。

| 通道 | 传输 | 典型命令/协议 | 采样 |
| --- | --- | --- | --- |
| `adb` | USB | `adb shell`、`logcat`、`dumpsys`、`pull` | 1–60s |
| `fastboot` | USB | `getvar`、`flash`、`oem`、NV 读写 | 按操作 |
| `pcui` | 串口 | AT 指令、MMI 指令、UART 日志 | 交互 |
| `can` | CAN(FD) | UDS（10/22/27/2E/31/3E）、MCU 私有命令 | 10ms–1s |
| `eth` | 以太网 | 打流、抓包、ping、DoIP 13400、PTP | 持续 |
| `ngx` | 采集卡 | TI 解串器出图、帧率/误码/图像质量 | 每帧 |
| `audio` | 声卡 | MIC 采集、喇叭回放、扫频、THD+N | 按测试 |

---

## 三、逐通道设计

### 1. USB · adb（调试与日志）

| 用途 | 命令 |
| --- | --- |
| 在线检测 | `adb devices -l`、`getprop sys.boot_completed` |
| 日志抓取 | `logcat -b all -v threadtime`、`dmesg`、`logcat -b crash` |
| 服务状态 | `dumpsys activity services`、`dumpsys media.audio_flinger` |
| 指标 | `dumpsys meminfo`、`/proc/stat`、`df /data` |
| 文件 | `adb pull /data/tombstones`、`adb pull /sdcard/logs` |

要点：**优先用 `adb exec-out`**（二进制安全），日志按 5–10s 批量回传，避免高频单条。

### 2. USB · fastboot（刷写与 NV）

| 用途 | 命令 |
| --- | --- |
| 设备识别 | `fastboot devices`、`getvar product/slot/secure` |
| 刷写 | `fastboot flash boot boot.img`（接 `fastbootCmds` 可多机并行） |
| NV 读写 | `fastboot oem readnv <id>` / `oem writenv <id> <hex>`（按厂商定义） |
| 分区备份 | `fastboot fetch <partition> out.img` |

要点：NV 写入属于**高危写操作**，必须：先备份 → 写入 → 读回校验 → 记录原值，全程进审计日志。

### 3. PCUI 串口（AT / MMI）

| 用途 | 命令 |
| --- | --- |
| 模组状态 | `AT+CPIN?`、`AT+CSQ`、`AT+COPS?` |
| 网络注册 | `AT+CREG?`、`AT+CGATT?` |
| 座舱私有 | `MMI,<cmd>,<args>`（按项目定义） |
| 底层日志 | UART 直出（bootloader / kernel early log） |

要点：串口独占，需要有**会话锁**；AT 与 MMI 用不同终止符（CR/LF），要可配。

### 4. CAN · 周立功（诊断报文 → MCU）

链路是两段，必须分开定位：

```
PC ──CAN──▶ MCU ──SPI/内部总线──▶ SOC
             │
             └─ 也可由 MCU 直接执行：复位 SOC / 断电 / 进入 EDL
```

| 场景 | 报文 | 判据 |
| --- | --- | --- |
| 会话保持 | `3E 00` → `7E 00` | 响应 ≤ 50ms |
| 读 DID | `22 F1 90`（VIN）等 | 正响应 + 数据长度 |
| 写配置 | `2E <DID> <data>` | 正响应 + 读回一致 |
| 例程控制 | `31 01 <RID>`（如自检） | 结果码 |
| MCU 动作 | 私有 ID（复位/断电/切 EDL） | 执行结果 + SOC 心跳变化 |

要点：**MCU 动作类命令要双确认**（页面二次弹窗），执行后必须等待 SOC 心跳恢复，超时判失败。

### 5. 以太 · 打流仪（报文监控）

| 用途 | 方式 |
| --- | --- |
| 抓包 | 端口镜像 + `dumpcap`/`tshark`，按 VLAN/端口过滤 |
| 打流 | 按 pps/带宽构造背景流，观察丢包与时延 |
| 健康 | `ping`、`ethtool -S`、`ptp4l` 状态、DoIP 13400 |

要点：打流与抓包**同时进行**会互相影响，需在报告里标注“带流测试 / 纯监听”模式。

### 6. NGX 板卡（TI 解串器出图）

| 用途 | 说明 |
| --- | --- |
| 出图抓取 | 采集解串器输出帧，落地 PNG/RAW |
| 链路质量 | 解串器寄存器：LOCK、CRC、误码计数、眼图（若支持） |
| 图像分析 | 黑屏/花屏/偏色/冻结检测：亮度直方图、帧差、色彩偏移 |

要点：与显示模块的 `SerDes 锁定` 指标联动——链路失锁时抓图，作为 8D 的视觉证据。

### 7. 音频板卡（MIC / 喇叭）

| 用途 | 指标 |
| --- | --- |
| MIC 采集 | 灵敏度（dBFS）、底噪、频响、通道顺序 |
| 喇叭回放 | THD+N、响度、扫频响应、异音检测 |
| 通道识别 | 逐声道播放 1kHz，确认无串音/无声 |

要点：测试音用 1kHz 0dBFS + 粉噪，环境底噪需先测基线。

---

## 四、与诊断网站的映射

| 网站位置 | 数据来源 |
| --- | --- |
| 顶部“设备在线” | `adb devices` + 各通道握手 |
| 模块卡片指标 | 对应通道的 parsed 值（如 `display.serdes` ← `ngx`） |
| 异常时间轴 | 规则引擎基于通道事件生成（`DISP_SERDES_UNLOCK` 等） |
| 8D 报告 | 事件 + 原始证据（截图、抓包、日志行） |
| 新增「台架」页 | 六通道在线状态、版本、最后一次操作记录 |

建议新增一页 **外设台架（Bench）**：左侧六通道状态灯，右侧每通道的最近 20 条操作与结果，
外加一个“一键自检”按钮（依次探测 adb / fastboot / 串口 / CAN / 以太 / NGX / 音频）。

---

## 五、实施顺序（按“不依赖供应商”优先）

| 阶段 | 内容 | 依赖 |
| --- | --- | --- |
| 1 | adb 通道（在线、logcat、dumpsys、拉文件） | 只要 USB |
| 2 | fastboot 通道（读 var、备份、刷写、NV 读写） | 只要 USB + fastbootCmds |
| 3 | CAN 通道（UDS 收发、MCU 动作） | 周立功 + MCU 协议 |
| 4 | 以太通道（抓包、ping、DoIP） | 网卡/镜像口 |
| 5 | 串口 PCUI（AT / MMI） | 串口线 + 指令集 |
| 6 | NGX / 音频 | 专用板卡 + 供应商接口 |

---

## 六、待补

- 第 6 类外设（用户列表未完成）
- MCU 私有命令表（复位/断电/EDL 的报文定义）
- PCUI 的 AT / MMI 指令清单与终止符约定
- NGX 板卡的采集接口（厂商 SDK？文件落盘？）
