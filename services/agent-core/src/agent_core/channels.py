from __future__ import annotations

from agent_core.integrations.telegram_bot import TelegramBotService
from agent_core.integrations.whatsapp_gateway import WhatsAppGatewayClient


class ChannelManager:
    def __init__(self, telegram: TelegramBotService) -> None:
        self._whatsapp = WhatsAppGatewayClient()
        self._telegram = telegram

    async def send(self, channel: str, chat_id: str, text: str) -> None:
        if channel == "whatsapp":
            await self._whatsapp.send_message(chat_id, text)
            return

        if channel == "telegram":
            await self._telegram.send_message(chat_id, text)
            return

        raise ValueError(f"Unsupported channel: {channel}")

