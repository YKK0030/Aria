from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from agent_core.config import settings
from agent_core.models import InboundEvent
from agent_core.reminders import ReminderStore
from agent_core.runtime import AgentRuntime


class ReminderStoreTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root_patch = patch.object(settings, "agent_data_dir", self.temp.name)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.reminders = ReminderStore()

    @staticmethod
    def future(hours: int = 1) -> str:
        return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()

    def test_creates_lists_and_scopes_cancel_by_chat(self) -> None:
        reminder = self.reminders.create("telegram", "123", "Take a break", self.future(), "daily")
        self.assertEqual(self.reminders.list("telegram", "123", True)[0]["id"], reminder["id"])
        with self.assertRaises(HTTPException) as error:
            self.reminders.cancel(reminder["id"], "telegram", "other")
        self.assertEqual(error.exception.status_code, 404)
        cancelled = self.reminders.cancel(reminder["id"], "telegram", "123")
        self.assertEqual(cancelled["status"], "cancelled")

    def test_validates_channel_time_and_recurrence(self) -> None:
        invalid = [
            ("web", "123", "text", self.future(), "none"),
            ("telegram", "123", "text", "2030-01-01T10:00:00", "none"),
            ("telegram", "123", "text", "not-a-date", "none"),
            ("telegram", "123", "text", self.future(), "monthly"),
        ]
        for values in invalid:
            with self.assertRaises(HTTPException):
                self.reminders.create(*values)


class ReminderDispatchTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        self.root_patch = patch.object(settings, "agent_data_dir", self.temp.name)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.reminders = ReminderStore()

    async def _cleanup(self) -> None:
        self.temp.cleanup()

    async def test_due_one_time_reminder_sends_and_completes(self) -> None:
        reminder = self.reminders.create(
            "telegram", "123", "Take medicine", (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        )
        due = datetime.now(UTC) + timedelta(hours=2)
        send = AsyncMock()
        sent_count = await self.reminders.dispatch_due(send, due)
        self.assertEqual(sent_count, 1)
        send.assert_awaited_once_with("telegram", "123", "⏰ Reminder: Take medicine")
        self.assertEqual(self.reminders.get(reminder["id"])["status"], "completed")

    async def test_recurring_reminder_advances_past_missed_intervals(self) -> None:
        reminder = self.reminders.create(
            "whatsapp", "chat", "Water plants", (datetime.now(UTC) + timedelta(hours=1)).isoformat(), "daily"
        )
        due = datetime.now(UTC) + timedelta(days=4)
        await self.reminders.dispatch_due(AsyncMock(), due)
        current = self.reminders.get(reminder["id"])
        self.assertEqual(current["status"], "active")
        self.assertGreater(datetime.fromisoformat(current["next_run_at"]), due)

    async def test_failed_delivery_keeps_reminder_due_for_retry(self) -> None:
        reminder = self.reminders.create(
            "telegram", "123", "Call home", (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
        )
        due = datetime.now(UTC) + timedelta(minutes=3)
        send = AsyncMock(side_effect=RuntimeError("offline"))
        with patch("agent_core.reminders.store.append_audit"):
            self.assertEqual(await self.reminders.dispatch_due(send, due), 0)
        current = self.reminders.get(reminder["id"])
        self.assertEqual(current["status"], "active")
        self.assertIsNone(current["last_run_at"])

    async def test_agent_exposes_reminder_tools_and_scopes_creation_to_current_chat(self) -> None:
        event = InboundEvent(
            channel="telegram", chatId="123", senderId="123", messageId="m1",
            text="remind me tomorrow", timestamp=1,
        )
        tools = {item.name: item for item in AgentRuntime()._tools_for(event, [])}
        self.assertTrue({"create_reminder", "list_reminders", "cancel_reminder"}.issubset(tools))
        scheduled = {
            "id": "reminder-id", "next_run_at": "2035-01-01T10:00:00+00:00", "channel": "telegram",
        }
        with patch("agent_core.runtime.reminder_store.create", return_value=scheduled) as create:
            response = tools["create_reminder"].entrypoint(
                text="Call home", run_at="2035-01-01T10:00:00Z", recurrence="weekly",
            )
        self.assertIn("scheduled", response)
        self.assertEqual(create.call_args.args[:2], ("telegram", "123"))


if __name__ == "__main__":
    import unittest

    unittest.main()
