from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from urllib.parse import urlsplit

from agno.tools.mcp import MCPTools
from agno.tools.mcp.params import StreamableHTTPClientParams

from agent_core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def connect_attic() -> AsyncIterator[MCPTools | None]:
    if not settings.attic_enabled or not settings.attic_mcp_api_key.strip():
        yield None
        return

    endpoint = urlsplit(settings.attic_mcp_url)
    try:
        # Avoid Agno MCPTools' leaked cancellation when the configured port refuses connections.
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(endpoint.hostname, endpoint.port or (443 if endpoint.scheme == "https" else 80)),
            timeout=2,
        )
        writer.close()
        await writer.wait_closed()
    except (OSError, TimeoutError, ValueError) as error:
        logger.warning(
            "Attic MCP unavailable; continuing without durable memory (%s)",
            type(error).__name__,
        )
        yield None
        return

    tools: MCPTools | None = None
    try:
        tools = MCPTools(
            transport="streamable-http",
            server_params=StreamableHTTPClientParams(
                url=settings.attic_mcp_url,
                headers={"Authorization": f"Bearer {settings.attic_mcp_api_key}"},
                timeout=timedelta(seconds=10),
            ),
            tool_name_prefix="attic",
            include_tools=["remember", "recall", "health"],
            timeout_seconds=10,
            refresh_connection=True,
        )
        await tools.connect()
    except Exception as error:
        logger.warning(
            "Attic MCP unavailable; continuing without durable memory (%s)",
            type(error).__name__,
        )
        if tools:
            try:
                await tools.close()
            except Exception:
                pass
        yield None
        return

    try:
        yield tools
    finally:
        try:
            await tools.close()
        except Exception as error:
            logger.warning("Attic MCP cleanup failed (%s)", type(error).__name__)
