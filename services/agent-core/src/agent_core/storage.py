from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_core.config import settings


class FileStore:
    def __init__(self, base_dir: str) -> None:
        configured_path = Path(base_dir)
        self.base_dir = configured_path if configured_path.is_absolute() else settings.resolved_agent_data_dir
        self.history_dir = self.base_dir / "history"
        self.audit_dir = self.base_dir / "audit"
        self.notes_dir = self.base_dir / "notes"
        self.todos_dir = self.base_dir / "todos"
        self.state_dir = self.base_dir / "state"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.todos_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def append_history(self, channel: str, chat_id: str, payload: dict[str, Any]) -> None:
        path = self.history_dir / f"{channel}-{self._safe_name(chat_id)}.jsonl"
        self._append_jsonl(path, payload)

    def read_history(self, channel: str, chat_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        path = self.history_dir / f"{channel}-{self._safe_name(chat_id)}.jsonl"
        if not path.exists():
            return []

        lines: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(parsed, dict):
                        lines.append(parsed)
        except OSError:
            return []

        size = limit or settings.max_history_messages
        return lines[-size:]

    def append_audit(self, event_type: str, payload: dict[str, Any]) -> None:
        if not settings.enable_audit_logging:
            return

        timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
        path = self.audit_dir / f"{timestamp}.jsonl"
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        self._append_jsonl(path, record)

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True, default=self._json_default) + "\n")
        except OSError:
            return

    def is_duplicate_message(self, channel: str, chat_id: str, message_id: str) -> bool:
        path = self.state_dir / f"processed-{channel}-{self._safe_name(chat_id)}.json"
        data = self._read_json_file(path, default={"message_ids": []})
        return message_id in data.get("message_ids", [])

    def mark_message_processed(self, channel: str, chat_id: str, message_id: str) -> None:
        path = self.state_dir / f"processed-{channel}-{self._safe_name(chat_id)}.json"
        data = self._read_json_file(path, default={"message_ids": []})
        message_ids = data.get("message_ids", [])
        if message_id in message_ids:
            return
        message_ids.append(message_id)
        data["message_ids"] = message_ids[-500:]
        self._write_json_file(path, data)

    def list_notes(self, channel: str, chat_id: str) -> list[dict[str, Any]]:
        path = self.notes_dir / f"{channel}-{self._safe_name(chat_id)}.json"
        data = self._read_json_file(path, default={"notes": []})
        return data.get("notes", [])

    def add_note(self, channel: str, chat_id: str, text: str, created_by: str) -> dict[str, Any]:
        path = self.notes_dir / f"{channel}-{self._safe_name(chat_id)}.json"
        data = self._read_json_file(path, default={"notes": []})
        notes = data.get("notes", [])
        record = {
            "id": len(notes) + 1,
            "text": text,
            "created_by": created_by,
            "ts": datetime.now(UTC).isoformat(),
        }
        notes.append(record)
        data["notes"] = notes
        self._write_json_file(path, data)
        return record

    def clear_notes(self, channel: str, chat_id: str) -> None:
        path = self.notes_dir / f"{channel}-{self._safe_name(chat_id)}.json"
        self._write_json_file(path, {"notes": []})

    def list_todos(self, channel: str, chat_id: str) -> list[dict[str, Any]]:
        path = self.todos_dir / f"{channel}-{self._safe_name(chat_id)}.json"
        data = self._read_json_file(path, default={"todos": []})
        return data.get("todos", [])

    def add_todo(self, channel: str, chat_id: str, text: str, created_by: str) -> dict[str, Any]:
        path = self.todos_dir / f"{channel}-{self._safe_name(chat_id)}.json"
        data = self._read_json_file(path, default={"todos": []})
        todos = data.get("todos", [])
        record = {
            "id": len(todos) + 1,
            "text": text,
            "created_by": created_by,
            "done": False,
            "ts": datetime.now(UTC).isoformat(),
        }
        todos.append(record)
        data["todos"] = todos
        self._write_json_file(path, data)
        return record

    def complete_todo(self, channel: str, chat_id: str, todo_id: int) -> dict[str, Any] | None:
        path = self.todos_dir / f"{channel}-{self._safe_name(chat_id)}.json"
        data = self._read_json_file(path, default={"todos": []})
        todos = data.get("todos", [])
        for todo in todos:
            if todo.get("id") == todo_id:
                todo["done"] = True
                todo["completed_ts"] = datetime.now(UTC).isoformat()
                self._write_json_file(path, data)
                return todo
        return None

    def clear_todos(self, channel: str, chat_id: str) -> None:
        path = self.todos_dir / f"{channel}-{self._safe_name(chat_id)}.json"
        self._write_json_file(path, {"todos": []})

    def _read_json_file(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else default
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return default

    def _write_json_file(self, path: Path, payload: dict[str, Any]) -> None:
        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=True, indent=2, default=self._json_default)
        except OSError:
            return

    @staticmethod
    def _json_default(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _safe_name(value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)


store = FileStore(settings.agent_data_dir)
