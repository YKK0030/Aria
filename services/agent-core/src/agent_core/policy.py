from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_core.config import settings


DEFAULT_POLICY: dict[str, Any] = {
    "metadata": {
        "version": 1,
    },
    "whatsapp": {
        "enabled": True,
        "allowed_chat_ids": [],
        "blocked_chat_ids": [],
    },
    "telegram": {
        "enabled": True,
        "allowed_chat_ids": [],
        "blocked_chat_ids": [],
    },
    "behavior": {
        "allow_auto_reply": True,
        "allowed_commands": [
            "/help",
            "/status",
            "/channels",
            "/memory",
            "/echo",
            "/capabilities",
            "/note",
            "/todo",
            "/summary",
        ],
    },
}


class AccessPolicy:
    def __init__(self, path: str) -> None:
        configured_path = Path(path)
        self._path = configured_path if configured_path.is_absolute() else settings.resolved_access_policy_file
        self._override_path = settings.resolved_access_policy_overrides_file

    def load(self) -> dict[str, Any]:
        data: dict[str, Any] = DEFAULT_POLICY
        if not self._path.exists():
            data = DEFAULT_POLICY
        else:
            try:
                with self._path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                data = DEFAULT_POLICY
        if not isinstance(data, dict):
            data = DEFAULT_POLICY

        def section(name: str) -> dict[str, Any]:
            value = data.get(name, {})
            return value if isinstance(value, dict) else {}

        merged = {
            "metadata": data.get("metadata", DEFAULT_POLICY["metadata"]),
            "whatsapp": {**DEFAULT_POLICY["whatsapp"], **section("whatsapp")},
            "telegram": {**DEFAULT_POLICY["telegram"], **section("telegram")},
            "behavior": {**DEFAULT_POLICY["behavior"], **section("behavior")},
        }
        try:
            with self._override_path.open("r", encoding="utf-8") as handle:
                overrides = json.load(handle)
            if not isinstance(overrides, dict):
                overrides = {}
            for channel in ("whatsapp", "telegram"):
                if isinstance(overrides.get(channel), dict):
                    merged[channel].update(overrides[channel])
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
        return merged

    def update_allowlist(self, channel: str, allowed: list[str], blocked: list[str]) -> dict[str, Any]:
        if channel not in {"whatsapp", "telegram"}:
            raise ValueError("Allowlist channel must be telegram or whatsapp")
        if not all(isinstance(item, str) for item in allowed + blocked):
            raise ValueError("Allowlist IDs must be strings")
        allowed = [item.strip() for item in allowed]
        blocked = [item.strip() for item in blocked]
        normalized = allowed + blocked
        if (
            len(allowed) > 1000 or len(blocked) > 1000
            or any(not item or len(item) > 128 for item in normalized)
            or len(set(allowed)) != len(allowed)
            or len(set(blocked)) != len(blocked)
            or set(allowed) & set(blocked)
        ):
            raise ValueError("Allowlist IDs must be unique, non-empty, at most 128 characters, and not overlap")

        self._override_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            overrides = json.loads(self._override_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            overrides = {"metadata": {"version": 1}}
        if not isinstance(overrides, dict):
            overrides = {"metadata": {"version": 1}}
        overrides[channel] = {
            "allowlist_managed": True,
            "allowed_chat_ids": allowed,
            "blocked_chat_ids": blocked,
        }
        temporary = self._override_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
        temporary.replace(self._override_path)
        return self.load()[channel]

    def reset_allowlist(self, channel: str) -> dict[str, Any]:
        if channel not in {"whatsapp", "telegram"}:
            raise ValueError("Allowlist channel must be telegram or whatsapp")
        try:
            overrides = json.loads(self._override_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            overrides = {}
        if not isinstance(overrides, dict):
            overrides = {}
        overrides.pop(channel, None)
        if overrides:
            temporary = self._override_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
            temporary.replace(self._override_path)
        else:
            self._override_path.unlink(missing_ok=True)
        return self.load()[channel]


policy = AccessPolicy(settings.access_policy_file)
