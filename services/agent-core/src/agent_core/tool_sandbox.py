from __future__ import annotations

import asyncio
import json


SOCKET_PATH = "/run/aria-tool-tests/runner.sock"


class ToolSandboxUnavailable(RuntimeError):
    pass


async def run_tool_tests(proposal: dict) -> dict:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(SOCKET_PATH), timeout=3)
        writer.write((json.dumps({"proposal": proposal}) + "\n").encode())
        await writer.drain()
        response = await asyncio.wait_for(reader.readline(), timeout=15)
        writer.close()
        await writer.wait_closed()
    except (OSError, TimeoutError) as error:
        raise ToolSandboxUnavailable("Isolated tool-test runner is unavailable.") from error
    try:
        result = json.loads(response)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ToolSandboxUnavailable("Isolated tool-test runner returned an invalid result.") from error
    if not isinstance(result, dict) or not isinstance(result.get("passed"), bool):
        raise ToolSandboxUnavailable("Isolated tool-test runner returned an invalid result.")
    return result
