# -*- coding: utf-8 -*-
"""生成《智能座舱域控测试用例集》工作簿。

用例锚点全部来自本仓库既有资产：
  - 诊断网站 app.js：CDC 9 个模块、三核心跳（安全岛/RDA/NRDA）、日志码
  - cockpit-diag/checks/cockpit.json：13 个可执行检查项（ADB / CAN / UDS / DoIP / ETH）
  - cockpit-diag/checks/rules.json：故障规则与判据
"""

import math

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

CASE_HEADERS = [
    ("用例ID", 10),
    ("域", 8),
    ("模块", 14),
    ("用例名称", 26),
    ("前置条件", 30),
    ("测试步骤", 58),
    ("预期结果", 40),
    ("判定标准 / 阈值", 40),
    ("关联日志码 / 信号", 24),
    ("诊断网站对应", 20),
    ("优先级", 7),
    ("执行结果", 9),
    ("备注", 18),
]

THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF", size=10)
BODY_FONT = Font(size=10)
P0_FILL = PatternFill("solid", fgColor="FCE4E4")
P1_FILL = PatternFill("solid", fgColor="FFF4D6")
SEC_FILL = PatternFill("solid", fgColor="DCE6F1")
WRAP = Alignment(wrap_text=True, vertical="top")


def disp_len(text):
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text))


def auto_height(row_values, widths):
    lines = 1
    for value, width in zip(row_values, widths):
        if value is None:
            continue
        text = str(value)
        per_line = max(int(width * 1.05), 8)
        n = 0
        for seg in text.split("\n"):
            n += max(1, math.ceil(disp_len(seg) / per_line))
        lines = max(lines, n)
    return min(max(lines * 13.5 + 4, 18), 320)


