import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agent_core.config import settings
from agent_core.models import InboundEvent
from agent_core.runtime import AgentRuntime
from agent_core.tooling.internal_api import create_internal_api_tool


class InternalApiToolTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.event = InboundEvent(
            channel="cli", chatId="local", senderId="owner", messageId="m1",
            text="what tools are active", timestamp=1,
        )

    def test_runtime_exposes_read_tool_only_with_admin_key(self) -> None:
        with patch.object(settings, "admin_api_key", "secret"):
            names = {item.name for item in AgentRuntime()._tools_for(self.event, [])}
        self.assertIn("read_internal_api", names)

        with patch.object(settings, "admin_api_key", ""):
            names = {item.name for item in AgentRuntime()._tools_for(self.event, [])}
        self.assertNotIn("read_internal_api", names)

    async def test_status_call_uses_private_key_and_scrubs_policy_and_paths(self) -> None:
        response = {
            "ok": True,
            "service": "agent-core",
            "model_provider": "ollama",
            "policy": {"telegram": {"allowed_chat_ids": ["private-chat"]}},
            "tools_dir": "/private/path",
            "long_term_memory_db_path": "/private/db",
        }
        with (
            patch.object(settings, "admin_api_key", "secret"),
            patch("agent_core.main.admin_status", new=AsyncMock(return_value=response)) as route,
            patch("agent_core.tooling.internal_api.store.append_audit") as audit,
        ):
            tool = create_internal_api_tool({"channel": "cli", "chat_id": "local", "message_id": "m1"})
            result = json.loads(await tool.entrypoint(resource="status"))

        route.assert_awaited_once_with(x_admin_api_key="secret")
        self.assertEqual(result, {"ok": True, "service": "agent-core", "model_provider": "ollama"})
        audit.assert_called_once_with(
            "internal_api_tool_called",
            {"channel": "cli", "chat_id": "local", "message_id": "m1", "resource": "status"},
        )

    async def test_only_allowlisted_read_endpoints_are_callable(self) -> None:
        with (
            patch.object(settings, "admin_api_key", "secret"),
            patch("agent_core.main.admin_capabilities", new=AsyncMock(return_value={"ok": True})) as capabilities,
            patch("agent_core.main.admin_tools", new=AsyncMock(return_value={"tools": []})) as tools,
            patch("agent_core.main.admin_scheduler_jobs", new=AsyncMock(return_value={"jobs": []})) as jobs,
        ):
            tool = create_internal_api_tool({"channel": "cli", "chat_id": "local", "message_id": "m1"})
            for resource in ("capabilities", "tools", "scheduled_jobs"):
                await tool.entrypoint(resource=resource)

        capabilities.assert_awaited_once_with(x_admin_api_key="secret")
        tools.assert_awaited_once_with(x_admin_api_key="secret")
        jobs.assert_awaited_once_with(x_admin_api_key="secret")

    async def test_missing_key_fails_closed_without_calling_backend(self) -> None:
        with (
            patch.object(settings, "admin_api_key", ""),
            patch("agent_core.main.admin_status", new=AsyncMock()) as route,
        ):
            tool = create_internal_api_tool({"channel": "cli", "chat_id": "local", "message_id": "m1"})
            result = await tool.entrypoint(resource="status")

        self.assertIn("admin key is not configured", result)
        route.assert_not_awaited()
