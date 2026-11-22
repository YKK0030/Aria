from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from fastapi import HTTPException

from agent_core.approvals import ApprovalStore
from agent_core.config import settings
from agent_core.models import InboundEvent
from agent_core.runtime import AgentRuntime


class ApprovalStoreTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch_root = patch.object(settings, "agent_data_dir", self.temp.name)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.approvals = ApprovalStore()

    def create_request(self) -> dict:
        return self.approvals.create(
            "send_message", "Send an update", "Send the approved update to the listed recipient.",
            {"channel": "web", "chat_id": "owner"},
        )

    def test_create_and_list_persist_request(self) -> None:
        request = self.create_request()
        self.assertEqual(request["status"], "pending")
        self.assertEqual(self.approvals.get(request["id"]), request)
        self.assertEqual(self.approvals.list("pending"), [request])

    def test_owner_decision_is_one_time_and_durable(self) -> None:
        request = self.create_request()
        decided = self.approvals.decide(request["id"], "approved", "admin_api")
        self.assertEqual(decided["status"], "approved")
        self.assertEqual(decided["decided_by"], "admin_api")
        self.assertEqual(self.approvals.get(request["id"])["status"], "approved")
        with self.assertRaises(HTTPException) as error:
            self.approvals.decide(request["id"], "rejected", "telegram:1")
        self.assertEqual(error.exception.status_code, 409)

    def test_expired_request_cannot_be_approved(self) -> None:
        request = self.create_request()
        request["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        self.approvals._write(request)
        with self.assertRaises(HTTPException) as error:
            self.approvals.decide(request["id"], "approved", "owner")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.approvals.get(request["id"])["status"], "expired")

    def test_validation_and_unknown_ids_fail_closed(self) -> None:
        with self.assertRaises(HTTPException):
            self.approvals.create("../shell", "Bad", "details", {})
        with self.assertRaises(HTTPException) as error:
            self.approvals.get("not-a-uuid")
        self.assertEqual(error.exception.status_code, 404)


class ApprovalToolTests(IsolatedAsyncioTestCase):
    async def test_model_tool_creates_audited_request_without_execution(self) -> None:
        event = InboundEvent(
            channel="telegram", chatId="123", senderId="123", messageId="m1",
            text="send a message", timestamp=1,
        )
        runtime = AgentRuntime()
        tools = {item.name: item for item in runtime._tools_for(event, [])}
        self.assertIn("request_human_approval", tools)
        with (
            patch("agent_core.runtime.approval_store.create", return_value={
                "id": "approval-id", "summary": "Send update", "action": "send_message",
            }) as create,
            patch("agent_core.runtime.store.append_audit") as audit,
        ):
            result = tools["request_human_approval"].entrypoint(
                action="send_message", summary="Send update", details="Exact message and recipient",
            )
        self.assertIn("No action was performed", result)
        create.assert_called_once_with(
            "send_message", "Send update", "Exact message and recipient",
            {"channel": "telegram", "chat_id": "123"},
        )
        audit.assert_called_once()

