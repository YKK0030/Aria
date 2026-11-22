from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import discord
from discord.ext import commands

from agent_core.config import settings
from agent_core.models import DiscordInboundEvent
from agent_core.storage import store

logger = logging.getLogger(__name__)


class DiscordBotService:
    def __init__(self, event_callback):
        self._event_callback = event_callback
        self._bot: commands.Bot | None = None

    async def start(self) -> None:
        if not settings.channel_enabled("discord"):
            return
        if not settings.discord_bot_token:
            logger.error("Discord is enabled but DISCORD_BOT_TOKEN is missing")
            return

        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True

        self._bot = commands.Bot(command_prefix="/aria ", intents=intents, help_command=None)
        self._register_handlers()

        await self._bot.start(settings.discord_bot_token)

    async def stop(self) -> None:
        if self._bot:
            await self._bot.close()

    async def send_message(self, channel_id: str, text: str) -> None:
        if not self._bot:
            raise RuntimeError("Discord bot is not started")
        channel = self._bot.get_channel(int(channel_id))
        if channel:
            await channel.send(text)

    def _register_handlers(self) -> None:
        @self._bot.event
        async def on_ready():
            logger.info(f"Discord bot connected as {self._bot.user}")

        @self._bot.event
        async def on_message(message: discord.Message):
            if message.author.bot or not message.content:
                return

            allowed_channels = set(settings.allowed_discord_channels or [])
            if allowed_channels and str(message.channel.id) not in allowed_channels:
                return

            event = DiscordInboundEvent(
                channel_id=str(message.channel.id),
                sender_id=str(message.author.id),
                push_name=message.author.display_name,
                group_name=message.guild.name if message.guild else "DM",
                is_group=message.guild is not None,
                message_id=str(message.id),
                text=message.content,
                timestamp=int(message.created_at.timestamp()),
            )
            await self._event_callback(event)

        @self._bot.command(name="status")
        async def status(ctx: commands.Context):
            await ctx.send(
                f"{settings.agent_name} is online.\n"
                f"Provider: {settings.model_provider}\n"
                f"Channels: {', '.join(sorted(settings.enabled_channels))}"
            )

    async def notify_completion(self, channel_id: str, tool_calls: list[dict]) -> None:
        if not self._bot:
            return
        tool_names = sorted({str(item.get("name", "tool")) for item in tool_calls if isinstance(item, dict)})
        details = "Tools: " + (", ".join(tool_names) if tool_names else "none")
        text = f"✅ Aria finished a request.\n{details}"
        channel = self._bot.get_channel(int(channel_id))
        if channel:
            try:
                await channel.send(text)
            except Exception as error:
                store.append_audit("discord_notification_failed", {"channel_id": channel_id, "error": str(error)})
