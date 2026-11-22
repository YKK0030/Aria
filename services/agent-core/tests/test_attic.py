from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from agent_core.memory import attic


class AtticConnectionTests(IsolatedAsyncioTestCase):
    async def test_disabled_without_api_key(self) -> None:
        with (
            patch.object(attic.settings, "attic_enabled", True),
            patch.object(attic.settings, "attic_mcp_api_key", " "),
            patch.object(attic, "MCPTools") as mcp_tools,
        ):
            async with attic.connect_attic() as tools:
                self.assertIsNone(tools)
            mcp_tools.assert_not_called()

    async def test_connect_uses_bearer_auth_and_closes(self) -> None:
        client = AsyncMock()
        writer = MagicMock()
        writer.wait_closed = AsyncMock()
        with (
            patch.object(attic.settings, "attic_enabled", True),
            patch.object(attic.settings, "attic_mcp_api_key", "secret"),
            patch.object(attic.settings, "attic_mcp_url", "http://attic/mcp"),
            patch.object(attic.asyncio, "open_connection", new=AsyncMock(return_value=(None, writer))),
            patch.object(attic, "MCPTools", return_value=client) as mcp_tools,
        ):
            async with attic.connect_attic() as tools:
                self.assertIs(tools, client)

            options = mcp_tools.call_args.kwargs
            self.assertEqual(options["server_params"].headers, {"Authorization": "Bearer secret"})
            self.assertEqual(options["include_tools"], ["remember", "recall", "health"])
            client.connect.assert_awaited_once()
            client.close.assert_awaited_once()

    async def test_unreachable_endpoint_returns_no_tools(self) -> None:
        with (
            patch.object(attic.settings, "attic_enabled", True),
            patch.object(attic.settings, "attic_mcp_api_key", "secret"),
            patch.object(attic, "MCPTools") as mcp_tools,
            patch.object(attic.asyncio, "open_connection", side_effect=ConnectionRefusedError),
        ):
            async with attic.connect_attic() as tools:
                self.assertIsNone(tools)
            mcp_tools.assert_not_called()

    async def test_failed_connection_returns_no_tools(self) -> None:
        client = AsyncMock()
        client.connect.side_effect = OSError("offline")
        with (
            patch.object(attic.settings, "attic_enabled", True),
            patch.object(attic.settings, "attic_mcp_api_key", "secret"),
            patch.object(
                attic.asyncio,
                "open_connection",
                new=AsyncMock(return_value=(None, MagicMock(wait_closed=AsyncMock()))),
            ),
            patch.object(attic, "MCPTools", return_value=client),
        ):
            async with attic.connect_attic() as tools:
                self.assertIsNone(tools)
            client.close.assert_awaited_once()
