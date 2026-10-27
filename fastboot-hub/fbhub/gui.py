"""Tkinter desktop UI for the multi-device fastboot tool."""

from __future__ import annotations

import queue
import shlex
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Optional

from .config import Config
from .discovery import list_devices
from .models import Device, DeviceResult, FbhubError
from .plan import Step, load_plan, parse_flash_pair, step_from_tokens
from .service import Event, run_on_devices, save_results_csv

CHECKED = "☑"
UNCHECKED = "☐"

REBOOT_TARGETS = {
    "系统": None,
    "Bootloader": "bootloader",
    "Fastbootd": "fastboot",
    "Recovery": "recovery",
    "EDL / 9008": "edl",
}

class ScrollableFrame(ttk.Frame):
    """A frame with a vertical scrollbar for the command panel."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=10)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor=tk.NW)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


COMMON_PARTITIONS = (
    "boot",
    "init_boot",
    "vendor_boot",
    "recovery",
    "vbmeta",
    "vbmeta_system",
    "dtbo",
    "super",
    "system",
    "vendor",
    "odm",
    "product",
    "system_ext",
    "userdata",
    "cache",
    "boot_a",
    "boot_b",
    "vendor_boot_a",
    "vendor_boot_b",
)


class App(tk.Tk):
    def __init__(self, config: Config, auto_refresh: bool = True):
        super().__init__()
        self.cfg = config
        self.auto_refresh_enabled = auto_refresh

        self.title("fbhub · 多设备 Fastboot 工装")
        self.geometry("1280x800")
        self.minsize(1050, 680)

        self.devices: dict[str, Device] = {}
        self.selected: set[str] = set()
        self.busy = False
        self.refreshing = False
        self.stop_event = threading.Event()
        self.queue: queue.Queue = queue.Queue()
        self.last_results: list[DeviceResult] = []
        self.row_state: dict[str, tuple[str, str, str, str]] = {}
        self._widget_states: dict[tk.Widget, str] = {}
        self._last_device_count: Optional[int] = None
        self.log_file = None

        self._build_style()
        self._build_ui()
        self._set_busy(False)
        self.after(100, self._poll_queue)
        self.after(300, self.refresh)
        self.after(1000, self._auto_tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_style(self) -> None:
        style = ttk.Style(self)
        available = style.theme_names()
        for theme in ("vista", "winnative", "clam"):
            if theme in available:
                try:
                    style.theme_use(theme)
                    break
                except tk.TclError:
                    continue
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Hint.TLabel", foreground="#666666")
        style.configure("Danger.TButton", foreground="#a00000")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="多设备 Fastboot", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            header,
            text="按 USB 物理路径定位设备，不依赖序列号",
            style="Hint.TLabel",
        ).pack(side=tk.LEFT, padx=(12, 0), pady=(4, 0))

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        self.refresh_button = ttk.Button(toolbar, text="刷新设备", command=self.refresh)
        self.refresh_button.pack(side=tk.LEFT)
        ttk.Button(toolbar, text="全选", command=self.select_all).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="全不选", command=self.select_none).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="设置别名", command=self.edit_alias).pack(side=tk.LEFT, padx=(6, 0))
        self.stop_button = ttk.Button(toolbar, text="停止", command=self.stop_job)
        self.stop_button.pack(side=tk.LEFT, padx=(18, 0))
        self.auto_var = tk.BooleanVar(value=self.auto_refresh_enabled)
        ttk.Checkbutton(
            toolbar, text="自动刷新", variable=self.auto_var
        ).pack(side=tk.RIGHT)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(toolbar, textvariable=self.status_var, style="Hint.TLabel").pack(
            side=tk.RIGHT, padx=(0, 12)
        )

        body = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        right = ttk.Frame(body, width=360)
        body.add(left, weight=4)
        body.add(right, weight=2)

        columns = ("sel", "path", "alias", "serial", "product", "state", "progress", "message")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        headings = {
            "sel": "",
            "path": "USB 路径",
            "alias": "别名",
            "serial": "SN",
            "product": "产品",
            "state": "状态",
            "progress": "进度",
            "message": "当前操作",
        }
        widths = {
            "sel": 34,
            "path": 150,
            "alias": 100,
            "serial": 150,
            "product": 180,
            "state": 70,
            "progress": 62,
            "message": 260,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column], anchor=tk.W)
            self.tree.column(
                column,
                width=widths[column],
                minwidth=30,
                anchor=tk.W if column not in {"sel", "state", "progress"} else tk.CENTER,
                stretch=column in {"message", "product"},
            )
        self.tree.tag_configure("ok", foreground="#0a7a0a")
        self.tree.tag_configure("fail", foreground="#b00020")
        self.tree.tag_configure("busy", foreground="#0b5394")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", lambda event: self.show_info())
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="查看设备信息", command=self.show_info)
        self.context_menu.add_command(label="设置别名…", command=self.edit_alias)
        self.context_menu.add_command(label="复制 USB 路径", command=self.copy_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="全选", command=self.select_all)
        self.context_menu.add_command(label="全不选", command=self.select_none)

        self._build_actions(right)

        log_frame = ttk.LabelFrame(outer, text="日志", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=False, pady=(8, 0))
        self.log_text = ScrolledText(
            log_frame, height=11, state=tk.DISABLED, font=("Consolas", 9),
            wrap=tk.WORD, background="#111418", foreground="#d8dee9",
            insertbackground="#d8dee9",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("error", foreground="#ff6b6b")
        self.log_text.tag_configure("warn", foreground="#f0c674")
        self.log_text.tag_configure("ok", foreground="#8ec07c")
        self.log_text.tag_configure("info", foreground="#d8dee9")

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(footer, text="导出结果 CSV", command=self.export_results).pack(side=tk.LEFT)
        ttk.Button(footer, text="清空日志", command=self.clear_log).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(
            footer,
            text="提示：危险操作会二次确认；设备无 SN 时按 USB 路径识别。",
            style="Hint.TLabel",
        ).pack(side=tk.RIGHT)

    def _build_actions(self, parent: ttk.Frame) -> None:
        self.action_widgets: list[tk.Widget] = []
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook = notebook

        flash_scroll = ScrollableFrame(notebook)
        command_scroll = ScrollableFrame(notebook)
        notebook.add(flash_scroll, text="刷写")
        notebook.add(command_scroll, text="常用命令")
        flash_tab = flash_scroll.inner
        command_tab = command_scroll.inner

        # Flash tab --------------------------------------------------------
        ttk.Label(flash_tab, text="单个分区刷写", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )
        ttk.Label(flash_tab, text="分区").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.partition_var = tk.StringVar(value="boot")
        self.partition_box = ttk.Combobox(
            flash_tab, textvariable=self.partition_var, values=COMMON_PARTITIONS, width=24
        )
        self.partition_box.grid(row=1, column=1, sticky=tk.EW, pady=3)
        self.action_widgets.append(self.partition_box)

        ttk.Label(flash_tab, text="镜像").grid(row=2, column=0, sticky=tk.W, pady=3)
        image_frame = ttk.Frame(flash_tab)
        image_frame.grid(row=2, column=1, sticky=tk.EW, pady=3)
        self.image_var = tk.StringVar()
        image_entry = ttk.Entry(image_frame, textvariable=self.image_var)
        image_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        browse = ttk.Button(image_frame, text="…", width=3, command=self.browse_image)
        browse.pack(side=tk.LEFT, padx=(4, 0))
        self.action_widgets.extend([image_entry, browse])

        flash_button = ttk.Button(
            flash_tab, text="刷写到选中设备", command=self.flash_selected
        )
        flash_button.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(14, 4))
        self.action_widgets.append(flash_button)

        plan_button = ttk.Button(flash_tab, text="加载并执行计划…", command=self.run_plan)
        plan_button.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=4)
        self.action_widgets.append(plan_button)

        ttk.Separator(flash_tab, orient=tk.HORIZONTAL).grid(
            row=5, column=0, columnspan=2, sticky=tk.EW, pady=14
        )
        ttk.Label(
            flash_tab,
            text=(
                "大镜像会自动转换为 sparse 并按\n"
                "max-download-size 分片；raw / sparse\n"
                "镜像都可以直接选择。"
            ),
            style="Hint.TLabel",
        ).grid(row=6, column=0, columnspan=2, sticky=tk.W)
        flash_tab.columnconfigure(1, weight=1)

        # Command tab ------------------------------------------------------
        command_tab.columnconfigure(1, weight=1)

        ttk.Label(command_tab, text="重启", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8)
        )
        self.reboot_var = tk.StringVar(value="系统")
        reboot_box = ttk.Combobox(
            command_tab, textvariable=self.reboot_var,
            values=list(REBOOT_TARGETS), state="readonly", width=24,
        )
        reboot_box.grid(row=1, column=0, sticky=tk.EW, pady=3)
        self.action_widgets.append(reboot_box)
        reboot_button = ttk.Button(command_tab, text="重启", command=self.reboot_selected)
        reboot_button.grid(row=1, column=1, sticky=tk.EW, pady=3)
        self.action_widgets.append(reboot_button)

        ttk.Label(command_tab, text="Bootloader", style="Title.TLabel").grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(14, 8)
        )
        unlock_button = ttk.Button(
            command_tab, text="解锁 (unlock)", command=lambda: self.flashing("unlock")
        )
        unlock_button.grid(row=3, column=0, sticky=tk.EW, pady=3)
        lock_button = ttk.Button(
            command_tab, text="上锁 (lock)", command=lambda: self.flashing("lock")
        )
        lock_button.grid(row=3, column=1, sticky=tk.EW, pady=3)
        self.action_widgets.extend([unlock_button, lock_button])

        ability_button = ttk.Button(
            command_tab, text="查询解锁能力", command=lambda: self.flashing("get_unlock_ability")
        )
        ability_button.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=3)
        self.action_widgets.append(ability_button)

        ttk.Label(command_tab, text="擦除分区", style="Title.TLabel").grid(
            row=5, column=0, columnspan=2, sticky=tk.W, pady=(14, 8)
        )
        self.erase_var = tk.StringVar(value="misc")
        erase_entry = ttk.Entry(command_tab, textvariable=self.erase_var)
        erase_entry.grid(row=6, column=0, sticky=tk.EW, pady=3)
        erase_button = ttk.Button(command_tab, text="擦除", command=self.erase_selected)
        erase_button.grid(row=6, column=1, sticky=tk.EW, pady=3)
        self.action_widgets.extend([erase_entry, erase_button])

        ttk.Label(command_tab, text="读取变量", style="Title.TLabel").grid(
            row=7, column=0, columnspan=2, sticky=tk.W, pady=(14, 8)
        )
        self.getvar_var = tk.StringVar(value="current-slot")
        getvar_entry = ttk.Entry(command_tab, textvariable=self.getvar_var)
        getvar_entry.grid(row=8, column=0, sticky=tk.EW, pady=3)
        getvar_button = ttk.Button(command_tab, text="读取", command=self.getvar_selected)
        getvar_button.grid(row=8, column=1, sticky=tk.EW, pady=3)
        self.action_widgets.extend([getvar_entry, getvar_button])

        info_button = ttk.Button(command_tab, text="查看设备信息 (getvar all)",
                                 command=self.show_info)
        info_button.grid(row=9, column=0, columnspan=2, sticky=tk.EW, pady=(3, 12))
        self.action_widgets.append(info_button)

        ttk.Label(command_tab, text="原始 fastboot 命令", style="Title.TLabel").grid(
            row=10, column=0, columnspan=2, sticky=tk.W, pady=(10, 8)
        )
        self.raw_var = tk.StringVar(value="oem edl")
        raw_entry = ttk.Entry(command_tab, textvariable=self.raw_var)
        raw_entry.grid(row=11, column=0, sticky=tk.EW, pady=3)
        raw_button = ttk.Button(command_tab, text="执行", command=self.raw_selected)
        raw_button.grid(row=11, column=1, sticky=tk.EW, pady=3)
        self.action_widgets.extend([raw_entry, raw_button])

        ttk.Label(
            command_tab,
            text="命令会同时发送到所有勾选设备。\n"
                 "重启后设备会重新枚举，本工具不会自动续跑后续步骤。",
            style="Hint.TLabel",
        ).grid(row=12, column=0, columnspan=2, sticky=tk.W, pady=(16, 0))

    # -------------------------------------------------------------- helpers
    def log(self, text: str, level: str = "info") -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{stamp}] {text}\n", level if level in {"error", "warn", "ok"} else "info")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _refresh_status(self) -> None:
        if self.busy:
            self.status_var.set(f"执行中 · 设备 {len(self.devices)} 台 · 已选 {len(self.selected)} 台")
        else:
            self.status_var.set(f"设备 {len(self.devices)} 台 · 已选 {len(self.selected)} 台")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        if busy:
            self._widget_states = {}
            for widget in self.action_widgets:
                try:
                    self._widget_states[widget] = str(widget.cget("state"))
                    widget.configure(state=tk.DISABLED)
                except tk.TclError:
                    pass
            self.refresh_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.NORMAL)
        else:
            for widget, state in self._widget_states.items():
                try:
                    widget.configure(state=state)
                except tk.TclError:
                    pass
            self._widget_states = {}
            self.refresh_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.DISABLED)
        self._refresh_status()

    def _on_close(self) -> None:
        if self.busy:
            if not messagebox.askyesno("退出", "任务仍在执行，确定退出吗？", parent=self):
                return
            self.stop_event.set()
        self.destroy()

    def selected_devices(self) -> list[Device]:
        return [self.devices[path] for path in sorted(self.selected) if path in self.devices]

    # ----------------------------------------------------------- refreshing
    def refresh(self) -> None:
        if self.busy or self.refreshing:
            return
        self.refreshing = True
        self.status_var.set("正在扫描 USB…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            devices = list_devices(self.cfg)
            self.queue.put(("devices", devices, None))
        except Exception as exc:
            self.queue.put(("devices", [], exc))

    def _apply_devices(self, devices: list[Device], error: Optional[Exception]) -> None:
        self.refreshing = False
        if error is not None:
            self.log(f"扫描设备失败: {error}", "error")
            self.status_var.set("扫描失败")
            return
        current = {device.location: device for device in devices}
        for location in list(self.devices):
            if location not in current:
                self.selected.discard(location)
                self.devices.pop(location, None)
                self.row_state.pop(location, None)
                if self.tree.exists(location):
                    self.tree.delete(location)
        for device in devices:
            self.devices[device.location] = device
            checked = CHECKED if device.location in self.selected else UNCHECKED
            values = [
                checked,
                device.location,
                device.alias or "-",
                device.serial_display,
                device.product or "-",
                "已选" if device.location in self.selected else "就绪",
                "-",
                "",
            ]
            tags: tuple[str, ...] = ()
            if not self.busy and device.location in self.row_state:
                state, progress, message, tag = self.row_state[device.location]
                values[5] = state
                values[6] = progress
                values[7] = message
                tags = (tag,) if tag else ()
            if self.tree.exists(device.location):
                self.tree.item(device.location, values=values, tags=tags)
            else:
                self.tree.insert("", tk.END, iid=device.location, values=values, tags=tags)
        self._refresh_status()
        if not devices and self._last_device_count != 0:
            self.log("未发现 fastboot 设备。检查设备模式/驱动，或运行 `fbhub doctor`。", "warn")
        elif devices and self._last_device_count in (0, None):
            self.log(f"发现 {len(devices)} 台 fastboot 设备。", "ok")
        self._last_device_count = len(devices)
        self._update_row_states()

    def _update_row_states(self) -> None:
        for location in self.devices:
            if not self.tree.exists(location):
                continue
            values = list(self.tree.item(location, "values"))
            values[0] = CHECKED if location in self.selected else UNCHECKED
            if not self.busy and location not in self.row_state:
                values[5] = "已选" if location in self.selected else "就绪"
            self.tree.item(location, values=values)
        self._refresh_status()

    def _auto_tick(self) -> None:
        if self.auto_var.get() and not self.busy:
            self.refresh()
        self.after(max(1000, int(self.cfg.auto_refresh_s) * 1000), self._auto_tick)

    # ------------------------------------------------------------ selection
    def _on_tree_click(self, event) -> None:
        if self.tree.identify_column(event.x) != "#1":
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.focus(row)
        if row in self.selected:
            self.selected.discard(row)
        else:
            self.selected.add(row)
        self._update_row_states()
        return "break"

    def _on_tree_right_click(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.tree.focus(row)
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def select_all(self) -> None:
        self.selected = set(self.devices)
        self._update_row_states()

    def select_none(self) -> None:
        self.selected.clear()
        self._update_row_states()

    def copy_path(self) -> None:
        row = self.tree.focus()
        if row:
            self.clipboard_clear()
            self.clipboard_append(row)
            self.log(f"已复制路径 {row}")

    def edit_alias(self) -> None:
        row = self.tree.focus()
        if not row:
            messagebox.showinfo("设置别名", "请先选中一台设备。", parent=self)
            return
        device = self.devices.get(row)
        current = device.alias if device else self.cfg.alias_for(row)
        value = simpledialog.askstring(
            "设置别名",
            f"给 {row} 设置一个工位名称（留空删除）：",
            initialvalue=current,
            parent=self,
        )
        if value is None:
            return
        self.cfg.set_alias(row, value)
        try:
            self.cfg.save()
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return
        if device:
            device.alias = value.strip()
        self.log(f"别名已更新: {row} -> {value.strip() or '（无）'}")
        self._apply_devices(list(self.devices.values()), None)

    # --------------------------------------------------------------- jobs
    def _require_devices(self) -> Optional[list[Device]]:
        devices = self.selected_devices()
        if not devices:
            messagebox.showwarning("未选择设备", "请先勾选至少一台设备。", parent=self)
            return None
        return devices

    def _confirm(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message, icon=messagebox.WARNING, parent=self)

    def _start_job(self, steps: list[Step], title: str, destructive: bool = False) -> None:
        if self.busy:
            messagebox.showinfo("请稍候", "已有任务在执行。", parent=self)
            return
        devices = self._require_devices()
        if not devices:
            return
        if destructive and self.cfg.confirm_destructive:
            lines = [f"计划: {title}", ""]
            for step in steps:
                lines.append(f"  • {step.describe()}")
            lines.append("")
            lines.append(f"目标 {len(devices)} 台设备：")
            for device in devices:
                lines.append(f"  • {device.label}  [{device.location}]")
            if not self._confirm("确认执行", "\n".join(lines)):
                return

        self.stop_event = threading.Event()
        self._set_busy(True)
        for device in devices:
            self._set_row(device.location, state="连接…", progress=0, message=title, tag="busy")
        self.log(f"开始: {title}（{len(devices)} 台）", "ok")
        threading.Thread(
            target=self._job_worker,
            args=(devices, steps, title),
            daemon=True,
        ).start()

    def _job_worker(self, devices: list[Device], steps: list[Step], title: str) -> None:
        try:
            results = run_on_devices(
                devices,
                steps,
                self.cfg,
                on_event=lambda event: self.queue.put(("event", event)),
                stop_event=self.stop_event,
            )
            self.queue.put(("finished", title, results))
        except Exception as exc:
            self.queue.put(("job_error", title, exc))

    def stop_job(self) -> None:
        if self.busy:
            self.stop_event.set()
            self.log("已请求停止：当前 USB 操作结束后停止。", "warn")
            self.status_var.set("正在停止…")

    def _set_row(self, location: str, *, state: Optional[str] = None,
                 progress: Optional[float] = None, message: Optional[str] = None,
                 tag: str = "") -> None:
        if not self.tree.exists(location):
            return
        values = list(self.tree.item(location, "values"))
        if state is not None:
            values[5] = state
        if progress is not None:
            values[6] = f"{int(progress * 100)}%" if progress >= 0 else "-"
        if message is not None:
            values[7] = message
        self.tree.item(location, values=values, tags=(tag,) if tag else ())
        self.row_state[location] = (values[5], values[6], values[7], tag)

    def _handle_event(self, event: Event) -> None:
        if event.kind == "start":
            self._set_row(event.location, state="连接…", progress=0,
                          message=event.message, tag="busy")
            self.log(f"[{event.label}] {event.message}")
        elif event.kind == "log":
            self._set_row(event.location, message=event.message,
                          tag="fail" if event.level == "error" else "busy")
            self.log(f"[{event.label}] {event.message}", event.level)
        elif event.kind == "progress":
            self._set_row(event.location, progress=event.fraction,
                          message=event.message, tag="busy")
        elif event.kind == "done":
            ok = event.level != "error"
            self._set_row(
                event.location,
                state="成功" if ok else "失败",
                progress=1.0 if ok else 0.0,
                message=event.message,
                tag="ok" if ok else "fail",
            )
            self.log(f"[{event.label}] {event.message}", "ok" if ok else "error")

    # ---------------------------------------------------------- flash actions
    def browse_image(self) -> None:
        path = filedialog.askopenfilename(
            title="选择镜像文件",
            filetypes=[("镜像文件", "*.img *.bin *.sparse"), ("所有文件", "*.*")],
            parent=self,
        )
        if path:
            self.image_var.set(path)

    def flash_selected(self) -> None:
        partition = self.partition_var.get().strip()
        image = self.image_var.get().strip()
        if not partition:
            messagebox.showwarning("缺少分区", "请输入分区名。", parent=self)
            return
        if not image or not Path(image).is_file():
            messagebox.showwarning("镜像无效", "请选择存在的镜像文件。", parent=self)
            return
        try:
            step = parse_flash_pair(partition, image)
        except FbhubError as exc:
            messagebox.showerror("参数错误", str(exc), parent=self)
            return
        self._start_job([step], f"刷写 {partition} ← {Path(image).name}", destructive=True)

    def run_plan(self) -> None:
        path = filedialog.askopenfilename(
            title="选择刷机计划",
            filetypes=[("JSON 计划", "*.json"), ("所有文件", "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            plan = load_plan(path)
        except FbhubError as exc:
            messagebox.showerror("计划错误", str(exc), parent=self)
            return
        destructive = any(
            step.action in {"flash", "erase"}
            or (step.action == "flashing" and (step.target or "").startswith("unlock"))
            for step in plan.steps
        )
        self._start_job(plan.steps, f"计划: {plan.name}", destructive=destructive)

    # --------------------------------------------------------- command actions
    def reboot_selected(self) -> None:
        target = REBOOT_TARGETS.get(self.reboot_var.get())
        self._start_job([Step("reboot", target=target)], f"重启到 {self.reboot_var.get()}")

    def flashing(self, action: str) -> None:
        if action.startswith("unlock"):
            destructive = True
        else:
            destructive = False
        self._start_job(
            [Step("flashing", target=action)],
            f"flashing {action}",
            destructive=destructive,
        )

    def erase_selected(self) -> None:
        partition = self.erase_var.get().strip()
        if not partition:
            messagebox.showwarning("缺少分区", "请输入分区名。", parent=self)
            return
        self._start_job(
            [Step("erase", partition=partition)],
            f"擦除 {partition}",
            destructive=True,
        )

    def getvar_selected(self) -> None:
        name = self.getvar_var.get().strip()
        if not name:
            messagebox.showwarning("缺少变量", "请输入变量名。", parent=self)
            return
        self._start_job([Step("getvar", name=name)], f"读取 {name}")

    def show_info(self) -> None:
        row = self.tree.focus()
        if not row:
            messagebox.showinfo("设备信息", "请先选中一台设备。", parent=self)
            return
        self._start_job([Step("getvar", name="all")], f"读取 {row} 设备信息")

    def raw_selected(self) -> None:
        text = self.raw_var.get().strip()
        if not text:
            return
        try:
            tokens = shlex.split(text)
            step = step_from_tokens(tokens)
        except (FbhubError, ValueError) as exc:
            messagebox.showerror("命令错误", str(exc), parent=self)
            return
        destructive = step.action in {"flash", "erase"} or (
            step.action == "flashing" and (step.target or "").startswith("unlock")
        )
        self._start_job([step], f"命令: {text}", destructive=destructive)

    # --------------------------------------------------------------- results
    def export_results(self) -> None:
        if not self.last_results:
            messagebox.showinfo("导出", "还没有可导出的执行结果。", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="保存结果 CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            parent=self,
        )
        if not path:
            return
        try:
            save_results_csv(self.last_results, path)
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)
            return
        self.log(f"结果已导出: {path}", "ok")

    # ---------------------------------------------------------------- queue
    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]
                if kind == "devices":
                    self._apply_devices(item[1], item[2])
                elif kind == "event":
                    self._handle_event(item[1])
                elif kind == "finished":
                    self._on_finished(item[1], item[2])
                elif kind == "job_error":
                    self._on_job_error(item[1], item[2])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _on_finished(self, title: str, results: list[DeviceResult]) -> None:
        self.last_results = results
        self._set_busy(False)
        ok = sum(1 for item in results if item.ok)
        failed = len(results) - ok
        self.log(f"结束: {title} — 成功 {ok}，失败 {failed}", "ok" if failed == 0 else "error")
        for item in results:
            if not item.ok:
                self.log(f"  {item.label}: {item.message}", "error")
        for item in results:
            for line in item.output:
                for part in str(line).splitlines():
                    self.log(f"  [{item.label}] {part}")
        if failed:
            messagebox.showwarning(
                "部分设备失败",
                f"成功 {ok} 台，失败 {failed} 台。\n详情见日志，可导出 CSV。",
                parent=self,
            )
        self.refresh()

    def _on_job_error(self, title: str, exc: Exception) -> None:
        self._set_busy(False)
        self.log(f"任务异常: {title}: {exc}", "error")
        messagebox.showerror("任务异常", str(exc), parent=self)
        self.refresh()


def run_gui(config: Config, auto_refresh: bool = True) -> int:
    try:
        app = App(config, auto_refresh=auto_refresh)
    except tk.TclError as exc:
        print(f"无法启动图形界面: {exc}")
        print("请确认当前环境有桌面（Windows 桌面会话）并安装了 Tk。")
        return 1
    app.mainloop()
    return 0
