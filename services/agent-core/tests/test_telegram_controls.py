from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agent_core.config import settings
from agent_core.integrations.telegram_bot import TelegramBotService
from agent_core.storage import store


class TelegramControlTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = TelegramBotService(AsyncMock())

    async def test_owner_controls_require_allowlisted_private_chat(self) -> None:
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(type="private", id=123),
            effective_user=SimpleNamespace(id=123),
        )
        with patch.object(settings, "telegram_allowed_chat_ids", "123"):
            self.assertTrue(self.bot._is_authorized_owner(update))
            update.effective_chat.type = "group"
            self.assertFalse(self.bot._is_authorized_owner(update))

    async def test_unconfigured_allowlist_rejects_all_inbound_messages(self) -> None:
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(type="private", id=123, title=None),
            effective_user=SimpleNamespace(id=123, full_name="Owner"),
            effective_message=SimpleNamespace(text="hello", message_id=1, date=datetime.now(UTC)),
        )
        callback = AsyncMock()
        bot = TelegramBotService(callback)
        with patch.object(settings, "telegram_allowed_chat_ids", ""):
            await bot._on_text(update, SimpleNamespace())
        callback.assert_not_awaited()

    async def test_empty_allowlist_keeps_telegram_polling_off(self) -> None:
        with (
            patch.object(settings, "aria_channels", "telegram"),
            patch.object(settings, "telegram_bot_token", "configured"),
            patch.object(settings, "telegram_allowed_chat_ids", ""),
        ):
            await self.bot.start()
        self.assertIsNone(self.bot._app)

    async def test_approval_refuses_unreviewed_draft(self) -> None:
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)
        proposal = {"name": "subtract_numbers", "status": "tested", "sha256": "a"}
        with patch.object(self.bot, "_proposal_named", return_value=proposal):
            await self.bot._request_approval(update, ["subtract_numbers"])
        message.reply_text.assert_awaited_once()
        self.assertIn("independent review", message.reply_text.await_args.args[0])

    async def test_action_approval_callback_requires_owner_and_only_records_decision(self) -> None:
        query = SimpleNamespace(
            data="action_approve:00000000-0000-0000-0000-000000000001",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(
            callback_query=query,
            effective_chat=SimpleNamespace(type="private", id=123),
            effective_user=SimpleNamespace(id=123),
        )
        approval = {"id": "00000000-0000-0000-0000-000000000001", "action": "send_message", "summary": "Send update"}
        with (
            patch.object(settings, "telegram_allowed_chat_ids", "123"),
            patch("agent_core.integrations.telegram_bot.approval_store.decide", return_value=approval) as decide,
            patch("agent_core.integrations.telegram_bot.store.append_audit") as audit,
        ):
            await self.bot._on_approval(update, SimpleNamespace())
        decide.assert_called_once_with(approval["id"], "approved", "telegram:123")
        audit.assert_called_once()
        query.edit_message_text.assert_awaited_once()
        self.assertIn("no action was executed", query.edit_message_text.await_args.args[0].lower())

    async def test_action_approval_callback_rejects_non_owner(self) -> None:
        query = SimpleNamespace(
            data="action_reject:00000000-0000-0000-0000-000000000001",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(
            callback_query=query,
            effective_chat=SimpleNamespace(type="group", id=123),
            effective_user=SimpleNamespace(id=123),
        )
        with (
            patch.object(settings, "telegram_allowed_chat_ids", "123"),
            patch("agent_core.integrations.telegram_bot.approval_store.decide") as decide,
        ):
            await self.bot._on_approval(update, SimpleNamespace())
        decide.assert_not_called()
        query.answer.assert_awaited_once()

    async def test_telegram_does_not_offer_approval_when_details_would_be_truncated(self) -> None:
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)
        request = {
            "id": "00000000-0000-0000-0000-000000000001",
            "action": "send_message", "summary": "Send long request", "details": "x" * 3600,
            "requested_by": {"channel": "web"},
        }
        with patch("agent_core.integrations.telegram_bot.approval_store.list", return_value=[request]):
            await self.bot._list_action_approvals(update)
        message.reply_text.assert_awaited_once()
        self.assertNotIn("reply_markup", message.reply_text.await_args.kwargs)
        self.assertIn("No decision was made", message.reply_text.await_args.args[0])

    async def test_notifications_go_only_to_allowlisted_chats(self) -> None:
        send_message = AsyncMock()
        self.bot._app = SimpleNamespace(bot=SimpleNamespace(send_message=send_message))
        with patch.object(settings, "telegram_allowed_chat_ids", "321,123"):
            await self.bot.notify_completion("web", [{"name": "web_search"}])
        self.assertEqual([call.kwargs["chat_id"] for call in send_message.await_args_list], [123, 321])
        self.assertIn("web_search", send_message.await_args.kwargs["text"])

    async def test_trace_command_filters_by_requested_window(self) -> None:
        now = datetime.now(UTC).isoformat()
        records = [{
            "ts": now,
            "event_type": "inbound_web_processed",
            "payload": {
                "channel": "web",
                "result": {
                    "event": {"text": "Search for my appointment"},
                    "used_tools": [{"name": "web_search"}],
                },
            },
        }]
        with patch.object(store, "read_audit", return_value=records):
            summary = self.bot._trace_summary("2h")
        self.assertIn("Requests completed: 1", summary)
        self.assertIn("Search for my appointment", summary)
        self.assertIn("web_search", summary)


if __name__ == "__main__":
    import unittest

    unittest.main()
