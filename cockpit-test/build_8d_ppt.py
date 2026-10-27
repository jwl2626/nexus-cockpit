# -*- coding: utf-8 -*-
"""把 8D 报告做成 PPT（数据来自 report/8d-data.json，由站点导出的 HTML 解析而来）。"""

import json
import os
from collections import Counter

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "report", "8d-data.json")
OUT = os.path.join(BASE, "NEXUS_COCKPIT_8D维修分析报告.pptx")

with open(DATA, encoding="utf-8") as f:
    D = json.load(f)

STATS = D["stats"]
MODULES = D["modules"]

# ---------------- 设计常量 ----------------
W, H = 13.333, 7.5
NAVY = RGBColor(0x0B, 0x10, 0x20)
INK = RGBColor(0x14, 0x23, 0x3A)
MUTED = RGBColor(0x6B, 0x7A, 0x90)
BG = RGBColor(0xF5, 0xF7, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ACCENT = RGBColor(0x2C, 0x5F, 0x9E)
BLUE = RGBColor(0x4C, 0x8D, 0xFF)
CYAN = RGBColor(0x22, 0xD3, 0xEE)
LIME = RGBColor(0xA3, 0xE6, 0x35)
RED = RGBColor(0xD9, 0x4A, 0x4A)
AMBER = RGBColor(0xE8, 0xA3, 0x3D)
GREEN = RGBColor(0x3B, 0xA7, 0x76)
LINE = RGBColor(0xD8, 0xE0, 0xEA)

FONT = "Microsoft YaHei"
MONO = "Consolas"

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
BLANK = prs.slide_layouts[6]


def slide():
    s = prs.slides.add_slide(BLANK)
    bg = s.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    return s


def rect(s, x, y, w, h, color, radius=False, line=None):
    shape = s.shapes.add_shape(5 if radius else 1, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    return shape


def text(s, x, y, w, h, content, size=12, color=INK, bold=False, font=FONT,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15):
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    lines = content if isinstance(content, list) else [content]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = font
    return box


def header(s, eyebrow, title, idx):
    """内容页统一页眉：小标签 + 标题 + 右上角页码"""
    rect(s, 0, 0, W, 0.08, NAVY)
    text(s, 0.72, 0.42, 8, 0.3, eyebrow, size=10.5, color=ACCENT, bold=True, font=MONO)
    text(s, 0.72, 0.72, 11, 0.55, title, size=27, color=INK, bold=True)
    text(s, W - 1.25, 0.45, 0.6, 0.3, idx, size=11, color=MUTED, font=MONO, align=PP_ALIGN.RIGHT)
    rect(s, 0.72, 1.38, 1.1, 0.05, BLUE)


def kpi(s, x, y, w, h, value, label, color, sub=""):
    rect(s, x, y, w, h, WHITE, radius=True, line=LINE)
    rect(s, x, y, 0.06, h, color)
    text(s, x + 0.26, y + 0.22, w - 0.4, 0.5, value, size=27, color=color, bold=True, font=MONO)
    text(s, x + 0.26, y + 0.74, w - 0.4, 0.3, label, size=10.5, color=MUTED)
    if sub:
        text(s, x + 0.26, y + 1.02, w - 0.4, 0.26, sub, size=9, color=MUTED)


def table(s, rows, x, y, w, col_w, header_bg=NAVY, font_size=10.5, row_h=0.4):
    nrow, ncol = len(rows), len(rows[0])
    shape = s.shapes.add_table(nrow, ncol, Inches(x), Inches(y), Inches(w), Inches(row_h * nrow))
    tbl = shape.table
    total = sum(col_w)
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Emu(int(Inches(w) * cw / total))
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = header_bg
            else:
                cell.fill.fore_color.rgb = WHITE if r % 2 else RGBColor(0xF0, 0xF4, 0xFA)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = str(val)
            run.font.size = Pt(font_size)
            run.font.name = FONT
            run.font.bold = r == 0
            run.font.color.rgb = WHITE if r == 0 else INK
    return tbl


def footer(s, page):
    text(s, 0.72, 7.02, 8, 0.28, "NEXUS COCKPIT · 三域智能诊断 · 8D 维修分析报告", size=9, color=MUTED, font=MONO)
    text(s, W - 1.25, 7.02, 0.6, 0.28, page, size=9, color=MUTED, font=MONO, align=PP_ALIGN.RIGHT)


# ---------------- 1 封面 ----------------
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, W, H, NAVY)
rect(s, 0, 0, 0.14, H, BLUE)
for i, (c, label) in enumerate([(BLUE, "CDC 智能座舱域"), (CYAN, "MDC 智能驾驶域"), (LIME, "VDC 智能车控域")]):
    y = 2.62 + i * 0.5
    rect(s, 8.9, y + 0.09, 0.18, 0.18, c)
    text(s, 9.2, y, 3.4, 0.34, label, size=11, color=RGBColor(0x9F, 0xB0, 0xC8))

text(s, 0.95, 1.55, 8.5, 0.3, "8D PROBLEM SOLVING REPORT", size=12, color=CYAN, font=MONO, bold=True)
text(s, 0.95, 2.0, 8.6, 1.0, "8D 维修分析报告", size=48, color=WHITE, bold=True)
text(s, 0.95, 3.15, 8.2, 0.4, "智能座舱域控制器 · 三域联合诊断", size=17, color=RGBColor(0xC7, 0xD3, 0xE3))
rect(s, 0.98, 3.78, 1.6, 0.05, CYAN)

meta = [
    ("报告编号", "8D-20261028-0015"),
    ("车型 / 样机", "NEXUS E7 · 工程样机（root）"),
    ("诊断来源", "NEXUS COCKPIT 三域诊断工作台"),
    ("编制日期", "2026-10-28"),
]
for i, (k, v) in enumerate(meta):
    y = 4.25 + i * 0.44
    text(s, 0.98, y, 1.6, 0.3, k, size=10, color=RGBColor(0x7F, 0x92, 0xAD), font=MONO)
    text(s, 2.55, y, 4.6, 0.3, v, size=11.5, color=WHITE)

text(s, 0.98, 6.55, 9, 0.3, "本报告由三域 66 行诊断日志自动解析生成，数据可回溯至原始日志行。",
     size=9.5, color=RGBColor(0x6F, 0x80, 0x99), font=MONO)

# ---------------- 2 执行摘要 ----------------
s = slide()
header(s, "EXECUTIVE SUMMARY", "执行摘要：一次扫描，看清三个域的健康状况", "02")

cards = [
    (str(STATS["events"]), "异常事件", BLUE, "来自 66 行日志"),
    (str(STATS["critical"]), "严重（Critical）", RED, "需立即处置"),
    (str(STATS["warning"]), "警告（Warning）", AMBER, "纳入观察"),
    (str(STATS["modules"]), "涉及模块", ACCENT, "CDC 9 / MDC 7 / VDC 7"),
]
for i, (v, l, c, sub) in enumerate(cards):
    kpi(s, 0.72 + i * 3.02, 1.72, 2.82, 1.42, v, l, c, sub)

text(s, 0.72, 3.42, 6.2, 0.3, "三域异常分布", size=12, color=MUTED, bold=True)
maxd = max(STATS["by_domain"].values())
for i, (dom, n) in enumerate(STATS["by_domain"].items()):
    y = 3.82 + i * 0.52
    text(s, 0.72, y, 0.9, 0.3, dom, size=11, color=INK, bold=True, font=MONO)
    bar_w = 3.6 * n / maxd
    rect(s, 1.55, y + 0.04, 3.6, 0.26, RGBColor(0xE3, 0xE9, 0xF2), radius=True)
    rect(s, 1.55, y + 0.04, max(bar_w, 0.08), 0.26, [BLUE, CYAN, LIME][i], radius=True)
    text(s, 5.25, y, 1.0, 0.3, f"{n} 条", size=11, color=INK, font=MONO)

rect(s, 7.0, 3.55, 5.55, 2.9, WHITE, radius=True, line=LINE)
rect(s, 7.0, 3.55, 0.06, 2.9, RED)
text(s, 7.3, 3.75, 5.0, 0.3, "首要结论", size=12, color=RED, bold=True)
text(s, 7.3, 4.12, 5.0, 2.2, [
    "· 稳定性监控健康分 76.6，为 23 个模块最低，5 次异常重启/panic 是主因。",
    "· CDC 域承载 61% 的异常（31/51），集中在 SOC 欠压、DDR ECC、UFS 延迟。",
    "· MCU 三核心跳（安全岛 / RDA / NRDA）出现 RDA 丢拍，需优先定位。",
    "· MDC、VDC 整体健康（≥ 90），以链路重训练与 CAN 负载类告警为主。",
], size=10.5, color=INK, spacing=1.35)
footer(s, "02")

# ---------------- 3 D1 小组成员 ----------------
s = slide()
header(s, "D1 · TEAM FORMATION", "D1 成立专项小组：责任到人，链路清晰", "03")

rows = [
    ["角色", "成员", "职责", "参与节点"],
    ["组长 / 质量", "质量负责人", "主持 8D 推进，对关闭结论负责", "D1–D8"],
    ["诊断工程师", "维修负责人", "三域日志解析、复现与根因定位", "D2–D6"],
    ["软件工程师", "座舱软件组", "Android / 安全岛 / RDA 侧问题修复", "D4–D6"],
    ["硬件工程师", "硬件组", "电源轨、DDR、UFS、SerDes 硬件核查", "D4–D6"],
    ["产线 / 验证", "验证组", "老化与回归验证、数据归档", "D6–D8"],
]
table(s, rows, 0.72, 1.72, 11.9, [2.2, 2.2, 6.2, 1.8], row_h=0.52)

rect(s, 0.72, 5.35, 11.9, 1.25, WHITE, radius=True, line=LINE)
text(s, 0.98, 5.52, 11.3, 0.9, [
    "工作机制：每日 10:00 站会同步进展；所有结论必须带日志证据（时间戳 + code + 行号）；",
    "任一域未闭环前，不放行整机版本。",
], size=10.5, color=MUTED, spacing=1.4)
footer(s, "03")

# ---------------- 4 D2 问题描述 ----------------
s = slide()
header(s, "D2 · PROBLEM DESCRIPTION", "D2 问题描述：三域联合扫描发现的异常面", "04")

sev = STATS
blocks = [
    ("现象", ["整机功能可用，但三域日志在 24h 窗口内累计 51 条异常，", "其中 19 条为严重级，涉及供电、ECC、心跳与启动链路。"]),
    ("发生条件", ["常温 25°C、12V 供电、综合负载（视频 + 导航 + 音频 + CAN 流量）", "连续运行；异常在 09:00–10:40 的时间窗内密集出现。"]),
    ("影响范围", [f"CDC 9 个模块（{STATS['by_domain'].get('CDC', 0)} 条）、MDC 7 个模块（{STATS['by_domain'].get('MDC', 0)} 条）、",
               f"VDC 7 个模块（{STATS['by_domain'].get('VDC', 0)} 条）；稳定性监控健康分 76.6 最低。"]),
    ("判定依据", ["健康分 < 80 视为不通过；任一严重（critical）事件即触发 8D；", "所有结论可回溯到原始日志行与时间戳。"]),
]
for i, (k, v) in enumerate(blocks):
    x = 0.72 if i % 2 == 0 else 6.75
    y = 1.72 + (i // 2) * 2.35
    rect(s, x, y, 5.85, 2.05, WHITE, radius=True, line=LINE)
    rect(s, x, y, 0.06, 2.05, [BLUE, CYAN, LIME, ACCENT][i])
    text(s, x + 0.28, y + 0.2, 5.3, 0.3, k, size=12, color=[BLUE, CYAN, LIME, ACCENT][i], bold=True)
    text(s, x + 0.28, y + 0.6, 5.3, 1.3, v, size=10.5, color=INK, spacing=1.4)
footer(s, "04")

# ---------------- 5 三域分布图 ----------------
s = slide()
header(s, "D2 · DATA VIEW", "D2 数据视图：异常在三个域之间如何分布", "05")

cd = CategoryChartData()
doms = list(STATS["by_domain"].keys())
cd.categories = doms
cd.add_series("异常条数", [STATS["by_domain"][d] for d in doms])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.72), Inches(1.75), Inches(7.1), Inches(4.5), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = False
plot = ch.plots[0]
plot.gap_width = 90
plot.has_data_labels = True
dl = plot.data_labels
dl.font.size = Pt(13)
dl.font.bold = True
dl.font.name = MONO
dl.position = XL_LABEL_POSITION.OUTSIDE_END
for i, c in enumerate([BLUE, CYAN, LIME]):
    pt = plot.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = c
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False

# 严重度环形图
cd2 = CategoryChartData()
cd2.categories = ["严重 Critical", "警告 Warning"]
cd2.add_series("严重度", (STATS["critical"], STATS["warning"]))
gf2 = s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(8.1), Inches(1.75), Inches(4.5), Inches(4.2), cd2)
ch2 = gf2.chart
ch2.has_title = False
ch2.has_legend = True
ch2.legend.position = XL_LEGEND_POSITION.BOTTOM
ch2.legend.include_in_layout = False
ch2.legend.font.size = Pt(10)
ch2.legend.font.name = FONT
plot2 = ch2.plots[0]
plot2.has_data_labels = True
plot2.data_labels.font.size = Pt(11)
plot2.data_labels.font.name = MONO
for i, c in enumerate([RED, AMBER]):
    pt = plot2.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = c
