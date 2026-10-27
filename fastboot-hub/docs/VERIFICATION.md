# 可行性验证记录

验证时间：2026-10-26  
验证环境：Windows 10 19045 x64，Python 3.10.1，fastboot.exe 位于 `D:\platform-tools`

> 当前没有连接 Android 真机，因此**实际 fastboot 握手、刷写**尚未验证；下面是可以在无设备条件下验证的部分，以及明天上机时的检查步骤。

## 已验证

### 1. USB 枚举与物理路径（真实 USB 设备）

本机连接了 3 个普通 USB 设备（非 fastboot）。运行：

```bat
python -m fbhub doctor
```

能够枚举出：

```text
1D00:0-1.6
1D00:0-1.3
1A00:0-1.2
```

并正确解析 Windows 的：

```text
PCIROOT(0)#PCI(1D00)#USBROOT(0)#USB(1)#USB(6)
```

说明：

- SetupAPI 枚举、`CreateFile`、`WinUsb_Initialize`、接口/端点查询这条链路可运行；
- `DEVPKEY_Device_LocationPaths` 解析出的“控制器:根HUB-端口链”符合预期；
- 非 WinUSB 设备会被跳过（`WinUsb_Initialize failed ... 没有使用 WinUSB 驱动`），不会导致崩溃；
- 当前机器没有 fastboot 接口，因此 `fastboot` 计数为 0 是正常的。

### 2. Fastboot 协议（模拟 transport）

用脚本化 transport 验证：

- `getvar`
- `download` + `flash`
- `FAIL` 处理
- `INFO` 处理
- `reboot` / `reboot-bootloader`
- 读超时
- `max-download-size` 缺省值
- AVB footer 从镜像末尾移动到分区末尾

### 3. Sparse 编码与分片（纯算法）

- raw → sparse → 还原，逐字节一致；
- 已有 sparse → 重新分片 → 还原，逐字节一致；
- 零块用 FILL、非零块用 RAW、DONT_CARE 跳过；
- 每个分片长度 ≤ `max-download-size`；
- 末块不足 4096 字节时补零；
- 2.4 GiB FILL 块会被拆成多个合法 chunk（`chunk_sz` 不超过 uint32）。

### 4. 多设备调度

- 多台设备并行执行；
- 单台失败不影响其他设备；
- `reboot` 后跳过后续步骤；
- dry-run 不连接 USB；
- 设备选择（`--all` / `--path` / `--alias` / `--hub` / `--index`）。

### 5. CLI / GUI

- `fbhub --help`、`list`、`doctor`、`flash --dry-run`、`run --dry-run`、`alias` 均可运行；
- GUI 可以启动、显示设备表格、勾选、模拟任务进度和成功/失败状态；
- 界面截图见 `docs/gui.png`。

### 6. 测试结果

```text
Ran 30 tests ... OK
```

## 尚未验证（需要真机）

1. Android bootloader 是否把 fastboot 接口暴露为 WinUSB；
2. `WinUsb_Initialize` 能否成功打开该接口；
3. 实际 `getvar` 响应格式、`download`/`flash` 写入；
4. 设备对 sparse 分片的接受程度；
5. 多台设备同时刷写的 USB 带宽/稳定性。

## 明天上机步骤

### 第一步：确认能看到设备

```bat
python -m fbhub doctor
python -m fbhub list
```

期望：

- `doctor` 的 WinUSB 接口里出现 `FASTBOOT`；
- `list` 显示 USB 路径，且 `SN=-`（设备没写 SN 时）。

如果 `doctor` 显示：

```text
WinUsb_Initialize failed: ... 没有使用 WinUSB 驱动
```

说明驱动不是 WinUSB，本工具无法直接访问。需要安装 Google USB Driver / 厂商 WinUSB 驱动，或先用 `fastboot.exe` 确认设备本身可用。

### 第二步：只读命令

```bat
python -m fbhub getvar version --path 1D00:0-1.3
python -m fbhub getvar current-slot --path 1D00:0-1.3
```

确认能收到 `OKAY` 和变量值。

### 第三步：dry-run 预览

```bat
python -m fbhub flash boot boot.img --path 1D00:0-1.3 --dry-run
```

### 第四步：先刷一个小分区

```bat
python -m fbhub flash boot boot.img --path 1D00:0-1.3 --yes
```

成功后再尝试多台：

```bat
python -m fbhub flash boot boot.img --all --yes
```

### 第五步：计划/大镜像

```bat
python -m fbhub plan examples/plan.example.json --all --dry-run
python -m fbhub plan examples/plan.example.json --all --yes
```

## 主要风险

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| 设备驱动不是 WinUSB | 工具枚举不到/打不开 | 安装 WinUSB 驱动；`doctor` 会明确报错 |
| 设备是复合设备且 fastboot 功能未注册 USB 接口 GUID | 可能枚举不到 | 先用 `doctor` 对照 `fastboot devices`；必要时可扩展枚举逻辑 |
| fastboot 响应格式与 AOSP 有差异 | 读取失败 | 抓 `doctor`/日志；协议代码集中在 `protocol.py`，易调整 |
| 大镜像分片设备不接受 | 刷写失败 | 先用小于 `max-download-size` 的 boot.img 验证 |
| 多台并发 USB 带宽不足 | 变慢/超时 | 用 `--jobs 2` 限制并发 |

## 结论

代码层面（枚举、路径解析、协议、sparse、并行调度、GUI/CLI）已完成并通过无设备测试。  
**实际可行性取决于明天设备的 WinUSB 驱动和 fastboot 协议兼容性**；第一步先跑 `doctor` 和 `getvar`，不要直接刷机。
