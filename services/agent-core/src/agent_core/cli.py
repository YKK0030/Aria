from __future__ import annotations

import asyncio
import time
from uuid import uuid4

from agent_core.config import settings
from agent_core.models import InboundEvent
from agent_core.service import AgentOrchestrator
from agent_core.tracing import trace_summary


async def chat() -> None:
    if not settings.channel_enabled("cli"):
        raise SystemExit("CLI channel is disabled. Start Aria with ARIA_CHANNELS=cli or all.")

    orchestrator = AgentOrchestrator()
    session_id = "local-cli"
    print("Aria CLI. Type /exit to leave.")
    while True:
        try:
            prompt = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if prompt.lower() in {"/exit", "/quit"}:
            return
        if not prompt:
            continue
        if prompt.lower() == "/trace" or prompt.lower().startswith("/trace "):
            _, _, window = prompt.partition(" ")
            print(trace_summary(window.strip() or "1h"))
            continue
        event = InboundEvent(
            channel="cli",
            chatId=session_id,
            senderId="local-user",
            messageId=uuid4().hex,
            text=prompt,
            timestamp=int(time.time()),
        )
        result = await orchestrator.process_local_event(event)
        print(f"aria> {result.get('response_text', 'No response returned.')}")


def main() -> None:
    asyncio.run(chat())


if __name__ == "__main__":
    main()