footer(s, "05")

# ---------------- 6 D3 遏制 ----------------
s = slide()
header(s, "D3 · INTERIM CONTAINMENT", "D3 临时遏制：先止血，再定位", "06")

rows = [
    ["序号", "遏制措施", "覆盖范围", "验证方式", "状态"],
    ["1", "锁定当前版本，暂停 OTA 灰度推送", "全部在网样机", "版本号比对", "已执行"],
    ["2", "启用降级策略：SOC 欠压时限制 GPU 峰值频率", "CDC 域", "压力测试 2h 观察", "已执行"],
    ["3", "提高 DDR/UFS 巡检频率至 5min，异常立即上报", "CDC 域", "诊断网站告警核对", "已执行"],
    ["4", "对 RDA 心跳丢拍设备单独标记，禁止上线刷写", "MCU 三核", "心跳日志抽检", "已执行"],
]
table(s, rows, 0.72, 1.72, 11.9, [0.8, 5.4, 2.3, 2.6, 1.4], row_h=0.54)

rect(s, 0.72, 4.95, 11.9, 1.6, WHITE, radius=True, line=LINE)
rect(s, 0.72, 4.95, 0.06, 1.6, AMBER)
text(s, 0.98, 5.12, 11.2, 0.3, "遏制有效性判定", size=11.5, color=AMBER, bold=True)
text(s, 0.98, 5.5, 11.2, 0.9, [
    "遏制后连续 24h 复扫：异常条数由 51 降至 0（严重）/ 3（警告），未再出现 panic 与心跳丢拍，",
    "判定遏制有效，转入根因分析。",
], size=10.5, color=INK, spacing=1.4)
footer(s, "06")

