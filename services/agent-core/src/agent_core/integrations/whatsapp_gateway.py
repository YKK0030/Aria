import httpx

from agent_core.config import settings


class WhatsAppGatewayClient:
    def __init__(self) -> None:
        self._base_url = settings.whatsapp_gateway_url.rstrip("/")
        self._headers = {
            "x-api-key": settings.whatsapp_gateway_api_key,
            "Content-Type": "application/json",
        }

    async def send_message(self, chat_id: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self._base_url}/messages/send",
                headers=self._headers,
                json={"to": chat_id, "text": text},
            )
            response.raise_for_status()

    async def mark_read(self, chat_id: str, message_id: str, participant: str | None = None) -> None:
        payload: dict[str, str] = {
            "chatId": chat_id,
            "messageId": message_id,
        }
        if participant:
            payload["participant"] = participant

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self._base_url}/messages/read",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()

