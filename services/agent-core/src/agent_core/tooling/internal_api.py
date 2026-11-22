from __future__ import annotations

import json
from typing import Any, Literal

from agno.tools import tool as agno_tool
from fastapi import HTTPException

from agent_core.config import settings
from agent_core.storage import store

InternalResource = Literal["status", "capabilities", "tools", "scheduled_jobs"]


def create_internal_api_tool(trace_context: dict[str, str]) -> Any:
    async def read_internal_api(resource: InternalResource) -> str:
        """Read one allowlisted Aria backend API. This tool cannot modify state."""
        if not settings.has_admin_api_key:
            return "Internal API reads are unavailable because the admin key is not configured."

        from agent_core import main

        endpoints = {
            "status": main.admin_status,
            "capabilities": main.admin_capabilities,
            "tools": main.admin_tools,
            "scheduled_jobs": main.admin_scheduler_jobs,
        }
        endpoint = endpoints.get(resource)
        if endpoint is None:
            raise ValueError("Unsupported internal API resource.")

        try:
            result = await endpoint(x_admin_api_key=settings.admin_api_key)
        except HTTPException as error:
            return f"Internal API read failed with status {error.status_code}."
        except Exception:
            return "Internal API read failed. No backend details were returned."

        if resource == "status":
            result = result.model_dump() if hasattr(result, "model_dump") else dict(result)
            for sensitive_field in ("policy", "long_term_memory_db_path", "tools_dir"):
                result.pop(sensitive_field, None)

        store.append_audit(
            "internal_api_tool_called",
            {**trace_context, "resource": resource},
        )
        return json.dumps(result, ensure_ascii=False, default=str)

    return agno_tool(
        name="read_internal_api",
        description=(
            "Read Aria's allowlisted internal backend APIs: status, capabilities, registered tools, "
            "or scheduled jobs. Read-only; cannot send messages, change allowlists, modify tools, "
            "read conversation history, or access secrets. Use only when the user asks about Aria's "
            "runtime or internal capabilities."
        ),
    )(read_internal_api)
