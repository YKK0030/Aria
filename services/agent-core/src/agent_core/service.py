from datetime import UTC, datetime

from agent_core.channels import ChannelManager
from agent_core.graph import build_graph
from agent_core.integrations.telegram_bot import TelegramBotService
from agent_core.memory import long_term_memory, short_term_memory
from agent_core.models import InboundEvent, TelegramInboundEvent
from agent_core.storage import store


class AgentOrchestrator:
    def __init__(self) -> None:
        self._graph = build_graph()
        self.telegram = TelegramBotService(self.process_telegram_event)
        self.channels = ChannelManager(self.telegram)

    async def process_whatsapp_event(self, event: InboundEvent) -> dict:
        return await self._process_event(event, "whatsapp")

    async def process_telegram_event(self, event: TelegramInboundEvent) -> dict:
        return await self._process_event(event, "telegram")

    async def send_manual_message(self, channel: str, chat_id: str, text: str) -> None:
        await self.channels.send(channel, chat_id, text)
        self._persist_outbound(channel, chat_id, text)
        await self._safe_append_short_term_message(channel, chat_id, "assistant", text)
        self._safe_add_long_term_node(channel, chat_id, "assistant", text)
        store.append_audit("manual_message_sent", {"channel": channel, "chat_id": chat_id, "text": text})

    def get_history(self, channel: str, chat_id: str, limit: int | None = None) -> list[dict]:
        return store.read_history(channel, chat_id, limit)

    async def _process_event(self, event: InboundEvent | TelegramInboundEvent, source: str) -> dict:
        if store.is_duplicate_message(event.channel, event.chat_id, event.message_id):
            self._safe_audit(
                f"duplicate_{source}_message_ignored",
                {"chat_id": event.chat_id, "message_id": event.message_id},
            )
            return {"should_reply": False, "duplicate": True}

        store.mark_message_processed(event.channel, event.chat_id, event.message_id)

        try:
            result = await self._graph.ainvoke({"event": event})
        except Exception as error:
            result = {
                "should_reply": True,
                "selected_model": "fallback",
                "response_text": (
                    "I hit an internal processing issue, but I am still online. "
                    "Please retry in a moment, or use /help for built-in commands."
                ),
                "error_message": str(error),
            }

        self._safe_persist_inbound(event.channel, event.chat_id, event.sender_id, event.text)
        await self._safe_append_short_term_message(event.channel, event.chat_id, "user", event.text)
        inbound_node_id = self._safe_add_long_term_node(
            event.channel,
            event.chat_id,
            "user",
            event.text,
            event.message_id,
        )

        if result.get("should_reply") and result.get("response_text"):
            try:
                await self.channels.send(event.channel, event.chat_id, result["response_text"])
                self._safe_persist_outbound(event.channel, event.chat_id, result["response_text"])
                await self._safe_append_short_term_message(
                    event.channel,
                    event.chat_id,
                    "assistant",
                    result["response_text"],
                )
                outbound_node_id = self._safe_add_long_term_node(
                    event.channel,
                    event.chat_id,
                    "assistant",
                    result["response_text"],
                )
                if inbound_node_id and outbound_node_id:
                    long_term_memory.add_edge(inbound_node_id, outbound_node_id, "response", 1.0)
            except Exception as error:
                result["delivery_error"] = str(error)
                self._safe_audit(
                    f"{source}_delivery_failed",
                    {"chat_id": event.chat_id, "channel": event.channel, "error": str(error)},
                )

        self._safe_audit(f"inbound_{source}_processed", {"chat_id": event.chat_id, "result": result})
        return result

    @staticmethod
    def _persist_inbound(channel: str, chat_id: str, sender_id: str, text: str) -> None:
        store.append_history(
            channel,
            chat_id,
            {
                "ts": datetime.now(UTC).isoformat(),
                "direction": "inbound",
                "sender_id": sender_id,
                "text": text,
            },
        )

    @staticmethod
    def _persist_outbound(channel: str, chat_id: str, text: str) -> None:
        store.append_history(
            channel,
            chat_id,
            {
                "ts": datetime.now(UTC).isoformat(),
                "direction": "outbound",
                "text": text,
            },
        )

    def _safe_persist_inbound(self, channel: str, chat_id: str, sender_id: str, text: str) -> None:
        try:
            self._persist_inbound(channel, chat_id, sender_id, text)
        except Exception:
            return

    def _safe_persist_outbound(self, channel: str, chat_id: str, text: str) -> None:
        try:
            self._persist_outbound(channel, chat_id, text)
        except Exception:
            return

    def _safe_audit(self, event_type: str, payload: dict) -> None:
        try:
            store.append_audit(event_type, payload)
        except Exception:
            return

    async def _safe_append_short_term_message(self, channel: str, chat_id: str, role: str, text: str) -> None:
        try:
            await short_term_memory.append_message(channel, chat_id, role, text)
        except Exception:
            return

    def _safe_add_long_term_node(
        self,
        channel: str,
        chat_id: str,
        role: str,
        text: str,
        source_message_id: str | None = None,
    ) -> int | None:
        try:
            return long_term_memory.add_node(channel, chat_id, role, text, source_message_id)
        except Exception:
            return None
