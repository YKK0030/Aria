from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

import httpx
from mcp.shared.memory import create_connected_server_and_client_session
from starlette.responses import JSONResponse

from agent_core.config import settings
from agent_core.main import app
from agent_core.mcp_server import MCPBearerAuth, create_mcp_server


class MCPServerTests(IsolatedAsyncioTestCase):
    async def test_client_discovers_narrow_tools_and_calls_shared_runtime(self) -> None:
        orchestrator = type("Orchestrator", (), {})()
        orchestrator.process_mcp_event = AsyncMock(return_value={"response_text": "Aria says hello"})
        with patch.object(settings, "mcp_identity", "alice"):
            server = create_mcp_server(orchestrator)

        async with create_connected_server_and_client_session(server) as client:
            await client.initialize()
            tools = await client.list_tools()
            result = await client.call_tool("ask", {"message": "hello"})

        self.assertEqual(
            {tool.name for tool in tools.tools},
            {"ask", "memory_search", "remember", "forget", "capabilities"},
        )
        self.assertEqual(result.content[0].text, "Aria says hello")
        event = orchestrator.process_mcp_event.await_args.args[0]
        self.assertEqual((event.channel, event.chat_id, event.sender_id), ("mcp", "mcp:alice", "alice"))

    async def test_memory_tools_use_only_configured_identity_namespace(self) -> None:
        orchestrator = type("Orchestrator", (), {"process_mcp_event": AsyncMock()})()
        with (
            patch.object(settings, "mcp_identity", "alice"),
            patch("agent_core.mcp_server.long_term_memory.add_node", return_value=17) as add_node,
            patch("agent_core.mcp_server.long_term_memory.search_nodes", return_value=[]) as search_nodes,
            patch("agent_core.mcp_server.long_term_memory.delete_node", return_value=True) as delete_node,
        ):
            server = create_mcp_server(orchestrator)
            async with create_connected_server_and_client_session(server) as client:
                await client.initialize()
                saved = await client.call_tool("remember", {"text": "likes tea"})
                await client.call_tool("memory_search", {"query": "tea"})
                await client.call_tool("forget", {"memory_id": 17})

        self.assertFalse(saved.model_dump(by_alias=True).get("isError", False))
        add_node.assert_called_once_with("mcp", "mcp:alice", "memory", "likes tea")
        search_nodes.assert_called_once_with("mcp", "mcp:alice", "tea", 5)
        delete_node.assert_called_once_with("mcp", "mcp:alice", 17)

    async def test_bearer_middleware_rejects_missing_and_accepts_configured_key(self) -> None:
        async def downstream(scope, receive, send):
            await JSONResponse({"ok": True})(scope, receive, send)

        with patch.object(settings, "admin_api_key", "test-secret"):
            client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=MCPBearerAuth(downstream)),
                base_url="http://test",
            )
            async with client:
                denied = await client.get("/mcp")
                allowed = await client.get("/mcp", headers={"Authorization": "Bearer test-secret"})

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)

    async def test_fastapi_mount_keeps_health_open_and_mcp_closed_by_default(self) -> None:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                health = await client.get("/health")
                with patch.object(settings, "admin_api_key", ""):
                    mcp = await client.get("/mcp")
                with patch.object(settings, "admin_api_key", "test-secret"):
                    initialize = await client.post(
                        "/mcp",
                        headers={
                            "Authorization": "Bearer test-secret",
                            "Accept": "application/json, text/event-stream",
                        },
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-03-26",
                                "capabilities": {},
                                "clientInfo": {"name": "aria-test", "version": "1.0"},
                            },
                        },
                    )

        self.assertEqual(health.status_code, 200)
        self.assertEqual(mcp.status_code, 503)
        self.assertEqual(initialize.status_code, 200, initialize.text)
