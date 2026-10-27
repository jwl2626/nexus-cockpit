"""Configuration and physical-port aliases."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional

from .models import ConfigError


def config_directory() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "fbhub"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "fbhub"


def config_path() -> Path:
    override = os.environ.get("FBHUB_CONFIG")
    return Path(override) if override else config_directory() / "config.json"


@dataclass
class Config:
    # Split large sparse images into pieces of at most this size.  The
    # device's max-download-size always wins when it is smaller.
    max_part_size_mb: int = 32
    # How long to wait for the final OKAY/FAIL after a flash/download.
    response_timeout_s: int = 180
    # How long to wait for the answer to a short command.
    command_timeout_s: int = 20
    # 0 means "one worker per selected device".
    jobs: int = 0
    auto_refresh_s: int = 3
    aliases: dict[str, str] = field(default_factory=dict)
    fastboot_exe: str = "fastboot"
    confirm_destructive: bool = True
    log_dir: str = ""

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        target = path or config_path()
        if not target.exists():
            config = cls()
            config._source_path = target  # type: ignore[attr-defined]
            return config
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigError(f"读取配置文件失败: {target}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"配置文件格式错误（应为 JSON 对象）: {target}")

        known = {item.name for item in fields(cls)}
        values = {key: value for key, value in raw.items() if key in known}
        aliases = values.get("aliases")
        if aliases is not None and not isinstance(aliases, dict):
            raise ConfigError("配置项 aliases 必须是对象，例如 {\"1D00:0-1.3\": \"工位1\"}")
        try:
            config = cls(**values)
        except TypeError as exc:
            raise ConfigError(f"配置文件内容无效: {exc}") from exc
        config._source_path = target  # type: ignore[attr-defined]
        return config

    def save(self, path: Optional[Path] = None) -> Path:
        target = path or getattr(self, "_source_path", None) or config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(asdict(self), ensure_ascii=False, indent=2)
        temp = target.with_suffix(".tmp")
        temp.write_text(data + "\n", encoding="utf-8")
        os.replace(temp, target)
        return target

    def alias_for(self, location: str) -> str:
        if location in self.aliases:
            return self.aliases[location]
        upper = location.upper()
        for key, value in self.aliases.items():
            if key.upper() == upper:
                return value
        return ""

    def set_alias(self, location: str, alias: str) -> None:
        cleaned = alias.strip()
        if cleaned:
            self.aliases[location] = cleaned
        else:
            self.aliases.pop(location, None)
