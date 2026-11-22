from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException

from agent_core.config import settings
from agent_core.storage import store

Recurrence = Literal["none", "daily", "weekly"]
PUSH_CHANNELS = {"telegram", "whatsapp", "slack", "discord"}


class ReminderStore:
    def __init__(self) -> None:
        self.root = settings.resolved_agent_data_dir / "reminders"

    def create(self, channel: str, chat_id: str, text: str, run_at: str, recurrence: str = "none") -> dict:
        if channel not in PUSH_CHANNELS:
            raise HTTPException(status_code=422, detail="Reminders require a Telegram, WhatsApp, Slack, or Discord chat")
        if not chat_id or len(chat_id) > 128:
            raise HTTPException(status_code=422, detail="A valid destination chat is required")
        if not text.strip() or len(text) > 2000:
            raise HTTPException(status_code=422, detail="Reminder text must be 1-2000 characters")
        if recurrence not in {"none", "daily", "weekly"}:
            raise HTTPException(status_code=422, detail="Recurrence must be none, daily, or weekly")
        try:
            scheduled = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="run_at must be an ISO timestamp with a timezone") from error
        if scheduled.tzinfo is None:
            raise HTTPException(status_code=422, detail="run_at must include a timezone, such as Z")
        scheduled = scheduled.astimezone(UTC)
        now = datetime.now(UTC)
        if scheduled <= now or scheduled > now + timedelta(days=365):
            raise HTTPException(status_code=422, detail="run_at must be in the next 365 days")
        active = [item for item in self.list(channel=channel, chat_id=chat_id) if item["status"] == "active"]
        if len(active) >= 500:
            raise HTTPException(status_code=409, detail="This chat already has 500 active reminders")

        reminder = {
            "id": str(uuid4()),
            "channel": channel,
            "chat_id": chat_id,
            "text": text.strip(),
            "recurrence": recurrence,
            "status": "active",
            "next_run_at": scheduled.isoformat(),
            "last_run_at": None,
            "created_at": now.isoformat(),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self._write(reminder)
        return reminder

    def list(self, channel: str | None = None, chat_id: str | None = None, active_only: bool = False) -> list[dict]:
        self.root.mkdir(parents=True, exist_ok=True)
        records = [self._read(path) for path in self.root.glob("*.json")]
        if channel is not None:
            records = [item for item in records if item.get("channel") == channel]
        if chat_id is not None:
            records = [item for item in records if item.get("chat_id") == chat_id]
        if active_only:
            records = [item for item in records if item.get("status") == "active"]
        return sorted(records, key=lambda item: item.get("next_run_at", ""))

    def cancel(self, reminder_id: str, channel: str | None = None, chat_id: str | None = None) -> dict:
        reminder = self.get(reminder_id)
        if channel is not None and (reminder["channel"] != channel or reminder["chat_id"] != chat_id):
            raise HTTPException(status_code=404, detail="Reminder not found")
        if reminder["status"] != "active":
            raise HTTPException(status_code=409, detail="Reminder is no longer active")
        reminder["status"] = "cancelled"
        reminder["cancelled_at"] = datetime.now(UTC).isoformat()
        self._write(reminder)
        return reminder

    def get(self, reminder_id: str) -> dict:
        try:
            UUID(reminder_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Reminder not found") from error
        path = self.root / f"{reminder_id}.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Reminder not found")
        return self._read(path)

    async def dispatch_due(
        self,
        send: Callable[[str, str, str], Awaitable[None]],
        now: datetime | None = None,
    ) -> int:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        sent = 0
        for reminder in self.list(active_only=True):
            scheduled = datetime.fromisoformat(reminder["next_run_at"])
            if scheduled > current:
                continue
            try:
                await send(reminder["channel"], reminder["chat_id"], f"⏰ Reminder: {reminder['text']}")
            except Exception as error:
                store.append_audit("reminder_delivery_failed", {
                    "reminder_id": reminder["id"], "channel": reminder["channel"],
                    "error": type(error).__name__,
                })
                continue

            reminder["last_run_at"] = current.isoformat()
            if reminder["recurrence"] == "none":
                reminder["status"] = "completed"
            else:
                step = timedelta(days=1 if reminder["recurrence"] == "daily" else 7)
                next_run = scheduled + step
                while next_run <= current:
                    next_run += step
                reminder["next_run_at"] = next_run.isoformat()
            self._write(reminder)
            store.append_audit("reminder_delivered", {
                "reminder_id": reminder["id"], "channel": reminder["channel"],
                "recurrence": reminder["recurrence"],
            })
            sent += 1
        return sent

    def _write(self, reminder: dict[str, Any]) -> None:
        path = self.root / f"{reminder['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(reminder, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))


reminder_store = ReminderStore()
