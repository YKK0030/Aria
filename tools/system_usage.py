"""Read-only snapshot of system resources visible to the Aria runtime."""

import json
import os
from pathlib import Path
import shutil
import time

TOOL_NAME = "system_usage"
TOOL_DESCRIPTION = (
    "Report current CPU, memory, battery, and disk usage visible to Aria. "
    "Read-only; disk usage refers to the runtime root filesystem."
)
TOOL_ENABLED = True
TOOL_APPROVAL_REQUIRED = False
TOOL_TIMEOUT_SECONDS = 3

_POWER_SUPPLY = Path("/sys/class/power_supply")


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def _cpu_counters() -> tuple[int, int] | None:
    line = _read_text(Path("/proc/stat"))
    if not line:
        return None
    fields = line.splitlines()[0].split()
    if len(fields) < 5 or fields[0] != "cpu":
        return None
    counters = [int(value) for value in fields[1:]]
    return sum(counters), counters[3] + (counters[4] if len(counters) > 4 else 0)


def _cpu_usage() -> dict:
    before = _cpu_counters()
    if before is None:
        return {"percent": None, "logical_cores": os.cpu_count()}
    time.sleep(0.12)
    after = _cpu_counters()
    if after is None:
        return {"percent": None, "logical_cores": os.cpu_count()}
    total_delta, idle_delta = after[0] - before[0], after[1] - before[1]
    percent = None if total_delta <= 0 else round(100 * (total_delta - idle_delta) / total_delta, 1)
    return {"percent": percent, "logical_cores": os.cpu_count()}


def _memory_usage() -> dict:
    values = {}
    contents = _read_text(Path("/proc/meminfo")) or ""
    for line in contents.splitlines():
        key, _, value = line.partition(":")
        if key in {"MemTotal", "MemAvailable"}:
            try:
                values[key] = int(value.strip().split()[0]) * 1024
            except (IndexError, ValueError):
                pass
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if total is None or available is None:
        return {"total_bytes": total, "used_bytes": None, "available_bytes": available, "percent": None}
    used = max(0, total - available)
    return {
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "percent": round(100 * used / total, 1) if total else None,
    }


def _battery_usage() -> dict:
    try:
        supplies = list(_POWER_SUPPLY.iterdir())
    except OSError:
        return {"available": False, "percent": None, "status": None, "plugged": None}

    battery = None
    plugged = None
    for supply in supplies:
        supply_type = (_read_text(supply / "type") or "").lower()
        if supply_type == "battery" or supply.name.lower().startswith("bat"):
            battery = supply
        elif supply_type in {"mains", "usb", "usb_c", "wireless"}:
            online = _read_text(supply / "online")
            if online in {"0", "1"}:
                plugged = online == "1" or plugged is True

    if battery is None:
        return {"available": False, "percent": None, "status": None, "plugged": plugged}
    try:
        percent = int(_read_text(battery / "capacity"))
    except (TypeError, ValueError):
        percent = None
    return {
        "available": True,
        "percent": percent,
        "status": _read_text(battery / "status"),
        "plugged": plugged,
    }


def run() -> str:
    """Return a JSON snapshot of resource usage; disk describes the container root."""
    disk = shutil.disk_usage("/")
    return json.dumps({
        "cpu": _cpu_usage(),
        "memory": _memory_usage(),
        "battery": _battery_usage(),
        "disk": {
            "scope": "runtime root filesystem",
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": round(100 * disk.used / disk.total, 1) if disk.total else None,
        },
    })
