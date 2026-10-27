# AOSP fastboot 改造补丁：USB 路径寻址 + 1 对多并行

基线：AOSP `system/core/fastboot`（`main`，Windows `fastboot.exe` / AdbWinApi）。
目标命令：

```bat
:: 按 hub / index 选择一台设备
fastboot --hub 1 --index 3 reboot
fastboot --hub 1 --index 3 flash boot boot.img

:: 对所有设备并行执行
fastboot --all getvar current-slot
fastboot --all flash boot boot.img
fastboot --all --hub 1 --index 3 reboot

:: 等价写法：直接使用 USB 路径（-s 原生支持）
fastboot -s usb:1D00:0-1.3 reboot
```

> 注意：`--hub` / `--index` 是新增的**全局选项**，放在命令前。  
> 你的原话 `fastboot reboot hubdex index` 如果要求两个位置参数，见文末“可选：位置参数形式”。

---

## 1. 改动内容

| 文件 | 改动 |
| --- | --- |
| `fastboot/usb_windows.cpp` | 填充 `usb_ifc_info::device_path`，从 Windows `DEVPKEY_Device_LocationPaths` 解析出 `usb:1D00:0-1.3` |
| `fastboot/usb_path_windows.{h,cpp}`（新增） | SetupAPI / CfgMgr32：接口路径 → 设备节点 → 物理端口链；以及路径匹配 |
| `fastboot/fastboot.cpp` | 新增 `--hub` / `--index` / `--all`，在枚举回调里按端口过滤，并调用多设备分发 |
| `fastboot/fastboot_multi.{h,cpp}`（新增） | `--all`：枚举所有设备，每台设备启动一个 `fastboot` 子进程并等待，全部结束汇总退出码 |
| `fastboot/Android.bp` | 加入新源文件，Windows 链接 `setupapi` / `cfgmgr32` |

### 为什么 Windows 原来不能用 `-s usb:...`

AOSP `fastboot/usb_windows.cpp` 里一直是：

```cpp
info.device_path[0] = 0;
```

所以 `fastboot -s usb:1-3` 在 Windows 上匹配不到设备。Linux 的 `usb_linux.cpp` 已经填了 `usb:bus-port`，所以 Linux 不需要这一段。

本补丁用 Windows 的 location path：

```text
PCIROOT(0)#PCI(1D00)#USBROOT(0)#USB(1)#USB(3)
  -> usb:1D00:0-1.3
```

- `1D00`：USB 主控制器 PCI 位置（避免多控制器时重号）
- `0`：root hub 序号
- `1.3`：端口链；`1` 是上一级 hub 端口，`3` 是最后一级端口
- `--hub 1 --index 3` 匹配最后两个数字

`fastboot devices -l` 的第二列会从空变成类似 `usb:1D00:0-1.3` 的路径。

---

## 2. 应用补丁

假设 AOSP 根目录为 `$AOSP`：

```bash
cd $AOSP/system/core

# 1) 复制新增文件
cp /path/to/fastboot-src-patch/fastboot/usb_path_windows.h      fastboot/
cp /path/to/fastboot-src-patch/fastboot/usb_path_windows.cpp    fastboot/
cp /path/to/fastboot-src-patch/fastboot/fastboot_multi.h        fastboot/
cp /path/to/fastboot-src-patch/fastboot/fastboot_multi.cpp      fastboot/

# 2) 应用修改
patch -p1 < /path/to/fastboot-src-patch/patches/0001-usb-path-windows.patch
patch -p1 < /path/to/fastboot-src-patch/patches/0002-fastboot-hub-index-all.patch

# 3) 编译
cd $AOSP
m fastboot
```

如果 `patch` 因分支差异拒绝：

```bash
git apply --3way /path/to/.../0002-fastboot-hub-index-all.patch
```

或按下面的“手工集成”逐段修改。

### 手工集成（补丁失败时）

1. 把 `fastboot_multi.cpp/h`、`usb_path_windows.cpp/h` 放进 `system/core/fastboot/`。
2. `Android.bp`：
   - `libfastboot` 的 `srcs` 加 `"fastboot_multi.cpp"`；
   - `libfastboot` 的 `windows.srcs` 加 `"usb_path_windows.cpp"`；
   - `libfastboot2` 的 `windows.srcs` 加 `"usb_path_windows.cpp"`（它也会编译 `usb_windows.cpp`）；
   - Windows 链接加 `-lsetupapi`、`-lcfgmgr32`。
3. `usb_windows.cpp`：
   - `#include "usb_path_windows.h"`；
   - `usb_handle` 增加 `std::wstring interface_name_w;`；
   - `do_usb_open()` 里 `ret->interface_name_w = interface_name;`；
   - `recognized_device()` 里把 `info.device_path[0] = 0;` 替换为调用 `fastboot::UsbPathFromInterfaceName(...)`。
4. `fastboot.cpp`：
   - 加 `#include "fastboot_multi.h"`、`#include <algorithm>`；
   - 加 `g_all_devices`、`g_usb_hub`、`g_usb_index`；
   - `match_fastboot_with_serial()` 里加 `PathMatches` 过滤；
   - `Main()` 开头保存 `original_args`；
   - `longopts` 加 `--all/--hub/--index`；
   - 解析三个选项；
   - 在 `open_device()` 前加 `g_all_devices` 分支，调用 `ListUsbPaths()` + `RunAll()`；
   - help 里加三行说明。

---

## 3. 使用

### 3.1 按 hub/index 选单台

```bat
fastboot --hub 1 --index 3 reboot
fastboot --hub 1 --index 3 reboot bootloader
fastboot --hub 1 --index 3 getvar current-slot
fastboot --hub 1 --index 3 flash boot boot.img
fastboot --hub 1 --index 3 erase misc
fastboot --hub 1 --index 3 oem edl
```