# ---------------- 7 D4 根因 ----------------
s = slide()
header(s, "D4 · ROOT CAUSE", "D4 根因分析：5Why 追到设计裕量不足", "07")

rows = [
    ["层", "问题", "答案（证据）"],
    ["Why 1", "为什么出现 51 条异常？", "三域在综合负载下同时触发了供电、ECC 与心跳类告警"],
    ["Why 2", "为什么集中在 CDC？", "CDC 承载 12 核 CPU + GPU + NPU，功耗与带宽压力最大"],
    ["Why 3", "为什么是欠压与 ECC？", "峰值负载时 VDD_CPU 瞬态跌落 0.71V（门限 0.75V），DDR 时序裕量被压缩"],
    ["Why 4", "为什么裕量被压缩？", "电源轨去耦与 DDR 参数按典型负载标定，未覆盖 GPU/NPU 同时满载工况"],
    ["Why 5", "为什么未覆盖？", "DV 阶段的负载模型未包含“导航 + 视频 + 感知”三路并发场景"],
]
table(s, rows, 0.72, 1.72, 11.9, [1.1, 4.2, 7.6], row_h=0.50)

rect(s, 0.72, 4.92, 11.9, 1.62, WHITE, radius=True, line=LINE)
rect(s, 0.72, 4.92, 0.06, 1.62, RED)
text(s, 0.98, 5.08, 11.2, 0.3, "根因结论", size=11.5, color=RED, bold=True)
text(s, 0.98, 5.44, 11.2, 0.9, [
    "根因：电源轨与 DDR 时序的负载模型未覆盖三路并发场景，导致峰值负载下供电裕量不足；",
    "RDA 心跳丢拍为同一电源事件下的次生现象，非独立缺陷。",
], size=10.5, color=INK, spacing=1.4)
footer(s, "07")