def write_case_sheet(wb, title, rows, note=None):
    ws = wb.create_sheet(title)
    headers = [h for h, _ in CASE_HEADERS]
    widths = [w for _, w in CASE_HEADERS]

    ws.append(headers)
    for idx, (_, width) in enumerate(CASE_HEADERS, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    for cell in ws[1]:
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[1].height = 30

    r = 2
    for item in rows:
        steps = item["steps"]
        if isinstance(steps, (list, tuple)):
            steps = "\n".join(f"{i}) {s}" for i, s in enumerate(steps, 1))
        cells = [
            item["id"], item["domain"], item["module"], item["name"], item["pre"],
            steps, item["expect"], item["criteria"], item["codes"], item["site"],
            item["priority"], "", item.get("note", ""),
        ]
        ws.append(cells)
        for col in range(1, len(cells) + 1):
            c = ws.cell(row=r, column=col)
            c.font = BODY_FONT
            c.alignment = WRAP
            c.border = BORDER
        pr = ws.cell(row=r, column=11)
        pr.alignment = Alignment(horizontal="center", vertical="top")
        if item["priority"] == "P0":
            pr.fill = P0_FILL
        elif item["priority"] == "P1":
            pr.fill = P1_FILL
        ws.row_dimensions[r].height = auto_height(cells, widths)
        r += 1

    last = r - 1
    ws.freeze_panes = "A2"
    if last >= 2:
        ws.auto_filter.ref = f"A1:M{last}"

    dv = DataValidation(type="list", formula1='"Pass,Fail,Blocked,N/A"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"L2:L{max(last, 2)}")

    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "1:1"

    if note:
        ws.sheet_properties.tabColor = "1F3864"
    return ws


# --------------------------------------------------------------------------
# 用例内容
# --------------------------------------------------------------------------
FUNCTIONAL = [
    dict(id="F-001", domain="Android", module="启动/系统", name="冷启动到可交互", priority="P0",
         pre="样机常温 25°C；12V 稳压电源；ADB 与串口已连接",
         steps=["断电 30s 后上电", "串口抓取启动时序（bootloader → kernel → Android）",
                "adb wait-for-device；adb shell getprop sys.boot_completed",
                "记录 VBAT 上电到 boot_completed=1 的耗时", "重复 20 次统计"],
         expect="每次均进入桌面；getprop 返回 1；无 boot loop",
         criteria="冷启动 ≤ 25s（P95）；20 次成功率 100%",
         codes="SOC_BOOT", site="稳定性监控 / SOC 核心监控"),
    dict(id="F-002", domain="Android", module="显示", name="显示服务与多屏在线", priority="P0",
         pre="系统已启动；仪表/中控/副驾/后排/HUD 屏线全部连接",
         steps=["adb shell dumpsys display | grep -i 'Display Devices'", "逐屏确认分辨率与刷新率",
                "播放全屏视频 10min 观察撕裂/闪烁"],
         expect="5 屏全部在线且分辨率正确；无撕裂、闪烁、花屏",
         criteria="dumpsys 输出包含 Display Devices；连续 10min 无视觉异常",
         codes="DISPLAY_*", site="外设区 / 音频显示区"),
    dict(id="F-003", domain="Android", module="音频", name="音频通路与 A2B 链路", priority="P0",
         pre="功放、喇叭、MIC 阵列、A2B 链路连接完毕",
         steps=["adb shell dumpsys audio | grep AudioFlinger", "依次播放各声道 1kHz 0dB 测试音",
                "录放回环测试 4 路 MIC", "读取 A2B 节点寄存器状态"],
         expect="AudioFlinger 正常；各声道独立发声无串音；MIC 无静音",
         criteria="A2B Jitter ≤ 1.5ms；THD+N ≤ 1%；4 路 MIC 信噪比 ≥ 60dB",
         codes="AUDIO_A2B_*", site="音频显示区"),
    dict(id="F-004", domain="Android", module="外设/Camera", name="摄像头帧率与丢帧", priority="P1",
         pre="前视/环视摄像头接入；EVS 或 Camera HAL 已加载",
         steps=["启动预览并持续 30min", "记录 FPS 与丢帧计数", "遮挡镜头验证曝光自适应"],
         expect="FPS 稳定；丢帧计数不增长",
         criteria="FPS ≥ 25；30min 丢帧 ≤ 5；无花屏/绿屏",
         codes="PERIPH_CAM_*", site="外设区"),
    dict(id="F-005", domain="Android", module="射频", name="多制式信号与天线自检", priority="P1",
         pre="屏蔽箱或暗室；SIM 卡已插入；AP 已配置",
         steps=["读取 5G/4G RSRP、WiFi RSSI、BT RSSI", "各制式分别建立连接并保持 10min",
                "切换飞行模式 20 次"],
         expect="各制式可注册可连接；无掉网",
         criteria="5G RSRP ≥ -105dBm；WiFi RSSI ≥ -70dBm；切换成功率 100%",
         codes="RF_*", site="射频短距离"),
    dict(id="F-006", domain="Android", module="USB/ADB", name="调试通道可用（工程样机）", priority="P0",
         pre="工程样机，root 已开启（userdebug/eng 版本）",
         steps=["adb get-state", "adb shell id（确认 uid=0）", "adb reboot bootloader 后 fastboot devices",
                "切回系统"],
         expect="ADB 可连、可 root、可切 fastboot 并被识别",
         criteria="get-state=device；id 返回 uid=0；fastboot devices 可见",
         codes="-", site="-", note="仅工程样机；量产 user 版本需回归验证不可 root"),
    dict(id="F-007", domain="Android", module="CAN", name="CAN 心跳与负载", priority="P0",
         pre="CANoe/周立功 CAN 盒接入；波特率 500k；终端电阻 60Ω",
         steps=["监听 0x18FF0102 心跳 5min", "统计总线负载与错误帧", "注入 70% 负载干扰 10min"],
         expect="心跳周期稳定；错误帧为 0；高负载下无丢帧",
         criteria="心跳周期抖动 ≤ ±10%；负载 ≤ 70%；错误帧 0",
         codes="MCU_CAN", site="MCU 监控区"),
    dict(id="F-008", domain="Android", module="诊断 UDS", name="UDS 会话与安全访问", priority="P0",
         pre="CAN 通道可用；诊断 ID 0x18DA0BF1 → 0x18DAF10B",
         steps=["发送 3E 00 保持会话，观察正响应", "10 03 进入扩展会话",
                "27 01/27 02 安全访问", "22 F1 90 读取 VIN"],
         expect="各请求均有正响应（7F 除外）",
         criteria="3E 00 响应 ≤ 50ms；安全访问成功率 100%",
         codes="CAN_UDS_NO_REPLY", site="稳定性监控 / CAN"),
    dict(id="F-009", domain="Android", module="以太网", name="车内网关连通性与 DoIP", priority="P0",
         pre="以太网口接入车内网关 192.168.1.1；IP 已配置",
         steps=["ping 192.168.1.1 -n 100", "UDP 13400 发送 02 01 探测 DoIP",
                "TCP 连接 HMI 8080", "ethtool 查看链路速率"],
         expect="ping 通、DoIP 有回包、HMI 端口可连",
         criteria="丢包 ≤ 1%；DoIP 回包 ≤ 100ms；链路 1000Mbps 全双工",
         codes="ETH_NO_LINK / ETH_DOIP_NO_REPLY", site="VDC 以太网 / 稳定性"),
    dict(id="F-010", domain="Android", module="存储", name="data 分区读写与掉电一致性", priority="P1",
         pre="系统已启动；root 可用",
         steps=["df /data 确认挂载", "dd 写入 2GB 校验 md5", "写入过程中断电 10 次",
                "重启后 e2fsck -fn 检查"],
         expect="分区可读写；掉电后文件系统一致",
         criteria="md5 一致；e2fsck 无错误；无只读重挂",
         codes="UFS_HEALTH", site="存储健康检测"),
    dict(id="F-011", domain="Android", module="稳定性", name="崩溃日志基线", priority="P1",
         pre="常温；系统启动后静置 30min",
         steps=["adb shell logcat -d -b crash -t 200", "统计 FATAL EXCEPTION 与 ANR",
                "检查 tombstone 目录"],
         expect="无新增崩溃",
         criteria="FATAL EXCEPTION = 0；ANR = 0",
         codes="STAB_CRASH / STAB_ANR", site="稳定性监控"),
]

SAFETY = [
    dict(id="S-001", domain="安全岛", module="启动自检", name="安全岛启动与版本读取", priority="P0",
         pre="样机断电重启；串口接安全岛调试口",
         steps=["上电抓取安全岛启动日志", "读取安全岛固件版本与配置 CRC", "对照发布清单校验"],
         expect="自检通过；版本号与发布一致；CRC 正确",
         criteria="自检时间 ≤ 200ms；版本/CRC 100% 匹配",
         codes="MCU_SAFETY_BOOT", site="MCU 监控区"),
    dict(id="S-002", domain="安全岛", module="三核心跳", name="安全岛/RDA/NRDA 心跳持续监测", priority="P0",
         pre="系统正常运行；心跳计数器可读",
         steps=["采集三核心跳 30min（1Hz）", "统计丢失次数与抖动", "与诊断网站 mcu.hbRda 对照"],
         expect="三核心跳连续、无丢失",
         criteria="丢失 0 次；抖动 ≤ ±5%；网站显示值与实测一致",
         codes="MCU_HEARTBEAT core=SAFETY/RDA/NRDA", site="MCU 监控区（RDA 心跳）"),
    dict(id="S-003", domain="安全岛", module="看门狗", name="看门狗超时复位验证", priority="P0",
         pre="工程样机；可人为挂起 RDA 任务",
         steps=["挂起 RDA 主循环（或注入死循环）", "计时看安全岛多久检测到心跳丢失",
                "确认复位/降级动作与日志", "恢复后确认系统自愈"],
         expect="安全岛在超时窗口内触发保护动作并记录日志",
         criteria="检测 ≤ 500ms；复位/降级 ≤ 2s；日志含原因码",
         codes="MCU_WATCHDOG", site="MCU 监控区 / 稳定性监控", note="破坏性用例，需在样机上单独执行"),
    dict(id="S-004", domain="安全岛", module="锁步/ECC", name="锁步核比对错误注入", priority="P0",
         pre="支持故障注入的样机；安全岛锁步已使能",
         steps=["通过寄存器注入 1bit 锁步 mismatch", "观察安全岛告警与降级策略",
                "注入 2bit 不可纠正错误", "确认进入安全状态"],
         expect="1bit 可纠正并上报；2bit 触发安全状态",
         criteria="告警 ≤ 100ms；不得静默忽略；复位后进入安全状态",
         codes="MCU_SAFETY_LOCKSTEP", site="MCU 监控区"),
    dict(id="S-005", domain="安全岛", module="隔离性", name="安全岛独立复位不影响 Android", priority="P0",
         pre="Android 侧正在播放视频并记录画面",
         steps=["单独复位安全岛", "观察 Android 画面/音频/触摸是否中断", "确认安全岛重启后重新握手"],
         expect="Android 业务不中断；握手在 1s 内恢复",
         criteria="画面无黑屏；音频无断流；握手 ≤ 1s",
         codes="MCU_SAFETY_RESET", site="MCU 监控区"),
    dict(id="S-006", domain="安全岛", module="IPC", name="安全岛与 Android 通信可靠性", priority="P0",
         pre="IPC 通道（SPI/共享内存）可用；有回环工具",
         steps=["连续收发 10000 帧递增序号", "统计丢帧、错序、CRC 错误", "注入 30% 总线负载后复测"],
         expect="无丢帧、无错序",
         criteria="丢帧 0；CRC 错误 0；时延 P99 ≤ 5ms",
         codes="MCU_IPC_*", site="MCU 监控区"),
    dict(id="S-007", domain="安全岛", module="故障响应", name="Android 侧 system_server 异常时安全岛响应", priority="P1",
         pre="工程样机；可 kill 系统进程",
         steps=["kill -9 system_server", "观察安全岛是否检测到 Android 心跳丢失",
                "记录安全岛动作（告警/降级/复位）", "Android 重启后确认状态恢复"],
         expect="安全岛检测并记录；系统重启后恢复正常",
         criteria="检测 ≤ 2s；日志含 component=android；恢复后无残留告警",
         codes="MCU_HEARTBEAT", site="稳定性监控 / MCU 监控区"),
    dict(id="S-008", domain="安全岛", module="电源", name="安全岛供电拉偏与掉电保持", priority="P1",
         pre="可调直流电源；安全岛独立电源轨",
         steps=["安全岛供电 3.3V 拉偏 ±5%，观察功能", "主电源掉电，验证安全岛保持时间",
                "恢复供电后自检"],
         expect="拉偏范围内功能正常；掉电期间关键状态不丢",
         criteria="3.135~3.465V 正常；掉电保持 ≥ 10ms；恢复后自检通过",
         codes="POWER_RAIL_*", site="功耗监控区"),
]

RDA = [
    dict(id="R-001", domain="RDA", module="心跳", name="RDA 心跳频率与抖动", priority="P0",
         pre="RDA 已运行；心跳计数可读",
         steps=["采样 60min", "计算平均频率与抖动", "与安全岛记录的心跳做比对"],
         expect="频率稳定在标称值；双方记录一致",
         criteria="频率偏差 ≤ ±2%；抖动 ≤ ±5%；一致率 100%",
         codes="MCU_HEARTBEAT core=RDA", site="MCU 监控区（RDA 心跳）"),
    dict(id="R-002", domain="RDA", module="实时性", name="RDA 任务调度延迟", priority="P0",
         pre="RDA 侧可运行延迟测试工具",
         steps=["运行 1kHz 周期任务 30min", "统计最大/平均延迟与超时次数",
                "叠加 Android 高负载后复测"],
         expect="调度延迟在预算内",
         criteria="平均延迟 ≤ 100µs；最大 ≤ 1ms；超时 0 次",
         codes="MCU_RDA_LATENCY", site="MCU 监控区"),
    dict(id="R-003", domain="RDA", module="IPC", name="RDA 与安全岛数据面吞吐", priority="P1",
         pre="两者 IPC 通道可用",
         steps=["以 1KB 帧持续发送 10min", "统计吞吐、丢帧、时延"],
         expect="吞吐达标、无丢帧",
         criteria="吞吐 ≥ 10MB/s；丢帧 0；时延 P99 ≤ 2ms",
         codes="MCU_IPC_*", site="MCU 监控区"),
    dict(id="R-004", domain="RDA", module="恢复", name="RDA 异常复位后自恢复", priority="P0",
         pre="工程样机；可触发 RDA 复位",
         steps=["触发 RDA 看门狗复位", "计时恢复到心跳正常", "确认业务侧无感或按预期降级"],
         expect="RDA 自动重启并重新握手",
         criteria="恢复 ≤ 3s；业务无黑屏；日志完整记录原因",
         codes="MCU_RDA_RESET", site="稳定性监控"),
    dict(id="R-005", domain="RDA", module="内存", name="RDA 内存错误计数", priority="P1",
         pre="RDA ECC 计数器可读",
         steps=["读取 ECC CE/UE 计数", "连续运行 72h 后复读", "对比增量"],
         expect="无不可纠正错误；可纠正错误增量在阈值内",
         criteria="UE = 0；CE 增量 ≤ 10/72h",
         codes="MCU_ECC", site="MCU 监控区"),
    dict(id="R-006", domain="RDA", module="长稳", name="RDA 72h 内存泄漏监测", priority="P1",
         pre="RDA 承载常驻业务",
         steps=["每 10min 采样一次内存占用", "绘制 72h 曲线", "做线性回归看斜率"],
         expect="无持续增长",
         criteria="72h 增长 ≤ 2%；无 OOM",
         codes="MCU_RDA_MEM", site="MCU 监控区"),
]

NRDA = [
    dict(id="N-001", domain="NRDA", module="心跳", name="NRDA 心跳与状态上报", priority="P0",
         pre="NRDA 已运行",
         steps=["采样心跳 30min", "读取状态寄存器", "与安全岛记录比对"],
         expect="心跳稳定；状态上报一致",
         criteria="丢失 0 次；状态一致率 100%",
         codes="MCU_HEARTBEAT core=NRDA", site="MCU 监控区"),
    dict(id="N-002", domain="NRDA", module="配置", name="NRDA 版本与配置校验", priority="P1",
         pre="可读取 NRDA 固件版本",
         steps=["读取版本号与配置 CRC", "对照发布清单", "升级后复测"],
         expect="版本与配置正确",
         criteria="版本匹配；CRC 一致；升级后功能正常",
         codes="MCU_NRDA_CFG", site="MCU 监控区"),
    dict(id="N-003", domain="NRDA", module="数据面", name="NRDA 与 Android 数据吞吐", priority="P1",
         pre="数据通道可用",
         steps=["持续传输 10min", "统计吞吐/丢包/时延", "边界速率测试"],
         expect="吞吐达标、无丢包",
         criteria="吞吐 ≥ 设计值 90%；丢包 0；时延 P99 ≤ 10ms",
         codes="MCU_NRDA_IO", site="MCU 监控区"),
    dict(id="N-004", domain="NRDA", module="隔离性", name="NRDA 复位不影响其他两域", priority="P1",
         pre="三域均在运行",
         steps=["复位 NRDA", "观察安全岛/RDA/Android 状态", "确认 NRDA 自动恢复"],
         expect="其他域不受影响",
         criteria="安全岛/RDA 心跳不丢；Android 无异常；NRDA 恢复 ≤ 3s",
         codes="MCU_NRDA_RESET", site="稳定性监控"),
    dict(id="N-005", domain="NRDA", module="低功耗", name="NRDA 低功耗状态进出", priority="P2",
         pre="支持 suspend/resume",
         steps=["触发进入低功耗", "测量静态电流", "唤醒并检查时延与状态"],
         expect="可正常进出；状态不丢",
         criteria="静态电流 ≤ 规格值；唤醒 ≤ 100ms；状态一致",
         codes="POWER_SUSPEND", site="功耗监控区"),
]

HOT = [
    dict(id="H-001", domain="高温", module="存储老化", name="高温存储 85°C / 96h", priority="P0",
         pre="样机断电，放入温箱；温度传感器贴外壳与 SoC 附近",
         steps=["温箱升至 85°C（≤3°C/min），保持 96h", "期间每 4h 记录箱温与样机外观",
                "结束降至常温，恢复 2h", "执行功能全检（F-001~F-011）"],
         expect="无外观变形、无功能失效",
         criteria="功能全检 100% 通过；外壳无变形/开裂；无器件脱落",
         codes="-", site="全部模块"),
    dict(id="H-002", domain="高温", module="工作老化", name="高温工作 70°C / 96h 循环负载", priority="P0",
         pre="样机通电，运行综合负载脚本（视频+导航+音频+CAN 流量+Camera）",
         steps=["温箱升至 70°C 并稳定", "连续运行 96h，负载循环 30min 一轮",
                "每 4h 巡检一次（共 24 次）：截图、音频、CAN、心跳、温度、功耗",
                "每 24h 抓取全量日志并按诊断网站格式归档"],
         expect="全程无宕机、无重启、无花屏、无断音",
         criteria="panic/异常重启/ANR = 0；CAN 错误帧 0；心跳丢失 0；屏幕/音频抽检 100% 通过",
         codes="STAB_* / POWER_* / MCU_HEARTBEAT", site="稳定性监控 / 功耗监控区"),
    dict(id="H-003", domain="高温", module="温控", name="高温降频与热保护策略", priority="P0",
         pre="可读 thermal_zone 与 cpufreq",
         steps=["70°C 下逐步加载 CPU/GPU 至满负荷", "同步记录结温、频率、功耗（1Hz）",
                "持续 2h，绘制温度-频率曲线", "确认无热关机"],
         expect="按设计曲线降频，不触发硬件关机",
         criteria="结温 ≤ 95°C；外壳 ≤ 70°C；降频行为符合标定曲线；热关机 0 次",
         codes="SOC_GPU_TEMP", site="SOC 核心监控 / 功耗监控区"),
    dict(id="H-004", domain="高温", module="存储", name="高温 UFS 持续读写", priority="P1",
         pre="root 可用；可读 UFS 健康节点",
         steps=["高温工作状态下 dd 写入/读取 20GB", "统计读写延迟 P95/P99",
                "读取坏块数、寿命、温度"],
         expect="读写稳定，延迟在高温预算内",
         criteria="读 P99 ≤ 200ms；坏块无新增；寿命下降符合写入量",
         codes="UFS_LATENCY / UFS_BAD_BLOCK", site="存储健康检测"),
    dict(id="H-005", domain="高温", module="内存", name="高温 DDR ECC 与错误统计", priority="P0",
         pre="DDR ECC 已使能；计数器可读",
         steps=["满载运行 96h", "每 4h 读取 CE/UE 计数", "统计跳变与刷新异常"],
         expect="无 UE；CE 在阈值内",
         criteria="UE = 0；CE ≤ 5/24h；无 DDR 训练失败",
         codes="DDR_ECC", site="DDR 运行内存"),
    dict(id="H-006", domain="高温", module="电源", name="高温电源轨与功耗", priority="P1",
         pre="可测 12V 输入电流；各路电源轨可探测",
         steps=["记录 70°C 满载输入功率与纹波", "逐路测量电压偏差", "对比常温基线"],
         expect="电源轨在容差内",
         criteria="12V 纹波 ≤ 100mVpp；各轨偏差 ≤ ±3%；功耗增幅 ≤ 15%",
         codes="POWER_RAIL_*", site="功耗监控区"),
    dict(id="H-007", domain="高温", module="电源循环", name="高温下反复上下电 500 次", priority="P1",
         pre="程控电源支持循环控制",
         steps=["70°C 下执行 500 次上电 30s / 断电 10s", "统计启动失败次数",
                "结束后执行功能全检"],
         expect="每次均正常启动",
         criteria="启动成功率 100%；无 boot loop",
         codes="SOC_BOOT", site="稳定性监控"),
    dict(id="H-008", domain="高温", module="功能抽检", name="高温功能巡检（每 4h）", priority="P0",
         pre="老化过程中执行",
         steps=["每 4h 执行：显示截图、音频播放、Camera 预览、CAN 收发、WiFi 连接",
                "记录每次结果与异常截图", "异常立即拍照并记录箱温与时间"],
         expect="24 次抽检全部通过",
         criteria="抽检通过率 100%；任一失败即判定老化不通过",
         codes="-", site="外设区 / 音频显示区 / 射频"),
    dict(id="H-009", domain="高温", module="性能基线", name="高温老化后性能对比", priority="P1",
         pre="老化前已完成基线测试并留档",
         steps=["老化后在常温恢复 2h", "复测启动时间、FPS、UFS 延迟、CPU 满载性能",
                "与基线逐项对比"],
         expect="性能无明显劣化",
         criteria="启动时间劣化 ≤ 10%；FPS 劣化 ≤ 5%；延迟劣化 ≤ 10%",
         codes="-", site="全部模块"),
    dict(id="H-010", domain="高温", module="诊断联动", name="老化期间诊断网站无人值守监控", priority="P1",
         pre="诊断网站可访问；日志按 5min 周期采集",
         steps=["老化全程每 5min 导入日志", "统计 ERROR 级事件数", "核对时间轴与温箱时间戳"],
         expect="无 ERROR 级异常；时间轴连续",
         criteria="ERROR 事件 0；日志断档 ≤ 10min；时间戳偏差 ≤ 1s",
         codes="全部", site="三域时间轴 / 8D 报告"),
]

COLD = [
    dict(id="L-001", domain="低温", module="存储老化", name="低温存储 -40°C / 96h", priority="P0",
         pre="样机断电入箱",
         steps=["降至 -40°C 保持 96h", "回温至常温并静置 2h（防凝露）",
                "开机执行功能全检"],
         expect="无功能失效、无凝露短路",
         criteria="功能全检 100% 通过；绝缘电阻 ≥ 10MΩ",
         codes="-", site="全部模块"),
    dict(id="L-002", domain="低温", module="冷启动", name="-30°C 冷启动", priority="P0",
         pre="样机在 -30°C 浸泡 ≥ 8h（断电）",
         steps=["保持 -30°C 上电", "记录启动时间与启动日志", "检查屏幕/触摸/音频是否正常",
                "重复 20 次"],
         expect="每次均能启动，无花屏、无触摸失效",
         criteria="启动 ≤ 40s（P95）；成功率 100%；屏幕无花屏",
         codes="SOC_BOOT", site="稳定性监控 / 外设区"),
    dict(id="L-003", domain="低温", module="工作老化", name="低温工作 -30°C / 48h", priority="P0",
         pre="样机在箱内通电运行",
         steps=["-30°C 下连续运行 48h（循环负载）", "每 4h 抽检显示/音频/CAN/心跳",
                "结束后常温恢复并全检"],
         expect="全程无宕机、功能正常",
         criteria="panic/重启/ANR = 0；抽检 100% 通过",
         codes="STAB_*", site="稳定性监控"),
    dict(id="L-004", domain="低温", module="显示/触摸", name="低温显示与触控响应", priority="P1",
         pre="-30°C 稳定运行",
         steps=["测量 LCM 响应时间与亮度", "触摸划线 100 次，记录断点",
                "对比常温基线"],
         expect="响应变慢但在规格内",
         criteria="亮度 ≥ 常温 70%；触摸断点 ≤ 1%；响应 ≤ 2× 常温",
         codes="PERIPH_LCM_*", site="外设区 / 音频显示区"),
    dict(id="L-005", domain="低温", module="存储", name="低温 UFS 读写", priority="P1",
         pre="-30°C 稳定运行",
         steps=["顺序/随机读写各 5GB", "统计延迟与吞吐", "校验数据完整性"],
         expect="读写正常，性能下降在预算内",
         criteria="读吞吐 ≥ 常温 60%；数据 md5 一致；无 I/O 错误",
         codes="UFS_LATENCY", site="存储健康检测"),
    dict(id="L-006", domain="低温", module="电源", name="低温启动电流与电源轨", priority="P1",
         pre="可测输入电流波形",
         steps=["-30°C 记录冷启动浪涌电流", "测量各路电源轨建立时间",
                "确认无欠压复位"],
         expect="浪涌在电源规格内",
         criteria="浪涌 ≤ 规格上限；建立时间 ≤ 50ms；欠压复位 0 次",
         codes="POWER_RAIL_*", site="功耗监控区"),
    dict(id="L-007", domain="低温", module="音频", name="低温音频与 MIC", priority="P1",
         pre="-30°C 运行中",
         steps=["各声道播放测试音", "4 路 MIC 录放回环", "检查是否有爆音/无声"],
         expect="音频正常",
         criteria="THD+N ≤ 2%；MIC 信噪比 ≥ 55dB；无爆音",
         codes="AUDIO_*", site="音频显示区"),
    dict(id="L-008", domain="低温", module="Camera", name="低温摄像头与加热策略", priority="P2",
         pre="-30°C 运行中；镜头可能结霜",
         steps=["启动预览 30min", "记录首帧时间与结霜情况", "验证加热除霜（如有）"],
         expect="图像可用，结霜可消除",
         criteria="首帧 ≤ 3s；30min 无失效；除霜 ≤ 5min（如有加热）",
         codes="PERIPH_CAM_*", site="外设区"),
    dict(id="L-009", domain="低温", module="电源循环", name="低温冷启动 200 次", priority="P1",
         pre="-30°C 环境",
         steps=["执行 200 次上电/断电循环", "统计启动失败与异常", "结束后功能全检"],
         expect="启动稳定",
         criteria="成功率 100%；无 boot loop；功能全检通过",
         codes="SOC_BOOT", site="稳定性监控"),
    dict(id="L-010", domain="低温", module="性能基线", name="低温老化后性能对比", priority="P1",
         pre="有老化前基线",
         steps=["常温恢复 2h 后复测启动/FPS/延迟", "与基线对比", "检查是否有不可恢复劣化"],
         expect="性能回到基线水平",
         criteria="劣化 ≤ 10%；无永久性功能损失",
         codes="-", site="全部模块"),
]

THERMAL = [
    dict(id="C-001", domain="温度循环", module="整机", name="-40°C ↔ 85°C 循环 20 次", priority="P0",
         pre="样机通电运行轻负载",
         steps=["每循环：-40°C 驻留 2h → 升温 1h → 85°C 驻留 2h → 降温 1h",
                "共 20 循环，全程通电并记录日志", "每循环结束执行功能抽检"],
         expect="循环后功能正常",
         criteria="循环中 panic/重启 0；抽检 100% 通过；无焊点开裂（外观）",
         codes="STAB_*", site="稳定性监控"),
    dict(id="C-002", domain="温度循环", module="整机", name="快速温变冲击 10 循环", priority="P1",
         pre="温变速率 ≥ 5°C/min",
         steps=["-40°C ↔ 85°C，每段驻留 30min，10 循环", "监测是否出现功能中断",
                "结束后 X-ray 抽检焊点（可选）"],
         expect="无功能中断",
         criteria="中断 0 次；外观无裂纹；X-ray 无异常（如执行）",
         codes="-", site="全部模块"),
    dict(id="C-003", domain="温度循环", module="凝露", name="循环中凝露与绝缘检查", priority="P1",
         pre="高湿段可控制湿度",
         steps=["在升温段观察 PCB 凝露", "测量绝缘电阻", "检查是否有短路/漏电"],
         expect="无凝露导致的短路",
         criteria="绝缘 ≥ 10MΩ；无漏电告警；无腐蚀痕迹",
         codes="POWER_*", site="功耗监控区"),
    dict(id="C-004", domain="温度循环", module="结构", name="循环后结构与紧固检查", priority="P2",
         pre="循环结束",
         steps=["检查螺丝扭矩、连接器锁扣、导热硅脂状态", "复核散热器接触",
                "记录外观照片"],
         expect="结构完好",
         criteria="扭矩在规格内；连接器无松动；硅脂无干裂",
         codes="-", site="-"),
]

STABILITY = [
    dict(id="ST-001", domain="稳定性", module="长稳", name="72h 常温长稳 + 循环负载", priority="P0",
         pre="常温 25°C；综合负载脚本",
         steps=["连续运行 72h，负载循环 30min", "每 1h 采集 CPU/内存/温度/心跳",
                "结束后全功能自检"],
         expect="无宕机、无内存泄漏",
         criteria="panic/ANR = 0；内存增长 ≤ 2%；心跳丢失 0",
         codes="STAB_*", site="稳定性监控"),
    dict(id="ST-002", domain="稳定性", name="Monkey 压力 10 万次", module="Android", priority="P1",
         pre="userdebug 版本；可执行 monkey",
         steps=["adb shell monkey -p <包名> --throttle 50 -v 100000",
                "记录 crash/ANR 次数", "结束后检查系统可用性"],
         expect="无 crash/ANR",
         criteria="crash = 0；ANR = 0；结束后功能正常",
         codes="STAB_CRASH / STAB_ANR", site="稳定性监控"),
    dict(id="ST-003", domain="稳定性", module="电源", name="电源拉偏与欠压恢复", priority="P1",
         pre="程控电源 9~16V 可调",
         steps=["在 9V/12V/16V 下各运行 1h", "执行 100 次 9V↔16V 切换", "记录复位/重启"],
         expect="电压范围内稳定工作",
         criteria="复位 0 次；切换后功能正常；无器件损伤",
         codes="POWER_UV", site="功耗监控区"),
    dict(id="ST-004", domain="稳定性", module="休眠", name="休眠唤醒 1000 次", priority="P1",
         pre="支持 STR/快速唤醒",
         steps=["循环进入/退出休眠 1000 次", "统计唤醒失败与时间", "检查外设是否掉线"],
         expect="唤醒稳定",
         criteria="失败 0 次；唤醒 ≤ 500ms；外设无掉线",
         codes="POWER_SUSPEND", site="功耗监控区"),
    dict(id="ST-005", domain="稳定性", module="掉电", name="异常掉电 200 次与文件系统一致性", priority="P0",
         pre="root 可用",
         steps=["随机时刻切断电源 200 次", "每次重启后 e2fsck -fn /data", "统计启动失败"],
         expect="文件系统始终一致",
         criteria="fsck 无错误；启动成功率 100%；无数据分区只读",
         codes="STAB_REBOOT", site="存储健康检测 / 稳定性监控"),
    dict(id="ST-006", domain="稳定性", module="重启", name="连续重启 500 次无 boot loop", priority="P1",
         pre="可脚本化重启",
         steps=["adb reboot 循环 500 次", "统计每次 boot_completed", "记录最长启动时间"],
         expect="全部正常启动",
         criteria="成功率 100%；最长启动 ≤ 35s",
         codes="SOC_BOOT / STAB_REBOOT", site="稳定性监控"),
]

DIAG = [
    dict(id="D-001", domain="诊断网站", module="日志解析", name="采集字段与解析器对齐", priority="P0",
         pre="网站可访问；样机日志可导出",
         steps=["导出 logcat/dmesg/kernel 日志", "按网站要求的 code= 与 key=value 格式整理",
                "导入网站，核对解析出的事件数与级别"],
         expect="字段无丢失；事件级别正确",
         criteria="解析成功率 ≥ 99%；ERROR/WARN 级别与源日志一致",
         codes="-", site="日志扫描面板"),
    dict(id="D-002", domain="诊断网站", module="码表映射", name="关键日志码注入与模块映射", priority="P0",
         pre="可向网站导入构造日志",
         steps=["构造 SOC_CPU_UV / SOC_ECC_CE / DDR_ECC / UFS_LATENCY / MCU_HEARTBEAT core=RDA 等日志",
                "导入并检查事件落到哪个模块", "核对时间轴与详情页指标"],
         expect="每条日志落到正确模块与字段",
         criteria="映射准确率 100%（抽 10 条码）",
         codes="SOC_* / DDR_* / UFS_* / MCU_*", site="对应 CDC 模块详情页"),
    dict(id="D-003", domain="诊断网站", module="阈值", name="网站阈值与实测判据一致性", priority="P0",
         pre="有本用例集的判据表",
         steps=["逐项比对网站告警阈值（温度/电压/负载/延迟）", "用临界值日志验证告警是否触发",
                "记录不一致项"],
         expect="阈值一致，临界值行为正确",
         criteria="阈值偏差 0；临界值误报/漏报 0",
         codes="-", site="规则与告警面板"),
    dict(id="D-004", domain="诊断网站", module="实时性", name="实时指标与实机偏差", priority="P1",
         pre="可同时读实机与网站数值",
         steps=["同一时刻读取网站 soc.temp 与 thermal_zone", "对比 100 个采样点",
                "测量页面刷新延迟"],
         expect="数值一致、刷新及时",
         criteria="温度偏差 ≤ 2°C；刷新 ≤ 1s",
         codes="SOC_GPU_TEMP", site="SOC 核心监控 / 功耗监控区"),
    dict(id="D-005", domain="诊断网站", module="健康评分", name="三域健康评分与人工判定一致性", priority="P1",
         pre="准备 10 个已知故障场景",
         steps=["每个场景运行 30min 并采集日志", "记录网站评分与人工结论", "统计一致率"],
         expect="评分能反映真实健康度",
         criteria="一致率 ≥ 90%；严重故障必须判为异常",
         codes="-", site="三域健康评分"),
    dict(id="D-006", domain="诊断网站", module="8D 报告", name="8D 维修报告导出完整性", priority="P1",
         pre="存在多条异常事件",
         steps=["点击导出维修报告", "检查 D1~D8 结构、模块卡片数、时间轴条目、图表快照",
                "打印/另存 PDF 检查排版"],
         expect="报告结构完整、图表可显示",
         criteria="D1~D8 齐全；23 模块卡片；时间轴条目与源数据一致；PDF 无溢出",
         codes="-", site="8D 报告导出"),
    dict(id="D-007", domain="诊断网站", module="无人值守", name="老化过程自动巡检", priority="P1",
         pre="老化台架 + 定时任务",
         steps=["每 5min 自动采集并导入日志", "统计断档与异常告警", "核对与温箱时间轴对齐"],
         expect="全程可追溯",
         criteria="断档 ≤ 10min；时间戳偏差 ≤ 1s；异常可回溯",
         codes="-", site="三域时间轴"),
    dict(id="D-008", domain="诊断网站", module="性能", name="大日志导入性能", priority="P2",
         pre="构造 10 万行日志",
         steps=["导入 10 万行日志", "记录解析耗时与页面内存", "检查交互是否卡顿"],
         expect="可完成解析、页面可用",
         criteria="解析 ≤ 10s；内存增长 ≤ 200MB；无卡死",
         codes="-", site="日志扫描面板"),
]

SHEETS = [
    ("02_功能测试", FUNCTIONAL),
    ("03_安全岛", SAFETY),
    ("04_RDA", RDA),
    ("05_NRDA", NRDA),
    ("06_高温老化", HOT),
    ("07_低温老化", COLD),
    ("08_温度循环", THERMAL),
    ("09_稳定性", STABILITY),
    ("10_诊断网站联动", DIAG),
]

DOMAIN_OF_SHEET = {
    "02_功能测试": "Android/域控",
    "03_安全岛": "安全岛",
    "04_RDA": "RDA",
    "05_NRDA": "NRDA",
    "06_高温老化": "高温老化",
    "07_低温老化": "低温老化",
    "08_温度循环": "温度循环",
    "09_稳定性": "稳定性",
    "10_诊断网站联动": "诊断网站",
}


def build():
    wb = Workbook()

    # ---------------- 00 说明 ----------------
    ws = wb.active
    ws.title = "00_说明"
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 110

    title = "智能座舱域控（Android + 安全岛 / RDA / NRDA）测试用例集"
    ws.merge_cells("A1:B1")
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=15, color="1F3864")
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 34

    info = [
        ("版本", "V1.0（初版，可直接执行；参数按企业标准调整后升版）"),
        ("被测对象", "智能座舱域控制器：Android 应用域 + 安全岛（Safety Island）+ RDA + NRDA"),
        ("样机状态", "早期烧片样机，具备 root 权限，可直接操作设备节点与调试通道"),
        ("适用范围", "DV（设计验证）阶段功能测试、高低温老化、温度循环、稳定性与诊断系统联动验证"),
        ("关联项目", "NEXUS COCKPIT 智能座舱三域诊断工作台（本仓库 index.html / app.js）"),
        ("用例锚点", "CDC 9 模块：SOC / DDR / 存储 / 射频 / 音频显示 / 外设 / MCU（安全岛·RDA·NRDA）/ 稳定性 / 功耗"),
        ("可执行检查", "cockpit-diag/checks/cockpit.json 中 13 项：ADB、fastboot、CAN 心跳、UDS、ping、DoIP、HMI 端口"),
        ("温度假设", "高温存储 85°C/96h；高温工作 70°C/96h；低温存储 -40°C/96h；低温工作 -30°C/48h；循环 -40↔85°C 20 次"),
        ("时间假设", "老化总时长约 96h/轮；巡检间隔 4h；长稳 72h。可按项目规范整体缩放"),
        ("判定原则", "所有 P0 用例通过方可判定阶段通过；P1 允许有条件的已知问题（需 DEF 跟踪）；任一 P0 失败即阻塞放行"),
        ("日志一致性", "每条用例的『关联日志码』应与诊断网站解析出的 code 一一对应，便于自动化回归"),
        ("命名规范", "F=功能 S=安全岛 R=RDA N=NRDA H=高温 L=低温 C=温度循环 ST=稳定性 D=诊断网站"),
        ("执行记录", "在『执行结果』列选择 Pass / Fail / Blocked / N/A；失败项复制到『11_缺陷记录模板』"),
    ]
    r = 3
    for k, v in info:
        ws.cell(row=r, column=1, value=k).font = Font(bold=True, size=10)
        ws.cell(row=r, column=1).fill = SEC_FILL
        ws.cell(row=r, column=1).alignment = Alignment(vertical="top")
        ws.cell(row=r, column=1).border = BORDER
        c = ws.cell(row=r, column=2, value=v)
        c.font = BODY_FONT
        c.alignment = WRAP
        c.border = BORDER
        ws.row_dimensions[r].height = auto_height([k, v], [22, 110])
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="风险提示").font = Font(bold=True, size=10, color="C00000")
    r += 1
    for tip in [
        "root / 故障注入 / 破坏性用例（S-003、S-004、S-007、ST-005 等）仅限工程样机，量产 user 版本需替换为等效非破坏手段。",
        "老化期间禁止在箱内开箱操作；取放样机需按高低温作业规范防护。",
        "涉及保修与安全件的拆装需先确认责任边界；X-ray / 破坏性分析属于可选加测项。",
    ]:
        ws.cell(row=r, column=2, value="· " + tip).alignment = WRAP
        ws.cell(row=r, column=2).font = BODY_FONT
        ws.row_dimensions[r].height = 32
        r += 1

    # ---------------- 01 总览 ----------------
    ws2 = wb.create_sheet("01_用例总览")
    ws2.column_dimensions["A"].width = 20
    for col in "BCDEF":
        ws2.column_dimensions[col].width = 12

    ws2["A1"] = "用例统计"
    ws2["A1"].font = Font(bold=True, size=12, color="1F3864")

    head = ["测试类别", "用例数", "P0", "P1", "P2", "备注"]
    for i, h in enumerate(head, start=1):
        c = ws2.cell(row=2, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER

    r = 3
    totals = [0, 0, 0, 0]
    for title, rows in SHEETS:
        cnt = len(rows)
        p0 = sum(1 for x in rows if x["priority"] == "P0")
        p1 = sum(1 for x in rows if x["priority"] == "P1")
        p2 = sum(1 for x in rows if x["priority"] == "P2")
        ws2.cell(row=r, column=1, value=title.split("_", 1)[1]).border = BORDER
        ws2.cell(row=r, column=2, value=cnt).border = BORDER
        ws2.cell(row=r, column=3, value=p0).border = BORDER
        ws2.cell(row=r, column=4, value=p1).border = BORDER
        ws2.cell(row=r, column=5, value=p2).border = BORDER
        ws2.cell(row=r, column=6, value="").border = BORDER
        for col in range(1, 6):
            ws2.cell(row=r, column=col).alignment = Alignment(horizontal="center")
        totals[0] += cnt
        totals[1] += p0
        totals[2] += p1
        totals[3] += p2
        r += 1

    ws2.cell(row=r, column=1, value="合计").font = Font(bold=True)
    for i, v in enumerate(totals, start=2):
        c = ws2.cell(row=r, column=i, value=v)
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
    for col in range(1, 7):
        ws2.cell(row=r, column=col).fill = SEC_FILL
        ws2.cell(row=r, column=col).border = BORDER

    # 覆盖矩阵
    r += 3
    ws2.cell(row=r, column=1, value="模块 × 测试类型 覆盖矩阵").font = Font(bold=True, size=12, color="1F3864")
    r += 1
    matrix_head = ["网站模块（CDC）", "功能", "高低温老化", "温度循环", "稳定性", "诊断联动"]
    for i, h in enumerate(matrix_head, start=1):
        c = ws2.cell(row=r, column=i, value=h)
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    ws2.row_dimensions[r].height = 28

    matrix = [
        ("SOC 核心监控", "F-001/F-002", "H-003/H-005", "C-001", "ST-001/ST-003", "D-002/D-004"),
        ("DDR 运行内存", "F-001", "H-005", "C-001", "ST-001", "D-002"),
        ("存储健康检测", "F-010", "H-004", "C-001", "ST-005", "D-002"),
        ("射频短距离", "F-005", "H-008/L-007", "-", "ST-001", "D-001"),
        ("音频显示区", "F-002/F-003", "H-008/L-004/L-007", "C-001", "ST-001", "D-001"),
        ("外设区", "F-004", "H-008/L-008", "C-001", "ST-001", "D-001"),
        ("MCU 监控区（安全岛/RDA/NRDA）", "S-001~S-008 / R-001~R-006 / N-001~N-005", "H-002/L-003", "C-001", "ST-001/ST-006", "D-002/D-005"),
        ("稳定性监控", "F-011", "H-002/L-003", "C-001", "ST-002/ST-006", "D-005"),
        ("功耗监控区", "F-009", "H-006/L-006", "C-003", "ST-003/ST-004", "D-004"),
    ]
    r += 1
    for row in matrix:
        for i, v in enumerate(row, start=1):
            c = ws2.cell(row=r, column=i, value=v)
            c.font = BODY_FONT
            c.alignment = Alignment(wrap_text=True, vertical="center",
                                    horizontal="left" if i == 1 else "center")
            c.border = BORDER
        ws2.row_dimensions[r].height = auto_height(row, [20, 12, 12, 12, 12, 12])
        r += 1

    ws2.freeze_panes = "A3"

    # ---------------- 用例页 ----------------
    for title, rows in SHEETS:
        write_case_sheet(wb, title, rows, note=True)

    # ---------------- 11 缺陷记录模板 ----------------
    ws3 = wb.create_sheet("11_缺陷记录模板")
    head = ["缺陷ID", "发现用例", "域/模块", "现象描述", "发生工况（温度/负载/时长）",
            "复现步骤", "日志与截图附件", "严重度", "责任人", "状态", "关闭结论"]
    widths = [10, 12, 16, 34, 26, 40, 26, 9, 10, 10, 26]
    ws3.append(head)
    for i, w in enumerate(widths, start=1):
        ws3.column_dimensions[get_column_letter(i)].width = w
    for c in ws3[1]:
        c.fill = HEAD_FILL
        c.font = HEAD_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    ws3.row_dimensions[1].height = 30
    example = [
        "DEF-001（示例）", "H-002", "功耗/热", "70°C 老化第 32h 出现 1 次异常重启",
        "70°C，综合负载，运行 32h", "1) 按 H-002 复现\n2) 抓取 last_kmsg\n3) 对比同时段温度曲线",
        "last_kmsg.txt / 温度曲线.png", "严重", "张三", "已关闭", "根因：DDR 高温训练失败；措施：更新 DDR 参数表",
    ]
    ws3.append(example)
    for col in range(1, len(example) + 1):
        c = ws3.cell(row=2, column=col)
        c.font = Font(size=10, italic=True, color="808080")
        c.alignment = WRAP
        c.border = BORDER
    ws3.row_dimensions[2].height = 70
    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = "A1:K1"

    return wb, totals


def main():
    wb, totals = build()
    out = r"D:\Backup\Documents\deepseek-harness\default-workspace\cockpit-test\智能座舱域控测试用例集_V1.0.xlsx"
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    wb.save(out)
    print("saved:", out)
    print("sheets:", len(wb.sheetnames), wb.sheetnames)
    print(f"total cases: {totals[0]}  P0={totals[1]}  P1={totals[2]}  P2={totals[3]}")


if __name__ == "__main__":
    main()
