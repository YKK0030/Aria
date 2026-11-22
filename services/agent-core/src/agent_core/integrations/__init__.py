from agent_core.integrations.telegram_bot import TelegramBotService
from agent_core.integrations.whatsapp_gateway import WhatsAppGatewayClient as WhatsAppGateway
from agent_core.integrations.email_gateway import EmailGateway

__all__ = [
    "TelegramBotService",
    "WhatsAppGateway",
    "EmailGateway",
]
