from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from agent_core.config import settings
from agent_core.models import SlackInboundEvent
from agent_core.storage import store

logger = logging.getLogger(__name__)


class SlackBotService:
    def __init__(self, event_callback):
        self._event_callback = event_callback
        self._app: AsyncApp | None = None
        self._handler: AsyncSocketModeHandler | None = None

    async def start(self) -> None:
        if not settings.channel_enabled("slack"):
            return
        if not settings.slack_bot_token or not settings.slack_app_token:
            logger.error("Slack is enabled but SLACK_BOT_TOKEN or SLACK_APP_TOKEN is missing")
            return

        self._app = AsyncApp(token=settings.slack_bot_token)
        self._register_handlers()

        self._handler = AsyncSocketModeHandler(self._app, settings.slack_app_token)
        await self._handler.connect_async()

    async def stop(self) -> None:
        if self._handler:
            await self._handler.close_async()

    async def send_message(self, channel: str, text: str) -> None:
        if not self._app:
            raise RuntimeError("Slack bot is not started")
        await self._app.client.chat_postMessage(channel=channel, text=text)

    def _register_handlers(self) -> None:
        @self._app.event("message")
        async def handle_message(event: dict[str, Any], say: Any) -> None:
            if event.get("subtype") or not event.get("text"):
                return

            allowed_channels = set(settings.allowed_slack_channels or [])
            if allowed_channels and event.get("channel") not in allowed_channels:
                return

            event_obj = SlackInboundEvent(
                channel=event["channel"],
                sender_id=event["user"],
                message_id=event.get("ts", ""),
                text=event["text"],
                timestamp=int(float(event["ts"])),
            )
            await self._event_callback(event_obj)

        @self._app.command("/aria-status")
        async def status_command(ack: Any, command: dict[str, Any]) -> None:
            await ack()
            await say(
                f"{settings.agent_name} is online.\n"
                f"Provider: {settings.model_provider}\n"
                f"Channels: {', '.join(sorted(settings.enabled_channels))}"
            )

    async def notify_completion(self, channel: str, tool_calls: list[dict]) -> None:
        if not self._app:
            return
        tool_names = sorted({str(item.get("name", "tool")) for item in tool_calls if isinstance(item, dict)})
        details = "Tools: " + (", ".join(tool_names) if tool_names else "none")
        text = f"✅ Aria finished a request.\n{details}\nSee trace for details."
        try:
            await self._app.client.chat_postMessage(channel=channel, text=text)
        except Exception as error:
            store.append_audit("slack_notification_failed", {"channel": channel, "error": str(error)})

    async def say(self, channel: str, text: str) -> None:
        if self._app:
            await self._app.client.chat_postMessage(channel=channel, text=text)
