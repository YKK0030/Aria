from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import httpx

from agent_core.config import settings
from agent_core.main import app


class ApprovalApiTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        )
        self.addAsyncCleanup(self.client.aclose)
        self.root_patch = patch.object(settings, "agent_data_dir", self.temp.name)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.key_patch = patch.object(settings, "admin_api_key", "test-admin")
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.audit_patch = patch("agent_core.main.store.append_audit")
        self.audit_patch.start()
        self.addCleanup(self.audit_patch.stop)

    async def _cleanup(self) -> None:
        self.temp.cleanup()

    async def test_approval_endpoints_require_admin_and_record_single_decision(self) -> None:
        denied = await self.client.get("/admin/approvals")
        self.assertEqual(denied.status_code, 401)
        headers = {"x-admin-api-key": "test-admin"}
        created = await self.client.post("/admin/approvals", headers=headers, json={
            "action": "send_message", "summary": "Send release note",
            "details": "Recipient: owner; message: release note.",
        })
        self.assertEqual(created.status_code, 200)
        request = created.json()["approval"]
        listed = await self.client.get("/admin/approvals?status=pending", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["approvals"][0]["id"], request["id"])
        decision = await self.client.post(
            f"/admin/approvals/{request['id']}/decision", headers=headers,
            json={"decision": "approved"},
        )
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["approval"]["status"], "approved")
        again = await self.client.post(
            f"/admin/approvals/{request['id']}/decision", headers=headers,
            json={"decision": "rejected"},
        )
        self.assertEqual(again.status_code, 409)


if __name__ == "__main__":
    import unittest

    unittest.main()
