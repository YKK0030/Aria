from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agent_core.approvals import ApprovalStore
from agent_core.approval_actions import decide_approval, handle_whatsapp_approval_command
from agent_core.config import settings
from agent_core.models import InboundEvent


class ApprovalActionTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.channels_patch = patch.object(settings, "aria_channels", "all")
        self.channels_patch.start()
        self.addCleanup(self.channels_patch.stop)
        self.approvals = ApprovalStore()
        self.approvals.root = Path(self.temp.name)
        self.request = self.approvals.create(
            "send_message", "Send release note", "Destination and exact text.",
            {"channel": "telegram", "chat_id": "123"},
            {"channel": "whatsapp", "chat_id": "15551234567@s.whatsapp.net", "text": "Released."},
        )

    async def test_approval_sends_only_the_bound_message(self) -> None:
        sender = AsyncMock()
        with (
            patch("agent_core.approval_actions.approval_store", self.approvals),
            patch("agent_core.approval_actions.store.append_audit"),
        ):
            record = await decide_approval(self.request["id"], "approved", "telegram:123", sender)

        sender.assert_awaited_once_with("whatsapp", "15551234567@s.whatsapp.net", "Released.")
        self.assertEqual(record["execution_status"], "succeeded")

    async def test_rejection_never_sends(self) -> None:
        sender = AsyncMock()
        with (
            patch("agent_core.approval_actions.approval_store", self.approvals),
            patch("agent_core.approval_actions.store.append_audit"),
        ):
            record = await decide_approval(self.request["id"], "rejected", "whatsapp:owner", sender)

        sender.assert_not_awaited()
        self.assertEqual(record["status"], "rejected")

    async def test_delivery_failure_is_recorded_without_retry(self) -> None:
        sender = AsyncMock(side_effect=OSError("gateway unavailable"))
        with (
            patch("agent_core.approval_actions.approval_store", self.approvals),
            patch("agent_core.approval_actions.store.append_audit"),
        ):
            record = await decide_approval(self.request["id"], "approved", "whatsapp:owner", sender)

        sender.assert_awaited_once()
        self.assertEqual(record["execution_status"], "failed")
        self.assertEqual(record["execution_error_type"], "OSError")

    async def test_whatsapp_owner_can_list_and_approve_from_a_private_chat(self) -> None:
        jid = "15551234567@s.whatsapp.net"
        event = InboundEvent(
            channel="whatsapp", chatId=jid, senderId=jid, messageId="m1", text="/approvals", timestamp=1,
        )
        sender = AsyncMock()
        with (
            patch.object(settings, "whatsapp_owner_numbers", "15551234567"),
            patch("agent_core.approval_actions.policy.load", return_value={"whatsapp": {"enabled": True}}),
            patch("agent_core.approval_actions.approval_store", self.approvals),
            patch("agent_core.approval_actions.store.append_audit"),
        ):
            listing = await handle_whatsapp_approval_command(event, sender)
            self.assertIn("Send via whatsapp", listing)
            self.assertIn(self.request["id"][:8], listing)
            event.text = f"/approve {self.request['id'][:8]}"
            result = await handle_whatsapp_approval_command(event, sender)

        self.assertIn("Approved and sent", result)
        sender.assert_awaited_once_with("whatsapp", jid, "Released.")

    async def test_group_or_non_owner_cannot_review_or_decide(self) -> None:
        jid = "15551234567@s.whatsapp.net"
        event = InboundEvent(
            channel="whatsapp", chatId=jid, senderId=jid, messageId="m1", text="/approvals", timestamp=1,
        )
        sender = AsyncMock()
        with (
            patch.object(settings, "whatsapp_owner_numbers", "99999999999"),
            patch("agent_core.approval_actions.policy.load", return_value={"whatsapp": {"enabled": True}}),
            patch("agent_core.approval_actions.approval_store", self.approvals),
        ):
            result = await handle_whatsapp_approval_command(event, sender)
            event.is_group = True
            with (
                patch.object(settings, "whatsapp_owner_numbers", "15551234567"),
                patch("agent_core.approval_actions.policy.load", return_value={"whatsapp": {"enabled": True}}),
            ):
                group_result = await handle_whatsapp_approval_command(event, sender)

        self.assertIn("owner private chat", result)
        self.assertIn("owner private chat", group_result)
        self.assertEqual(self.approvals.get(self.request["id"])["status"], "pending")

    async def test_whatsapp_owner_controls_respect_channel_allowlist(self) -> None:
        jid = "15551234567@s.whatsapp.net"
        event = InboundEvent(
            channel="whatsapp", chatId=jid, senderId=jid, messageId="m1", text="/approvals", timestamp=1,
        )
        with (
            patch.object(settings, "whatsapp_owner_numbers", "15551234567"),
            patch("agent_core.approval_actions.policy.load", return_value={
                "whatsapp": {"enabled": True, "allowed_chat_ids": ["another-chat"]}
            }),
        ):
            result = await handle_whatsapp_approval_command(event, AsyncMock())

        self.assertIn("owner private chat", result)
        self.assertEqual(self.approvals.get(self.request["id"])["status"], "pending")

    async def test_non_approval_whatsapp_message_is_left_for_normal_agent(self) -> None:
        event = InboundEvent(
            channel="whatsapp", chatId="chat", senderId="chat", messageId="m1", text="hello", timestamp=1,
        )
        self.assertIsNone(await handle_whatsapp_approval_command(event, AsyncMock()))

