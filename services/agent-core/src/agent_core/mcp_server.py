from __future__ import annotations

import hmac
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from agent_core.commands import capabilities_text
from agent_core.config import settings
from agent_core.memory import long_term_memory
from agent_core.models import TelegramInboundEvent
from agent_core.service import AgentOrchestrator


class MCPBearerAuth:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        api_key = settings.mcp_api_key.strip()
        if not api_key:
            response = JSONResponse({"detail": "ADMIN_API_KEY is not configured"}, status_code=503)
        else:
            authorization = Request(scope).headers.get("authorization", "")
            scheme, _, supplied_key = authorization.partition(" ")
            if scheme.lower() != "bearer" or not hmac.compare_digest(supplied_key, api_key):
                response = JSONResponse({"detail": "Invalid bearer token"}, status_code=401)
            else:
                await self._app(scope, receive, send)
                return

        await response(scope, receive, send)


def create_mcp_server(orchestrator: AgentOrchestrator) -> FastMCP:
    server = FastMCP(
        name="Aria",
        instructions="Use Aria's ask and identity-scoped memory tools. Never request raw channel or database access.",
        transport_security=TransportSecuritySettings(allowed_hosts=settings.allowed_mcp_hosts),
    )
    identity = settings.mcp_identity.strip() or "local"
    chat_id = f"mcp:{identity}"

    @server.tool()
    async def ask(message: str) -> str:
        """Ask Aria using the same agent runtime as WhatsApp and Telegram."""
        if not message.strip():
            raise ValueError("message must not be empty")
        event = TelegramInboundEvent(
            channel="mcp",
            chat_id=chat_id,
            sender_id=identity,
            message_id=uuid4().hex,
            text=message,
            timestamp=int(time.time()),
        )
        result = await orchestrator.process_mcp_event(event)
        return str(result.get("response_text", ""))

    @server.tool()
    def memory_search(query: str, limit: int = 5) -> list[dict]:
        """Search only this authenticated identity's saved Aria memories."""
        return long_term_memory.search_nodes("mcp", chat_id, query, max(1, min(limit, 20)))

    @server.tool()
    def remember(text: str) -> dict:
        """Save a memory for this authenticated identity."""
        if not text.strip():
            raise ValueError("text must not be empty")
        memory_id = long_term_memory.add_node("mcp", chat_id, "memory", text.strip())
        if memory_id is None:
            raise RuntimeError("Memory could not be saved")
        return {"id": memory_id}

    @server.tool()
    def forget(memory_id: int) -> bool:
        """Delete one of this authenticated identity's saved memories by ID."""
        return long_term_memory.delete_node("mcp", chat_id, memory_id)

    @server.tool()
    def capabilities() -> str:
        """List Aria's supported capabilities."""
        return capabilities_text()

    return server
