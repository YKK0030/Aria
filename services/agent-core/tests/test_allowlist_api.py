from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import httpx

from agent_core.config import settings
from agent_core.main import app
from agent_core.policy import policy


class AllowlistApiTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        self.addAsyncCleanup(self.client.aclose)
        self.key_patch = patch.object(settings, "admin_api_key", "test-admin")
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.path_patch = patch.object(policy, "_override_path", Path(self.temp.name) / "overrides.json")
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.audit_patch = patch("agent_core.main.store.append_audit")
        self.audit_patch.start()
        self.addCleanup(self.audit_patch.stop)

    async def _cleanup(self) -> None:
        self.temp.cleanup()

    async def test_admin_can_update_read_and_reset_allowlists(self) -> None:
        denied = await self.client.get("/admin/allowlists")
        self.assertEqual(denied.status_code, 401)
        headers = {"x-admin-api-key": "test-admin"}
        updated = await self.client.put("/admin/allowlists/telegram", headers=headers, json={
            "allowed_chat_ids": ["123"], "blocked_chat_ids": ["456"],
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["allowlist"]["allowed_chat_ids"], ["123"])
        view = await self.client.get("/admin/allowlists", headers=headers)
        self.assertTrue(view.json()["allowlists"]["telegram"]["managed"])
        self.assertEqual(view.json()["allowlists"]["telegram"]["blocked_chat_ids"], ["456"])
        reset = await self.client.delete("/admin/allowlists/telegram", headers=headers)
        self.assertEqual(reset.status_code, 200)
        self.assertFalse(reset.json()["managed"])

    async def test_admin_rejects_invalid_channel_and_conflicting_ids(self) -> None:
        headers = {"x-admin-api-key": "test-admin"}
        bad_channel = await self.client.put("/admin/allowlists/email", headers=headers, json={
            "allowed_chat_ids": [], "blocked_chat_ids": [],
        })
        self.assertEqual(bad_channel.status_code, 422)
        conflict = await self.client.put("/admin/allowlists/whatsapp", headers=headers, json={
            "allowed_chat_ids": ["same"], "blocked_chat_ids": ["same"],
        })
        self.assertEqual(conflict.status_code, 422)


if __name__ == "__main__":
    import unittest

    unittest.main()