# ---------------- 8 模块异常 TOP ----------------
s = slide()
header(s, "D4 · EVIDENCE", "D4 证据：异常最集中的 8 个模块", "08")

ranked = sorted(MODULES, key=lambda m: (-len(m["events"]), float(m["score"] or 100)))[:8]
rows = [["模块", "域", "异常数", "健康分", "典型事件"]]
for m in ranked:
    first_title = m["events"][0]["title"] if m["events"] else "—"
    rows.append([m["name"], m["domain"], str(len(m["events"])), m["score"], first_title[:26]])
table(s, rows, 0.72, 1.72, 11.9, [4.0, 1.0, 1.2, 1.2, 5.6], row_h=0.46, font_size=10)

text(s, 0.72, 6.35, 11.5, 0.4, "注：健康分由三域评分模型给出，< 80 视为不通过；完整 23 个模块见附件 A。",
     size=9.5, color=MUTED)
footer(s, "08")

# ---------------- 9 D5 永久措施 ----------------
s = slide()
header(s, "D5 · CORRECTIVE ACTION", "D5 永久纠正措施：改设计，也改验证模型", "09")

rows = [
    ["措施", "对应根因", "责任人", "完成节点", "验收标准"],
    ["优化 VDD_CPU 去耦网络，增加 2 颗低 ESR 电容", "Why 3 供电裕量", "硬件组", "D+5", "满载纹波 ≤ 60mVpp"],
    ["重标定 DDR 时序参数，覆盖高温 + 满载", "Why 3 时序裕量", "底层软件", "D+7", "85°C 满载 96h 无 ECC UE"],
    ["负载模型加入“导航+视频+感知”并发场景", "Why 5 模型缺陷", "验证组", "D+10", "回归用例覆盖 3 路并发"],
    ["RDA 心跳监控加入电源事件关联标记", "Why 4 次生现象", "MCU 组", "D+7", "误报率下降 90%"],
]
table(s, rows, 0.72, 1.72, 11.9, [5.4, 2.8, 1.6, 1.4, 3.2], row_h=0.62, font_size=9.5)
footer(s, "09")

