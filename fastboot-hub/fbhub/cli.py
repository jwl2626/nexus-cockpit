"""Command line interface for fbhub."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

from . import __version__
from .config import Config, config_path
from .discovery import diagnose, list_devices, list_fastboot_exe
from .models import Device, FbhubError
from .plan import Step, load_plan, parse_flash_pair, step_from_tokens
from .service import (
    Event,
    run_on_devices,
    save_results_csv,
    select_devices,
    summarize,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fbhub",
        description="多设备 Fastboot 工具：按 USB 物理路径批量刷写/发送命令",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  fbhub list\n"
            "  fbhub flash boot boot.img --all\n"
            "  fbhub plan factory.json --path 1D00:0-1.3 --path 1D00:0-1.4\n"
            "  fbhub run --all -- getvar current-slot\n"
            "  fbhub reboot bootloader --all\n"
            "  fbhub gui\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"fbhub {__version__}")
    parser.add_argument("--config", help="配置文件路径（默认 %%APPDATA%%\\fbhub\\config.json）")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list ---------------------------------------------------------------
    list_parser = subparsers.add_parser("list", aliases=["ls", "devices"],
                                        help="列出 fastboot 设备及其 USB 路径")
    list_parser.add_argument("--json", action="store_true", help="输出 JSON")
    list_parser.add_argument("--details", action="store_true", help="显示 Windows location path")
    _add_backend_note(list_parser)

    # doctor -------------------------------------------------------------
    doctor_parser = subparsers.add_parser("doctor", help="诊断为什么检测不到设备")
    doctor_parser.add_argument("--json", action="store_true")
    _add_backend_note(doctor_parser)

    # flash --------------------------------------------------------------
    flash_parser = subparsers.add_parser("flash", help="向多台设备刷写同一个分区镜像")
    flash_parser.add_argument("partition", help="分区名，例如 boot / vendor_boot / super")
    flash_parser.add_argument("image", help="镜像文件路径（raw 或 sparse 均可）")
    flash_parser.add_argument("--csv", help="把结果写入 CSV")
    _add_selection(flash_parser)
    _add_execution(flash_parser)

    # plan ---------------------------------------------------------------
    plan_parser = subparsers.add_parser("plan", help="执行 JSON 刷机计划")
    plan_parser.add_argument("plan", help="计划 JSON 文件")
    plan_parser.add_argument("--csv", help="把结果写入 CSV")
    _add_selection(plan_parser)
    _add_execution(plan_parser)

    # run ----------------------------------------------------------------
    run_parser = subparsers.add_parser("run", help="向多台设备发送一条 fastboot 命令")
    run_parser.add_argument("fastboot_args", nargs=argparse.REMAINDER,
                            help="命令，例如: reboot bootloader / getvar current-slot")
    _add_selection(run_parser)
    _add_execution(run_parser)

    # reboot -------------------------------------------------------------
    reboot_parser = subparsers.add_parser("reboot", help="批量重启")
    reboot_parser.add_argument("target", nargs="?", default=None,
                               help="system/bootloader/fastboot/recovery/edl")
    _add_selection(reboot_parser)
    _add_execution(reboot_parser)

    # getvar -------------------------------------------------------------
    getvar_parser = subparsers.add_parser("getvar", help="批量读取变量")
    getvar_parser.add_argument("name", help="变量名，例如 current-slot / max-download-size")
    _add_selection(getvar_parser)
    _add_execution(getvar_parser)

    # erase --------------------------------------------------------------
    erase_parser = subparsers.add_parser("erase", help="批量擦除分区（危险）")
    erase_parser.add_argument("partition")
    _add_selection(erase_parser)
    _add_execution(erase_parser)

    # oem ----------------------------------------------------------------
    oem_parser = subparsers.add_parser("oem", help="批量执行 OEM 命令")
    oem_parser.add_argument("oem_args", nargs=argparse.REMAINDER, help="OEM 参数，例如: edl")
    _add_selection(oem_parser)
    _add_execution(oem_parser)

    # alias --------------------------------------------------------------
    alias_parser = subparsers.add_parser("alias", help="给 USB 路径设置工位别名")
    alias_parser.add_argument("path", nargs="?", help="USB 路径，例如 1D00:0-1.3")
    alias_parser.add_argument("name", nargs="?", help="别名，例如 工位A")
    alias_parser.add_argument("--list", action="store_true", help="列出别名")
    alias_parser.add_argument("--remove", action="store_true", help="删除别名")

    # gui ----------------------------------------------------------------
    gui_parser = subparsers.add_parser("gui", help="打开图形界面")
    gui_parser.add_argument("--no-auto-refresh", action="store_true")

    return parser


def _add_selection(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("设备选择")
    group.add_argument("--all", action="store_true", help="选中全部设备")
    group.add_argument("--path", "--port", dest="paths", action="append", default=[],
                       metavar="USB路径", help="按 USB 路径选择，可重复/逗号分隔")
    group.add_argument("--serial", action="append", default=[], metavar="SN",
                       help="按序列号选择（设备有 SN 时）")
    group.add_argument("--alias", action="append", default=[], metavar="别名",
                       help="按工位别名选择")
    group.add_argument("--hub", type=int, help="按上一级 HUB 端口号过滤")
    group.add_argument("--index", type=int, help="按最后一级端口号过滤")
    group.add_argument("--exclude", action="append", default=[], metavar="USB路径",
                       help="排除指定路径")
    group.add_argument("--wait", type=float, default=0.0, metavar="秒",
                       help="等待设备出现的最长时间")


def _add_execution(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("执行")
    group.add_argument("--jobs", type=int, default=0, help="并发数（默认每台设备一个线程）")
    group.add_argument("--dry-run", action="store_true", help="只打印计划，不连接设备")
    group.add_argument("--yes", "-y", action="store_true", help="跳过危险操作确认")
    group.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    group.add_argument("--raw-progress", action="store_true", help="显示细粒度进度")


def _add_backend_note(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fastboot-exe", default=None,
                        help="仅用于 doctor 诊断的 fastboot.exe 路径")


def main(argv: Optional[list[str]] = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cfg = Config.load(Path(args.config) if args.config else None)
    except FbhubError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2

    try:
        if args.command == "gui":
            from .gui import run_gui
            return run_gui(cfg, auto_refresh=not args.no_auto_refresh)
        if args.command == "alias":
            return _cmd_alias(args, cfg)
        if args.command == "doctor":
            return _cmd_doctor(args, cfg)
        if args.command in {"list", "ls", "devices"}:
            return _cmd_list(args, cfg)
        if args.command == "plan":
            plan = load_plan(args.plan)
            return _run_steps(args, cfg, plan.steps, plan_name=plan.name)
        if args.command == "flash":
            step = parse_flash_pair(args.partition, args.image)
            return _run_steps(args, cfg, [step], plan_name=f"flash {args.partition}")
        if args.command == "reboot":
            return _run_steps(
                args, cfg, [Step("reboot", target=args.target)], plan_name="reboot"
            )
        if args.command == "getvar":
            return _run_steps(
                args, cfg, [Step("getvar", name=args.name)], plan_name=f"getvar {args.name}"
            )
        if args.command == "erase":
            return _run_steps(
                args, cfg, [Step("erase", partition=args.partition)],
                plan_name=f"erase {args.partition}",
            )
        if args.command == "oem":
            return _run_steps(
                args, cfg, [Step("oem", args=_clean_remainder(args.oem_args))],
                plan_name="oem",
            )
        if args.command == "run":
            tokens = _clean_remainder(args.fastboot_args)
            if not tokens:
                parser.error("run 需要一条 fastboot 命令，例如: fbhub run --all -- reboot bootloader")
            step = step_from_tokens(tokens)
            return _run_steps(args, cfg, [step], plan_name=" ".join(tokens))
    except FbhubError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130

    parser.print_help()
    return 2


def _run_steps(args, cfg: Config, steps: list[Step], *, plan_name: str) -> int:
    for step in steps:
        if step.action in {"flash", "boot"} and step.image:
            if not Path(step.image).is_file():
                raise FbhubError(f"找不到镜像文件: {step.image}")
    actions = {step.action for step in steps}
    destructive = bool(actions & {"flash", "erase"}) or any(
        step.action == "flashing" and (step.target or "").startswith("unlock")
        for step in steps
    )

    devices = _wait_for_selection(args, cfg)
    if not devices and args.dry_run:
        print(f"计划: {plan_name}")
        for step in steps:
            print(f"  - {step.describe()}")
        print("未发现设备；dry-run 不连接 USB。")
        return 0
    if not devices:
        _print_no_devices(args, cfg)
        return 1

    if destructive and not args.dry_run and cfg.confirm_destructive and not args.yes:
        print(f"计划: {plan_name}")
        for step in steps:
            print(f"  - {step.describe()}")
        print(f"目标: {len(devices)} 台设备")
        for device in devices:
            print(f"  * {device.label}  [{device.location}]  SN={device.serial_display}")
        if not _confirm("确认执行？"):
            print("已取消")
            return 130

    _print_selection(devices, args)
    stop_event = None
    results = run_on_devices(
        devices,
        steps,
        cfg,
        jobs=args.jobs,
        on_event=_make_cli_event_printer(args),
        stop_event=stop_event,
        dry_run=args.dry_run,
    )

    ok, failed = summarize(results)
    if args.json:
        payload = {
            "ok": failed == 0,
            "plan": plan_name,
            "devices": [device.as_dict() for device in devices],
            "results": [item.as_dict() for item in results],
            "summary": {"ok": ok, "failed": failed, "total": len(results)},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("\n结果:")
        for item in results:
            mark = "OK  " if item.ok else "FAIL"
            print(f"  [{mark}] {item.label} [{item.location}]  {item.message}")
            for line in item.output:
                for part in str(line).splitlines():
                    print(f"          {part}")
        print(f"\n完成: 成功 {ok} 台，失败 {failed} 台")

    csv_path = getattr(args, "csv", None)
    if csv_path:
        save_results_csv(results, csv_path)
        if not args.json:
            print(f"结果已写入 {csv_path}")

    return 0 if failed == 0 else 1


def _wait_for_selection(args, cfg: Config) -> list[Device]:
    deadline = time.monotonic() + max(0.0, float(args.wait or 0.0))
    first = True
    while True:
        devices = list_devices(cfg)
        selected = select_devices(
            devices,
            select_all=args.all,
            paths=args.paths,
            serials=args.serial,
            aliases=args.alias,
            hub=args.hub,
            index=args.index,
            exclude_paths=args.exclude,
        )
        if selected:
            return selected
        if first and not devices and not args.wait:
            return []
        first = False
        if time.monotonic() >= deadline:
            return []
        time.sleep(1.0)


def _print_no_devices(args, cfg: Config) -> None:
    print("未找到/未选中任何 fastboot 设备。", file=sys.stderr)
    print("请确认: 设备处于 fastboot/bootloader 模式，USB 线连接正常，", file=sys.stderr)
    print("并且设备使用 WinUSB 驱动（安装 Google USB Driver 或厂商驱动）。", file=sys.stderr)
    print("可运行 `fbhub list` 或 `fbhub doctor` 查看详情。", file=sys.stderr)


def _print_selection(devices: list[Device], args) -> None:
    if args.json:
        return
    print(f"目标设备 {len(devices)} 台:")
    for device in devices:
        print(f"  * {device.label:<18} [{device.location}]  SN={device.serial_display}")
    print()


def _make_cli_event_printer(args):
    last_progress: dict[str, float] = {}

    def printer(event: Event) -> None:
        if args.json:
            if event.kind == "done" and event.level == "error":
                print(f"[{event.label}] {event.message}", file=sys.stderr)
            return
        prefix = f"[{event.label}]"
        if event.kind == "log":
            print(f"{prefix} {event.message}")
        elif event.kind == "done":
            if event.level == "error":
                print(f"{prefix} 失败: {event.message}")
            elif args.raw_progress:
                print(f"{prefix} {event.message}")
        elif event.kind == "progress":
            if not args.raw_progress:
                return
            fraction = event.fraction or 0.0
            previous = last_progress.get(event.location, -1.0)
            if fraction >= previous + 0.05 or fraction >= 1.0:
                last_progress[event.location] = fraction
                print(f"{prefix} {fraction * 100:5.1f}%  {event.message}")

    return printer


def _cmd_list(args, cfg: Config) -> int:
    devices = list_devices(cfg)
    if args.json:
        print(json.dumps([device.as_dict() for device in devices], ensure_ascii=False, indent=2))
        return 0
    if not devices:
        print("未发现 fastboot 设备。")
        print("提示: 运行 `fbhub doctor` 查看 USB 接口与驱动状态。")
        return 1
    print(f"发现 {len(devices)} 台 fastboot 设备:\n")
    header = f"{'USB路径':<22} {'别名':<14} {'SN':<18} {'产品':<28} {'VID:PID':<10}"
    print(header)
    print("-" * len(header))
    for device in devices:
        print(
            f"{device.location:<22} {device.label if device.alias else '-':<14} "
            f"{device.serial_display:<18} {(device.product or '-'):<28} "
            f"{device.vendor_id:04x}:{device.product_id:04x}"
        )
        if args.details:
            print(f"    instance: {device.instance_id}")
            for path in device.location_paths:
                print(f"    location: {path}")
    return 0


def _cmd_doctor(args, cfg: Config) -> int:
    info = diagnose()
    fastboot_exe = args.fastboot_exe or cfg.fastboot_exe
    exe_ok, exe_output = list_fastboot_exe(fastboot_exe)
    payload = {
        "version": __version__,
        "platform": platform.platform(),
        "python": sys.version,
        "config": str(config_path()),
        "usb_interfaces": info["interfaces"],
        "errors": info["errors"],
        "fastboot_exe": fastboot_exe,
        "fastboot_exe_ok": exe_ok,
        "fastboot_exe_output": exe_output,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"fbhub {__version__}")
    print(f"Python : {sys.version.split()[0]}  ({platform.platform()})")
    print(f"配置   : {config_path()}")
    print()
    print("WinUSB 接口:")
    if not info["interfaces"]:
        print("  （没有枚举到任何 USB 设备接口）")
    for item in info["interfaces"]:
        state = "FASTBOOT" if item.get("fastboot") else ("可打开" if item.get("opened") else "跳过")
        print(f"  {item['location']:<22} {state:<9} {item.get('product') or item.get('instance_id')}")
        if item.get("error"):
            print(f"      {item['error']}")
    print()
    print(f"fastboot.exe ({fastboot_exe}):")
    if exe_ok:
        print("  " + (exe_output.replace("\n", "\n  ") if exe_output else "（没有设备）"))
    else:
        print(f"  调用失败: {exe_output}")
    print()
    fastboot_count = sum(1 for item in info["interfaces"] if item.get("fastboot"))
    if fastboot_count:
        print(f"结论: 发现 {fastboot_count} 个 fastboot 接口，可以运行 `fbhub list`。")
    elif exe_ok and exe_output.strip():
        print("结论: fastboot.exe 能看到设备，但本工具无法打开其 WinUSB 接口。")
        print("      通常是驱动不是 WinUSB，或设备被其他程序占用。")
    else:
        print("结论: 没有检测到 fastboot 设备。请检查设备模式、USB 线和驱动。")
    return 0


def _cmd_alias(args, cfg: Config) -> int:
    if args.list or not args.path:
        if not cfg.aliases:
            print("尚未设置别名。")
        else:
            for key, value in sorted(cfg.aliases.items()):
                print(f"{key:<24} {value}")
        return 0
    save_path = Path(args.config) if getattr(args, "config", None) else None
    if args.remove:
        cfg.set_alias(args.path, "")
        path = cfg.save(save_path)
        print(f"已删除 {args.path} 的别名（{path}）")
        return 0
    if not args.name:
        print(cfg.alias_for(args.path) or f"{args.path} 没有别名")
        return 0
    cfg.set_alias(args.path, args.name)
    path = cfg.save(save_path)
    print(f"已设置 {args.path} -> {args.name}（{path}）")
    return 0


def _confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        raise FbhubError("非交互环境执行危险操作，请加 --yes 明确确认")
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _clean_remainder(values: Iterable[str]) -> list[str]:
    result = list(values)
    if result and result[0] == "--":
        result = result[1:]
    return result


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
