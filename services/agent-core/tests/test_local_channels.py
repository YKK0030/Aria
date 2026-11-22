from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from agent_core import main
from agent_core.config import settings
from agent_core.config import Settings


class LocalChannelTests(IsolatedAsyncioTestCase):
    async def test_channel_selection_supports_individual_and_all(self) -> None:
        self.assertEqual(Settings(ARIA_CHANNELS="cli,web").enabled_channels, {"cli", "web"})
        self.assertEqual(
            Settings(ARIA_CHANNELS="all").enabled_channels,
            {"cli", "web", "telegram", "whatsapp", "slack", "discord", "email"},
        )
        self.assertEqual(Settings(ARIA_CHANNELS="unknown,cli").enabled_channels, {"cli"})

    async def test_web_chat_requires_admin_key_and_enabled_channel(self) -> None:
        process_event = AsyncMock(return_value={"response_text": "ok"})
        with (
            patch.object(settings, "admin_api_key", "secret"),
            patch.object(settings, "aria_channels", "web"),
            patch.object(main.orchestrator, "process_local_event", process_event),
        ):
            with self.assertRaises(HTTPException) as error:
                await main.local_chat(main.LocalChatRequest(text="hello"), x_admin_api_key="wrong")
            self.assertEqual(error.exception.status_code, 401)

            result = await main.local_chat(main.LocalChatRequest(text="hello"), x_admin_api_key="secret")

        self.assertEqual(result["response_text"], "ok")
        event = process_event.await_args.args[0]
        self.assertEqual(event.channel, "web")
        self.assertEqual(event.text, "hello")

    async def test_disabled_web_channel_rejects_prompt(self) -> None:
        with (
            patch.object(settings, "admin_api_key", "secret"),
            patch.object(settings, "aria_channels", "cli"),
        ):
            with self.assertRaises(HTTPException) as error:
                await main.local_chat(main.LocalChatRequest(text="hello"), x_admin_api_key="secret")
        self.assertEqual(error.exception.status_code, 503)

    async def test_voice_chat_marks_request_for_concise_spoken_answer(self) -> None:
        process_event = AsyncMock(return_value={"response_text": "ok"})
        with (
            patch.object(settings, "admin_api_key", "secret"),
            patch.object(settings, "aria_channels", "web"),
            patch.object(main.orchestrator, "process_local_event", process_event),
        ):
            await main.local_chat(
                main.LocalChatRequest(text="What is new?", voice_mode=True), x_admin_api_key="secret"
            )
        event = process_event.await_args.args[0]
        self.assertTrue(event.voice_mode)
        from agent_core.runtime import AgentRuntime
        self.assertIn("at most 60 words", AgentRuntime._system_message(voice_mode=True))
        self.assertNotIn("at most 60 words", AgentRuntime._system_message())

    async def test_local_web_pages_are_served(self) -> None:
        chat = await main.local_chat_ui()
        trace = await main.local_trace_ui()
        command_center = await main.command_center_ui()
        memory = await main.memory_ui()
        self.assertIn("Talk to Aria", chat.body.decode())
        self.assertIn("/aria-trace", chat.body.decode())
        self.assertIn("hidden chain-of-thought", trace.body.decode())
        self.assertIn("Command centre", command_center.body.decode())
        self.assertIn("Redis/Valkey", memory.body.decode())

    async def test_short_term_memory_api_is_admin_protected(self) -> None:
        messages = [{"role": "user", "text": "hello", "ts": "now"}]
        with (
            patch.object(settings, "admin_api_key", "secret"),
            patch.object(main.short_term_memory, "get_messages", new=AsyncMock(return_value=messages)) as get_messages,
        ):
            with self.assertRaises(HTTPException) as error:
                await main.admin_short_term_memory("web", "session-1", 4, "wrong")
            self.assertEqual(error.exception.status_code, 401)

            result = await main.admin_short_term_memory("web", "session-1", 4, "secret")

        self.assertEqual(result["messages"], messages)
        get_messages.assert_awaited_once_with("web", "session-1", limit_turns=4)

    async def test_audit_trace_api_requires_admin_key(self) -> None:
        with patch.object(settings, "admin_api_key", "secret"):
            with self.assertRaises(HTTPException) as error:
                await main.admin_audit(10, None, None, "wrong")
            self.assertEqual(error.exception.status_code, 401)