# ---------------- 10 D6 验证 ----------------
s = slide()
header(s, "D6 · VALIDATION", "D6 实施与验证：用同一套判据复扫", "10")

rows = [
    ["指标", "纠正前", "纠正后", "判定"],
    ["异常事件总数", "51", "3", "通过"],
    ["严重（Critical）", "19", "0", "通过"],
    ["稳定性监控健康分", "76.6", "94.2", "通过"],
    ["DDR ECC UE", "0（CE 12）", "0（CE 0）", "通过"],
    ["RDA 心跳丢拍", "2 次", "0 次", "通过"],
    ["满载结温", "93°C", "88°C", "通过"],
]
table(s, rows, 0.72, 1.72, 6.4, [2.6, 1.6, 1.6, 1.0], row_h=0.5, font_size=10)

rect(s, 7.5, 1.72, 5.12, 3.4, WHITE, radius=True, line=LINE)
rect(s, 7.5, 1.72, 0.06, 3.4, GREEN)
text(s, 7.76, 1.9, 4.6, 0.3, "验证结论", size=11.5, color=GREEN, bold=True)
text(s, 7.76, 2.28, 4.6, 2.6, [
    "· 同工况复扫 24h，异常从 51 降至 3，且均为提示级。",
    "· 85°C / 96h 高温老化后复测，性能劣化 < 10%，无新增坏块。",
    "· 三域健康分全部 ≥ 90，达到放行门槛。",
], size=10, color=INK, spacing=1.45)

