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

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return DEFAULT_POLICY

        try:
            with self._path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return DEFAULT_POLICY

        return {
            "metadata": data.get("metadata", DEFAULT_POLICY["metadata"]),
            "whatsapp": {**DEFAULT_POLICY["whatsapp"], **data.get("whatsapp", {})},
            "telegram": {**DEFAULT_POLICY["telegram"], **data.get("telegram", {})},
            "behavior": {**DEFAULT_POLICY["behavior"], **data.get("behavior", {})},
        }


policy = AccessPolicy(settings.access_policy_file)
