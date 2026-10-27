"""USB topology helpers: parsing, formatting and matching port addresses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class Location:
    """A physical USB port address.

    ``prefix`` identifies the host controller (usually a PCI slot, but can be
    ``USB`` on machines without location paths), ``root_hub`` is Windows'
    root-hub index and ``ports`` is the chain of hub ports from the root hub to
    the device.
    """

    prefix: str
    root_hub: int
    ports: tuple[int, ...]

    @property
    def hub_port(self) -> Optional[int]:
        """Port on the immediate parent hub (the second-to-last hop)."""
        return self.ports[-2] if len(self.ports) >= 2 else None

    @property
    def index(self) -> Optional[int]:
        """Port on the immediate hub / the last hop."""
        return self.ports[-1] if self.ports else None

    def __str__(self) -> str:
        suffix = ".".join(str(port) for port in self.ports)
        return f"{self.prefix}:{self.root_hub}-{suffix}" if suffix else f"{self.prefix}:{self.root_hub}"

    @property
    def short(self) -> str:
        return ".".join(str(port) for port in self.ports) or "-"


_LOCATION_RE = re.compile(
    r"^(?:(?P<prefix>[A-Za-z0-9]+)[:/])?(?P<root>\d+)-(?P<ports>\d+(?:\.\d+)*)$"
)


def parse_location(value: str) -> Location:
    text = value.strip()
    if text.lower().startswith("usb:"):
        text = text[4:]
    match = _LOCATION_RE.match(text)
    if not match:
        # Allow a bare port chain such as "1.3" for convenience.
        if re.fullmatch(r"\d+(?:\.\d+)*", text):
            return Location("USB", 0, tuple(int(part) for part in text.split(".")))
        raise ValueError(f"无法识别的 USB 路径: {value!r}（示例: 1D00:0-1.3）")
    ports = tuple(int(part) for part in match.group("ports").split("."))
    return Location(
        prefix=(match.group("prefix") or "USB").upper(),
        root_hub=int(match.group("root")),
        ports=ports,
    )


def try_parse_location(value: str) -> Optional[Location]:
    try:
        return parse_location(value)
    except ValueError:
        return None


def natural_location_key(value: str) -> tuple:
    """Sort addresses in human order (2 before 10)."""
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"([0-9]+)", value)
    )


def location_matches(device_location: str, wanted: str) -> bool:
    """Match a full or shortened address (``1D00:0-1.3`` / ``0-1.3`` / ``1.3``)."""
    try:
        left = parse_location(device_location)
        right = parse_location(wanted)
    except ValueError:
        return device_location.lower() == wanted.lower()

    if right.prefix != "USB" and left.prefix != right.prefix:
        return False
    if right.prefix == "USB" and right.root_hub != 0 and left.root_hub != right.root_hub:
        return False
    if right.root_hub and left.root_hub != right.root_hub:
        return False
    if right.ports and left.ports != right.ports:
        return False
    return True


def matches_selector(
    *,
    location: str,
    serial: Optional[str],
    alias: str = "",
    paths: Iterable[str] = (),
    serials: Iterable[str] = (),
    aliases: Iterable[str] = (),
    hub: Optional[int] = None,
    index: Optional[int] = None,
) -> bool:
    wanted_paths = list(paths)
    wanted_serials = list(serials)
    wanted_aliases = list(aliases)

    if wanted_paths and not any(location_matches(location, item) for item in wanted_paths):
        return False
    if wanted_serials:
        wanted = {item.casefold() for item in wanted_serials}
        if not serial or serial.casefold() not in wanted:
            return False
    if wanted_aliases:
        wanted = {item.casefold() for item in wanted_aliases}
        if not alias or alias.casefold() not in wanted:
            return False

    try:
        parsed = parse_location(location)
    except ValueError:
        return not (hub is not None or index is not None)

    if hub is not None and parsed.hub_port != hub:
        return False
    if index is not None and parsed.index != index:
        return False
    return True