`--index` 就是最后一级端口号；`--hub` 是上一级端口号。  
如果设备只有一级端口（直接插在 root hub），只写 `--index`。

### 3.2 直接使用 USB 路径

```bat
fastboot -s usb:1D00:0-1.3 reboot
fastboot -s usb:1D00:0-1.3 flash boot boot.img
```

`fastboot devices -l` 可以查看路径。

### 3.3 1 对多

```bat
fastboot --all reboot
fastboot --all reboot bootloader
fastboot --all getvar current-slot
fastboot --all flash boot boot.img
fastboot --all erase misc
fastboot --all --hub 1 --index 3 getvar version
```

行为：

- 主进程先枚举所有 fastboot 设备；
- 每台设备启动一个**独立子进程**，参数自动加 `-s <path>`；
- 所有子进程**并行**执行，父进程等待全部结束；
- 任一子进程非 0，整体退出码非 0；
- 子进程输出继承父进程控制台，所以刷多台时日志会交错（这是当前实现的一个限制）。

### 3.4 为什么 `--all` 用子进程而不是线程

AOSP `fastboot.cpp` 里 `fb`、`serial`、`target_sparse_limit`、`g_boot_img_hdr`、`FlashingPlan` 等大量全局状态，且 `FastBootDriver` 与 `FlashingPlan` 强绑定。直接多线程复用会引入难以验证的竞态。
每设备一个子进程可以完整复用所有现有命令（`flash`、`flashall`、`update`、`format`、`sideload` 之外的 OEM 命令、slot、AVB 逻辑等），风险最低。

---

## 4. 已验证 / 未验证

本机验证（Windows 10，MinGW g++ 8.1，真实 USB 设备，非 fastboot）：

```text
\\?\usb#vid_0d8c&pid_0014#6&135b54c7&0&6#...
  -> usb:1D00:0-1.6
\\?\usb#vid_0c45&pid_8071#6&135b54c7&0&3#...
  -> usb:1D00:0-1.3
\\?\usb#vid_30fa&pid_1701#6&134753f9&0&2#...
  -> usb:1A00:0-1.2
```

- USB 路径解析 helper 在真实设备上通过；
- `PathMatches`（`--hub/--index`）单元测试通过；
- `--all` 子进程分发在本机用测试程序验证：2 台设备并行、参数 `-s path` 正确传递、子进程退出码汇总正确；
- `patches/0002` 已用 AOSP main 的 `fastboot.cpp` 原文片段做上下文应用验证（所有 hunk 均可匹配）；
- 两个新增 `.cpp` 均以 `-Wall -Wextra -Werror` 在 MinGW g++ 8.1 下编译通过；
- 未连接 Android 真机，**尚未验证** `AdbCreateInterfaceByName` 拿到 fastboot 接口后的实际握手/刷写。

明天上机第一步：

```bat
fastboot devices -l
fastboot --hub 1 --index 3 getvar version
```

确认路径和 `OKAY` 后再刷。

---

## 5. 已知限制

- `--all` 的子进程日志会交错；如果需要每台独立日志，后续可加 `--all-log-dir`，把每个子进程 stdout/stderr 重定向到文件。
- `--all` 不能和 `-s` 同时使用；要过滤设备请用 `--hub/--index`。如果环境里设置了 `FASTBOOT_DEVICE` / `ANDROID_SERIAL`，先 unset，否则也会被当成显式选择。
- `--hub/--index` 依赖 `device_path`；没有路径且没有 SN 的设备无法被 `--all` 枚举（Windows 补丁后正常情况都有路径）。
- `--all` 每台设备一个进程，设备很多时进程数 = 设备数；产线一般 8/16 台可接受。
- 只对 Windows 补了 `device_path`；Linux/macOS 的路径解析沿用 AOSP 原有逻辑。
- 刷机中途拔线、设备重启导致的 USB 重新枚举，仍是 fastboot 原有行为。

---

## 6. 可选：位置参数形式 `fastboot reboot 1 3`

如果你坚持要：

```bat
fastboot reboot 1 3
```

可以在 `fastboot.cpp` 的 `reboot` 分支里，在 `RebootTask` 之前检查 `args` 的前两个参数是否为数字；如果是，则：

1. 设置 `g_usb_hub = atoi(argv1)`、`g_usb_index = atoi(argv2)`；
2. 从 `args` 里删掉这两个数字；
3. 再走原逻辑。

但这样只对 `reboot` 生效，`flash`、`getvar`、`erase` 仍然是 `--hub/--index`，语法不统一，且 `reboot 1` 可能和 `reboot bootloader` 的 target 解析冲突。**不推荐**；推荐全局选项形式。

---

## 7. 文件清单

```text
fastboot-src-patch/
├─ fastboot/
│  ├─ fastboot_multi.h
│  ├─ fastboot_multi.cpp
│  ├─ usb_path_windows.h
│  └─ usb_path_windows.cpp
├─ patches/
│  ├─ 0001-usb-path-windows.patch
│  └─ 0002-fastboot-hub-index-all.patch
├─ test_usb_path.cpp      # 本机 USB 路径 helper 验证程序
├─ test_multi.cpp         # 本机 --all 子进程分发验证程序
└─ README.md
```

测试程序编译（MinGW）：

```bat
g++ -std=c++17 -Wall -Wextra -Ifastboot test_usb_path.cpp fastboot/usb_path_windows.cpp -lsetupapi -lcfgmgr32 -o test_usb_path.exe
g++ -std=c++17 -Wall -Wextra -DFBHUB_NO_USB -Ifastboot test_multi.cpp fastboot/fastboot_multi.cpp -o test_multi.exe
```