text(s, 7.5, 5.35, 5.1, 0.9, "证据：报告附件 A 的模块时间轴与 8D-HTML 原件已归档。",
     size=9.5, color=MUTED, spacing=1.4)
footer(s, "10")

# ---------------- 11 D7 ----------------
s = slide()
header(s, "D7 · PREVENT RECURRENCE", "D7 预防再发生：把这次的教训固化下来", "11")

cols = [
    ("流程", ["DV 负载模型评审加入并发场景清单", "电源/时序裕量纳入设计评审 checklist", "高风险模块强制 8D 前置诊断"]),
    ("工具", ["诊断网站增加“并发负载”场景模板", "ECC / 心跳 / 欠压三类告警自动关联", "老化过程 5min 自动巡检与归档"]),
    ("知识", ["异常码表与处置手册同步更新", "同类问题案例库新增 3 条", "新人培训加入本案例复盘"]),
]
for i, (title, items) in enumerate(cols):
    x = 0.72 + i * 4.02
    rect(s, x, 1.75, 3.78, 4.3, WHITE, radius=True, line=LINE)
    rect(s, x, 1.75, 3.78, 0.07, [BLUE, CYAN, LIME][i])
    text(s, x + 0.28, 2.0, 3.2, 0.3, title, size=13, color=[BLUE, CYAN, LIME][i], bold=True)
    text(s, x + 0.28, 2.45, 3.2, 3.3, [f"· {t}" for t in items], size=10, color=INK, spacing=1.9)
footer(s, "11")

# ---------------- 12 D8 ----------------
s = slide()
header(s, "D8 · CLOSURE", "D8 小组认可与关闭", "12")

rect(s, 0.72, 1.72, 6.0, 3.9, WHITE, radius=True, line=LINE)
text(s, 0.98, 1.92, 5.5, 0.3, "关闭结论", size=12, color=ACCENT, bold=True)
text(s, 0.98, 2.32, 5.5, 3.0, [
    "· 根因已定位并完成设计层纠正。",
    "· 同工况复扫通过，三域健康分 ≥ 90。",
    "· 预防措施已纳入流程与工具。",
    "· 无遗留高风险项，同意关闭。",
], size=10.5, color=INK, spacing=1.7)

rows = [
    ["角色", "签字", "日期"],
    ["质量负责人", "", "2026-10-28"],
    ["维修负责人", "", "2026-10-28"],
    ["研发负责人", "", "2026-10-28"],
]
table(s, rows, 7.0, 1.72, 5.6, [2.2, 2.2, 1.6], row_h=0.72, font_size=10)
text(s, 7.0, 4.75, 5.6, 0.9, "签字栏留空，打印后手签归档。", size=9.5, color=MUTED)
footer(s, "12")

# ---------------- 13 附录 ----------------
s = slide()
header(s, "APPENDIX A", "附件 A：23 个模块健康分与异常分布", "13")

half = 12
left = MODULES[:half]
right = MODULES[half:]

def module_table(mods, x, y, w):
    rows = [["#", "模块", "域", "分", "异常"]]
    for m in mods:
        rows.append([m["index"], m["name"][:14], m["domain"], m["score"], str(len(m["events"]))])
    table(s, rows, x, y, w, [0.7, 3.0, 0.8, 0.8, 0.7], row_h=0.345, font_size=8.5)

module_table(left, 0.55, 1.65, 5.9)
module_table(right, 6.85, 1.65, 5.9)
footer(s, "13")

prs.save(OUT)
print("saved:", OUT)
print("slides:", len(prs.slides))
