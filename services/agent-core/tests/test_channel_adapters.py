from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from agent_core import main
from agent_core.channels import ChannelManager
from agent_core.integrations.telegram_bot import TelegramBotService
from agent_core.models import InboundEvent, TelegramInboundEvent
from agent_core.service import AgentOrchestrator, store


class ChannelAdapterTests(IsolatedAsyncioTestCase):
    async def test_both_channels_use_shared_runtime_and_reply(self) -> None:
        orchestrator = AgentOrchestrator()
        orchestrator._runtime.run = AsyncMock(
            return_value={"should_reply": True, "response_text": "shared answer"}
        )
        orchestrator.channels.send = AsyncMock()
        orchestrator._safe_persist_inbound = lambda *args: None
        orchestrator._safe_persist_outbound = lambda *args: None
        orchestrator._safe_append_short_term_message = AsyncMock()
        orchestrator._safe_add_long_term_node = lambda *args: None
        orchestrator._safe_audit = lambda *args: None

        whatsapp = InboundEvent(
            channel="whatsapp", chatId="chat-wa", senderId="user-wa",
            messageId="message-wa", text="hello", timestamp=1,
        )
        telegram = TelegramInboundEvent(
            chat_id="chat-tg", sender_id="user-tg", message_id="message-tg",
            text="hello", timestamp=1,
        )

        with (
            patch.object(store, "is_duplicate_message", return_value=False),
            patch.object(store, "mark_message_processed"),
            patch("agent_core.service.long_term_memory.add_edge"),
        ):
            await orchestrator.process_whatsapp_event(whatsapp)
            await orchestrator.process_telegram_event(telegram)

        self.assertEqual(orchestrator._runtime.run.await_args_list[0].args, (whatsapp,))
        self.assertEqual(orchestrator._runtime.run.await_args_list[1].args, (telegram,))
        self.assertEqual(orchestrator.channels.send.await_count, 2)
        self.assertEqual(
            [call.args[:2] for call in orchestrator.channels.send.await_args_list],
            [("whatsapp", "chat-wa"), ("telegram", "chat-tg")],
        )

    async def test_channel_manager_uses_channel_specific_senders(self) -> None:
        telegram = TelegramBotService(AsyncMock())
        manager = ChannelManager(telegram, None, None, None)
        manager._whatsapp.send_message = AsyncMock()
        telegram.send_message = AsyncMock()

        await manager.send("whatsapp", "wa-chat", "reply")
        await manager.send("telegram", "42", "reply")

        manager._whatsapp.send_message.assert_awaited_once_with("wa-chat", "reply")
        telegram.send_message.assert_awaited_once_with("42", "reply")

    async def test_duplicate_event_does_not_run_or_send_again(self) -> None:
        orchestrator = AgentOrchestrator()
        orchestrator._runtime.run = AsyncMock()
        orchestrator.channels.send = AsyncMock()
        event = TelegramInboundEvent(
            chat_id="chat", sender_id="user", message_id="seen", text="hello", timestamp=1,
        )

        with patch.object(store, "is_duplicate_message", return_value=True):
            result = await orchestrator.process_telegram_event(event)

        self.assertTrue(result["duplicate"])
        orchestrator._runtime.run.assert_not_awaited()
        orchestrator.channels.send.assert_not_awaited()

    async def test_telegram_rejects_chat_outside_allowlist(self) -> None:
        callback = AsyncMock()
        bot = TelegramBotService(callback)
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=99),
            effective_user=SimpleNamespace(id=10),
            effective_message=SimpleNamespace(
                text="hello", message_id=1, date=datetime.now(UTC),
            ),
        )

        with patch("agent_core.integrations.telegram_bot.settings.telegram_allowed_chat_ids", "42"):
            await bot._on_text(update, None)

        callback.assert_not_awaited()

    async def test_whatsapp_webhook_rejects_invalid_api_key(self) -> None:
        event = InboundEvent(
            channel="whatsapp", chatId="chat", senderId="user",
            messageId="message", text="hello", timestamp=1,
        )
        with (
            patch.object(main.settings, "whatsapp_webhook_api_key", "secret"),
        ):
            with self.assertRaises(HTTPException) as error:
                await main.whatsapp_webhook(event, x_api_key="wrong")

        self.assertEqual(error.exception.status_code, 401)
