from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from runner import run_proposal


SOCKET_PATH = Path(os.getenv("ARIA_TOOL_TEST_SOCKET", "/run/aria-tool-tests/runner.sock"))
MAX_REQUEST_BYTES = 128 * 1024
test_lock = asyncio.Lock()


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request = await asyncio.wait_for(reader.readline(), timeout=3)
        if not request or len(request) > MAX_REQUEST_BYTES:
            raise ValueError("Invalid request size")
        payload = json.loads(request)
        proposal = payload.get("proposal") if isinstance(payload, dict) else None
        if not isinstance(proposal, dict):
            raise ValueError("Missing proposal")
        async with test_lock:
            result = await asyncio.to_thread(run_proposal, proposal, True)
    except Exception as error:
        result = {"passed": False, "tests": 0, "results": [], "error": type(error).__name__}
    try:
        writer.write((json.dumps(result, ensure_ascii=True) + "\n").encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def main() -> None:
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    group_id = int(os.getenv("ARIA_GID", "1000"))
    os.chown(SOCKET_PATH.parent, 0, group_id)
    os.chmod(SOCKET_PATH.parent, 0o2770)
    if SOCKET_PATH.exists():
        if not SOCKET_PATH.is_socket():
            raise RuntimeError("Tool-test socket path is not a socket")
        SOCKET_PATH.unlink()
    os.umask(0o007)
    server = await asyncio.start_unix_server(handle_client, path=str(SOCKET_PATH), limit=MAX_REQUEST_BYTES + 1)
    os.chown(SOCKET_PATH, 0, group_id)
    os.chmod(SOCKET_PATH, 0o660)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
