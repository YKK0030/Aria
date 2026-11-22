from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import httpx

from agent_core.config import settings
from agent_core.main import app
from agent_core.reminders import reminder_store


class ReminderApiTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        self.addAsyncCleanup(self.client.aclose)
        self.key_patch = patch.object(settings, "admin_api_key", "test-admin")
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.root_patch = patch.object(reminder_store, "root", Path(self.temp.name))
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.audit_patch = patch("agent_core.main.store.append_audit")
        self.audit_patch.start()
        self.addCleanup(self.audit_patch.stop)

    async def _cleanup(self) -> None:
        self.temp.cleanup()

    async def test_admin_can_create_list_and_cancel_reminder(self) -> None:
        denied = await self.client.get("/admin/reminders")
        self.assertEqual(denied.status_code, 401)
        headers = {"x-admin-api-key": "test-admin"}
        run_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        created = await self.client.post("/admin/reminders", headers=headers, json={
            "channel": "telegram", "chat_id": "123", "text": "Take a break",
            "run_at": run_at, "recurrence": "weekly",
        })
        self.assertEqual(created.status_code, 200)
        reminder_id = created.json()["reminder"]["id"]
        listed = await self.client.get("/admin/reminders?active_only=true", headers=headers)
        self.assertEqual(listed.json()["reminders"][0]["id"], reminder_id)
        cancelled = await self.client.delete(f"/admin/reminders/{reminder_id}", headers=headers)
        self.assertEqual(cancelled.json()["reminder"]["status"], "cancelled")

    async def test_admin_rejects_non_push_channel(self) -> None:
        headers = {"x-admin-api-key": "test-admin"}
        response = await self.client.post("/admin/reminders", headers=headers, json={
            "channel": "web", "chat_id": "browser", "text": "Do it",
            "run_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        })
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    import unittest

    unittest.main()
