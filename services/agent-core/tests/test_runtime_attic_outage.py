from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agent_core.models import TelegramInboundEvent
from agent_core.runtime import AgentRuntime


@asynccontextmanager
async def unavailable_attic():
    yield None


class RuntimeAtticOutageTests(IsolatedAsyncioTestCase):
    async def test_model_reply_survives_attic_outage(self) -> None:
        agent = SimpleNamespace(
            arun=AsyncMock(return_value=SimpleNamespace(content="model answer", tools=[]))
        )
        event = TelegramInboundEvent(
            chat_id="chat-1",
            sender_id="user-1",
            message_id="message-1",
            text="hello",
            timestamp=1,
        )

        with (
            patch("agent_core.runtime.settings.groq_api_key", "test-key"),
            patch("agent_core.runtime.short_term_memory.get_messages", new=AsyncMock(return_value=[])),
            patch("agent_core.runtime.policy.load", return_value={}),
            patch("agent_core.runtime.connect_attic", unavailable_attic),
            patch("agent_core.runtime.create_agent", return_value=agent),
        ):
            result = await AgentRuntime().run(event)

        self.assertEqual(result["response_text"], "model answer")
        self.assertTrue(result["should_reply"])
        agent.arun.assert_awaited_once()

    async def test_ollama_does_not_require_groq_key(self) -> None:
        agent = SimpleNamespace(arun=AsyncMock(return_value=SimpleNamespace(content="¡Hola!", tools=[])))
        event = TelegramInboundEvent(
            chat_id="chat-1", sender_id="user-1", message_id="message-2", text="Hola", timestamp=2
        )

        with (
            patch("agent_core.runtime.settings.model_provider", "ollama"),
            patch("agent_core.runtime.settings.groq_api_key", ""),
            patch("agent_core.runtime.short_term_memory.get_messages", new=AsyncMock(return_value=[])),
            patch("agent_core.runtime.policy.load", return_value={}),
            patch("agent_core.runtime.connect_attic", unavailable_attic),
            patch("agent_core.runtime.create_agent", return_value=agent) as create_agent,
        ):
            result = await AgentRuntime().run(event)

        self.assertEqual(result["selected_model"], "llama3.2:latest")
        self.assertEqual(result["response_text"], "¡Hola!")
        create_agent.assert_called_once()
