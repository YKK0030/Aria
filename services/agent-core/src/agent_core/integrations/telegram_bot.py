from __future__ import annotations

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from agent_core.config import settings
from agent_core.models import TelegramInboundEvent


class TelegramBotService:
    def __init__(self, event_callback):
        self._event_callback = event_callback
        self._app: Application | None = None

    async def start(self) -> None:
        if not settings.telegram_bot_token:
            return

        self._app = Application.builder().token(settings.telegram_bot_token).build()
        self._app.add_handler(MessageHandler(filters.TEXT, self._on_text))
        await self._app.initialize()
        await self._app.start()
        if self._app.updater:
            await self._app.updater.start_polling()

    async def stop(self) -> None:
        if not self._app:
            return
        if self._app.updater:
            await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()

    async def send_message(self, chat_id: str, text: str) -> None:
        if not self._app:
            raise RuntimeError("Telegram bot is not started or TELEGRAM_BOT_TOKEN is missing")
        await self._app.bot.send_message(chat_id=int(chat_id), text=text)

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context

        if not update.effective_chat or not update.effective_user or not update.effective_message:
            return

        allowed_ids = settings.allowed_telegram_chat_ids
        if allowed_ids and update.effective_chat.id not in allowed_ids:
            return

        text = update.effective_message.text or ""
        if not text.strip():
            return

        event = TelegramInboundEvent(
            chat_id=str(update.effective_chat.id),
            sender_id=str(update.effective_user.id),
            push_name=update.effective_user.full_name,
            group_name=update.effective_chat.title,
            is_group=update.effective_chat.type in {"group", "supergroup"},
            message_id=str(update.effective_message.message_id),
            text=text,
            timestamp=int(update.effective_message.date.timestamp()),
        )
        await self._event_callback(event)
