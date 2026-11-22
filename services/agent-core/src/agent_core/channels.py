from __future__ import annotations

from typing import Any

from agent_core.integrations import TelegramBotService, EmailGateway
from agent_core.integrations.whatsapp_gateway import WhatsAppGatewayClient


class ChannelManager:
    def __init__(
        self,
        telegram: TelegramBotService,
        slack: Any,
        discord: Any,
        email: EmailGateway,
    ) -> None:
        self._whatsapp = WhatsAppGatewayClient()
        self._telegram = telegram
        self._slack = slack
        self._discord = discord
        self._email = email

    async def send(self, channel: str, chat_id: str, text: str) -> None:
        if channel == "whatsapp":
            await self._whatsapp.send_message(chat_id, text)
            return

        if channel == "telegram":
            await self._telegram.send_message(chat_id, text)
            return

        if channel == "slack":
            if self._slack is None:
                raise RuntimeError("Slack SDK is not installed")
            await self._slack.send_message(chat_id, text)
            return

        if channel == "discord":
            if self._discord is None:
                raise RuntimeError("Discord SDK is not installed")
            await self._discord.send_message(chat_id, text)
            return

        if channel == "email":
            # Email sending would typically go through an SMTP service
            # For now, we'll log it
            return

        raise ValueError(f"Unsupported channel: {channel}")

