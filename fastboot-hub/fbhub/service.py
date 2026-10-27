"""Multi-device orchestration and command execution."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence

from .config import Config
from .discovery import open_client
from .models import (
    Device,
    DeviceResult,
    FastbootError,
    Response,
)
from .plan import Step
from .topology import matches_selector


@dataclass
class Event:
    kind: str  # start | log | progress | done
    location: str
    label: str
    message: str = ""
    level: str = "info"  # info | ok | warn | error
    fraction: Optional[float] = None


EventCallback = Callable[[Event], None]


def select_devices(
    devices: Sequence[Device],
    *,
    select_all: bool = False,
    paths: Iterable[str] = (),
    serials: Iterable[str] = (),
    aliases: Iterable[str] = (),
    hub: Optional[int] = None,
    index: Optional[int] = None,
    exclude_paths: Iterable[str] = (),
) -> list[Device]:
    path_list = _split_values(paths)
    serial_list = _split_values(serials)
    alias_list = _split_values(aliases)
    exclude = _split_values(exclude_paths)
    has_positive = bool(path_list or serial_list or alias_list or hub is not None or index is not None)

    selected: list[Device] = []
    for device in devices:
        if not select_all and not has_positive:
            continue
        if path_list or serial_list or alias_list or hub is not None or index is not None:
            if not matches_selector(
                location=device.location,
                serial=device.serial,
                alias=device.alias,
                paths=path_list,
                serials=serial_list,
                aliases=alias_list,
                hub=hub,
                index=index,
            ):
                continue
        if exclude and any(
            matches_selector(
                location=device.location,
                serial=device.serial,
                alias=device.alias,
                paths=[item],
            )
            for item in exclude
        ):
            continue
        selected.append(device)
    return selected


def _split_values(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                result.append(item)
    return result


def run_on_devices(
    devices: Sequence[Device],
    steps: Sequence[Step],
    config: Config,
    *,
    jobs: int = 0,
    on_event: Optional[EventCallback] = None,
    stop_event: Optional[threading.Event] = None,
    dry_run: bool = False,
) -> list[DeviceResult]:
    if not devices:
        raise FastbootError("没有选中设备")
    if not steps:
        raise FastbootError("没有要执行的步骤")

    def emit(kind: str, device: Device, message: str = "", level: str = "info",
             fraction: Optional[float] = None) -> None:
        if on_event:
            on_event(
                Event(
                    kind=kind,
                    location=device.location,
                    label=device.label,
                    message=message,
                    level=level,
                    fraction=fraction,
                )
            )

    if dry_run:
        results: list[DeviceResult] = []
        for device in devices:
            output = [step.describe() for step in steps]
            emit("start", device, "dry-run")
            for line in output:
                emit("log", device, line)
            result = DeviceResult(
                location=device.location,
                label=device.label,
                ok=True,
                message="dry-run，未连接设备",
                output=output,
            )
            emit("done", device, result.message, "ok", 1.0)
            results.append(result)
        return results

    workers = jobs if jobs and jobs > 0 else len(devices)
    workers = max(1, min(workers, len(devices), 32))

    def worker(device: Device) -> DeviceResult:
        started = time.monotonic()
        output: list[str] = []
        emit("start", device, "连接设备…")
        client = None
        try:
            client = open_client(device, config)
            emit("log", device, "已连接 fastboot", "ok")
            for position, step in enumerate(steps, 1):
                if stop_event is not None and stop_event.is_set():
                    raise FastbootError("已被用户停止")
                emit("log", device, f"[{position}/{len(steps)}] {step.describe()}")
                response = _execute_step(client, step, device, emit, stop_event)
                if response is not None:
                    text = _response_text(response)
                    if text:
                        output.append(text)
                        emit("log", device, text)
                if step.action == "reboot":
                    emit("log", device, "设备正在重启，后续步骤已跳过", "warn")
                    break
            duration = time.monotonic() - started
            emit("done", device, f"完成（{duration:.1f}s）", "ok", 1.0)
            return DeviceResult(
                location=device.location,
                label=device.label,
                ok=True,
                message="完成",
                duration=duration,
                output=output,
            )
        except Exception as exc:  # keep other workers running
            duration = time.monotonic() - started
            message = str(exc) or exc.__class__.__name__
            emit("done", device, message, "error", None)
            return DeviceResult(
                location=device.location,
                label=device.label,
                ok=False,
                message=message,
                duration=duration,
                output=output,
            )
        finally:
            if client is not None:
                client.close()

    results: list[DeviceResult] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fbhub") as pool:
        futures = [pool.submit(worker, device) for device in devices]
        for future in as_completed(futures):
            results.append(future.result())

    order = {device.location: index for index, device in enumerate(devices)}
    results.sort(key=lambda item: order.get(item.location, 0))
    return results


def _execute_step(
    client,
    step: Step,
    device: Device,
    emit: Callable[..., None],
    stop_event: Optional[threading.Event],
) -> Optional[Response]:
    def progress(fraction: float, label: str) -> None:
        emit("progress", device, label, "info", max(0.0, min(1.0, fraction)))

    if step.action == "flash":
        client.flash_file(step.partition or "", step.image or "", progress=progress)
        return None
    if step.action == "erase":
        client.erase(step.partition or "")
        return None
    if step.action == "reboot":
        client.reboot(step.target)
        return None
    if step.action == "getvar":
        value = client.getvar(step.name or "", timeout=client.response_timeout)
        return Response("OKAY", f"{step.name}: {value}")
    if step.action == "oem":
        return client.oem(step.args)
    if step.action == "flashing":
        return client.flashing(step.target or "")
    if step.action == "set_active":
        return client.set_active(step.target or "")
    if step.action == "boot":
        client.boot_file(step.image or "", progress=progress)
        return None
    if step.action == "continue":
        return client.continue_boot()
    if step.action == "sleep":
        if stop_event is not None:
            if stop_event.wait(step.seconds):
                raise FastbootError("已被用户停止")
        else:
            time.sleep(step.seconds)
        return None
    if step.action == "raw":
        return client.raw_command(step.command or "")
    raise FastbootError(f"不支持的操作: {step.action}")


def _response_text(response: Response) -> str:
    parts = list(response.infos)
    if response.value:
        parts.append(response.value)
    return "\n".join(part for part in parts if part)


def summarize(results: Sequence[DeviceResult]) -> tuple[int, int]:
    ok = sum(1 for item in results if item.ok)
    return ok, len(results) - ok


def save_results_csv(results: Sequence[DeviceResult], path: str) -> None:
    import csv

    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["USB路径", "别名", "结果", "耗时(秒)", "信息", "输出"])
        for item in results:
            writer.writerow([
                item.location,
                item.label,
                "OK" if item.ok else "FAIL",
                f"{item.duration:.2f}",
                item.message,
                "\n".join(item.output),
            ])
