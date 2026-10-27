"""Flash plans: a list of fastboot operations executed on every device."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import PlanError

SUPPORTED_ACTIONS = {
    "flash",
    "erase",
    "reboot",
    "getvar",
    "oem",
    "flashing",
    "set_active",
    "boot",
    "continue",
    "sleep",
    "raw",
}

UNSUPPORTED_HINTS = {
    "format": "format 需要生成文件系统镜像，请使用 Android platform-tools 的 fastboot format，或先 flash 一个已格式化的镜像。",
    "flashall": "flashall 依赖 $ANDROID_PRODUCT_OUT，本工具请改用 flash 计划（plan.json）。",
    "update": "update ZIP 解析较复杂，请使用 fastboot update，或把 zip 内的镜像拆成 flash 计划。",
    "sideload": "sideload 使用 adb 协议，请使用 adb sideload。",
    "flash:raw": "flash:raw 需要 mkbootimg；请先制作 boot.img，再使用 flash。",
    "wipe-super": "wipe-super 需要解析 super 元数据，请使用 fastboot wipe-super。",
    "create-logical-partition": "动态分区管理命令未实现，请使用 fastboot。",
    "delete-logical-partition": "动态分区管理命令未实现，请使用 fastboot。",
    "resize-logical-partition": "动态分区管理命令未实现，请使用 fastboot。",
}


@dataclass
class Step:
    action: str
    partition: Optional[str] = None
    image: Optional[str] = None
    target: Optional[str] = None
    name: Optional[str] = None
    args: list[str] = field(default_factory=list)
    seconds: float = 0.0
    command: Optional[str] = None

    def describe(self) -> str:
        if self.action == "flash":
            return f"刷写 {self.partition} ← {Path(self.image or '').name}"
        if self.action == "erase":
            return f"擦除 {self.partition}"
        if self.action == "reboot":
            return f"重启到 {self.target or '系统'}"
        if self.action == "getvar":
            return f"读取变量 {self.name}"
        if self.action == "oem":
            return "OEM " + " ".join(self.args)
        if self.action == "flashing":
            return f"flashing {self.target}"
        if self.action == "set_active":
            return f"切换 slot {self.target}"
        if self.action == "boot":
            return f"临时启动 {Path(self.image or '').name}"
        if self.action == "continue":
            return "继续启动"
        if self.action == "sleep":
            return f"等待 {self.seconds:g} 秒"
        if self.action == "raw":
            return f"原始命令 {self.command}"
        return self.action

    def validate(self) -> None:
        action = self.action.lower()
        if action in UNSUPPORTED_HINTS:
            raise PlanError(UNSUPPORTED_HINTS[action])
        if action not in SUPPORTED_ACTIONS:
            raise PlanError(f"不支持的操作: {self.action}")
        if action == "flash":
            if not self.partition:
                raise PlanError("flash 步骤缺少 partition")
            if not self.image:
                raise PlanError(f"flash {self.partition} 缺少 image")
        elif action == "erase":
            if not self.partition:
                raise PlanError("erase 步骤缺少 partition")
        elif action == "getvar":
            if not self.name:
                raise PlanError("getvar 步骤缺少 name")
        elif action in {"flashing", "set_active"}:
            if not self.target:
                raise PlanError(f"{action} 步骤缺少 target")
        elif action == "boot":
            if not self.image:
                raise PlanError("boot 步骤缺少 image")
        elif action == "raw":
            if not self.command:
                raise PlanError("raw 步骤缺少 command")
        elif action == "sleep":
            if self.seconds <= 0:
                raise PlanError("sleep 的 seconds 必须大于 0")


@dataclass
class Plan:
    name: str
    steps: list[Step]
    source: Optional[Path] = None

    def validate(self) -> None:
        if not self.steps:
            raise PlanError("计划中没有步骤")
        for index, step in enumerate(self.steps, 1):
            try:
                step.validate()
            except PlanError as exc:
                raise PlanError(f"第 {index} 步（{step.describe()}）: {exc}") from exc


def _resolve_image(value: Any, base_dir: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError("image 必须是非空字符串")
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        raw = base_dir / raw
    return str(raw.resolve())


def _step_from_dict(item: dict[str, Any], base_dir: Path, index: int) -> Step:
    action = item.get("action", item.get("cmd", item.get("type", "")))
    if not isinstance(action, str) or not action:
        raise PlanError(f"第 {index} 步缺少 action")
    action = action.strip().lower()

    if action in UNSUPPORTED_HINTS:
        raise PlanError(f"第 {index} 步: {UNSUPPORTED_HINTS[action]}")

    partition = item.get("partition")
    target = item.get("target")
    name = item.get("name") or item.get("var") or item.get("variable")
    args = item.get("args", [])
    if isinstance(args, str):
        args = shlex.split(args)
    if args is None:
        args = []
    if not isinstance(args, list):
        raise PlanError(f"第 {index} 步的 args 必须是数组")

    image = item.get("image") or item.get("file")
    if image:
        image = _resolve_image(image, base_dir)

    seconds = item.get("seconds", item.get("sleep", 0))
    try:
        seconds = float(seconds)
    except (TypeError, ValueError) as exc:
        raise PlanError(f"第 {index} 步的 seconds 无效") from exc

    command = item.get("command") or item.get("raw")
    step = Step(
        action=action,
        partition=str(partition) if partition else None,
        image=image,
        target=str(target) if target else None,
        name=str(name) if name else None,
        args=[str(value) for value in args],
        seconds=seconds,
        command=str(command) if command else None,
    )
    if action == "oem" and not step.args and command:
        step.args = shlex.split(command)
    if action == "raw" and not step.command and step.args:
        step.command = " ".join(step.args)
    step.validate()
    return step


def _step_from_string(text: str, base_dir: Path, index: int) -> Step:
    tokens = shlex.split(text)
    if not tokens:
        raise PlanError(f"第 {index} 步为空")
    step = step_from_tokens(tokens, base_dir=base_dir)
    step.validate()
    return step


def load_plan(path: str | Path) -> Plan:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise PlanError(f"找不到计划文件: {source}")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanError(f"读取计划失败: {source}: {exc}") from exc

    base_dir = source.parent
    steps_raw: Iterable[Any]
    name = source.stem
    if isinstance(raw, list):
        steps_raw = raw
    elif isinstance(raw, dict):
        name = str(raw.get("name") or name)
        steps_raw = raw.get("steps")
        if steps_raw is None:
            raise PlanError("计划文件缺少 steps 数组")
    else:
        raise PlanError("计划文件格式错误：应为 JSON 对象或数组")

    if not isinstance(steps_raw, list):
        raise PlanError("steps 必须是数组")

    steps: list[Step] = []
    for index, item in enumerate(steps_raw, 1):
        if isinstance(item, str):
            steps.append(_step_from_string(item, base_dir, index))
        elif isinstance(item, dict):
            steps.append(_step_from_dict(item, base_dir, index))
        else:
            raise PlanError(f"第 {index} 步格式错误")

    plan = Plan(name=name, steps=steps, source=source)
    plan.validate()
    return plan


def step_from_tokens(tokens: list[str], base_dir: Optional[Path] = None) -> Step:
    """Build a step from a fastboot-like command line."""
    base = base_dir or Path.cwd()
    if not tokens:
        raise PlanError("命令为空")
    command = tokens[0].lower()
    rest = tokens[1:]

    aliases = {
        "reboot-bootloader": ("reboot", "bootloader"),
        "reboot-fastboot": ("reboot", "fastboot"),
        "reboot-recovery": ("reboot", "recovery"),
        "reboot-edl": ("reboot", "edl"),
        "reboot-bootloader-fastboot": ("reboot", "fastboot"),
    }
    if command in aliases:
        action, target = aliases[command]
        return Step(action=action, target=target)

    if command == "reboot":
        target = rest[0].lower() if rest else None
        if target in {"system", "normal"}:
            target = None
        if rest[1:]:
            raise PlanError("reboot 只接受一个目标")
        return Step("reboot", target=target)

    if command == "flash":
        if len(rest) < 2:
            raise PlanError("用法: flash <分区> <镜像文件>")
        if len(rest) > 2:
            raise PlanError("flash 参数过多")
        return Step(
            "flash",
            partition=rest[0],
            image=_resolve_image(rest[1], base),
        )

    if command == "erase":
        if len(rest) != 1:
            raise PlanError("用法: erase <分区>")
        return Step("erase", partition=rest[0])

    if command == "format":
        raise PlanError(UNSUPPORTED_HINTS["format"])

    if command == "getvar":
        if len(rest) != 1:
            raise PlanError("用法: getvar <变量名>")
        return Step("getvar", name=rest[0])

    if command == "oem":
        if not rest:
            raise PlanError("用法: oem <命令...>")
        return Step("oem", args=rest)

    if command == "flashing":
        if len(rest) != 1:
            raise PlanError("用法: flashing lock|unlock|...")
        return Step("flashing", target=rest[0])

    if command in {"set_active", "set-active"}:
        if len(rest) != 1:
            raise PlanError("用法: set_active <slot>")
        return Step("set_active", target=rest[0])

    if command == "boot":
        if len(rest) != 1:
            raise PlanError("用法: boot <镜像文件>")
        return Step("boot", image=_resolve_image(rest[0], base))

    if command == "continue":
        return Step("continue")

    if command in UNSUPPORTED_HINTS:
        raise PlanError(UNSUPPORTED_HINTS[command])

    if command == "raw":
        if not rest:
            raise PlanError("用法: raw <fastboot 命令>")
        return Step("raw", command=" ".join(rest))

    # Unknown command: pass through as a raw fastboot command.  This keeps OEM
    # extensions (``oem ...`` is covered above) usable without hiding mistakes:
    # the device will answer with FAIL if the command does not exist.
    return Step("raw", command=" ".join(tokens))


def parse_flash_pair(partition: str, image: str) -> Step:
    step = Step(
        "flash",
        partition=partition,
        image=_resolve_image(image, Path.cwd()),
    )
    step.validate()
    return step
