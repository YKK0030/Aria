from datetime import UTC, datetime
import re
import time

from agent_core.channels import ChannelManager
from agent_core.integrations import (
    TelegramBotService,
    EmailGateway,
)
try:
    from agent_core.integrations.slack_bot import SlackBotService
except ModuleNotFoundError as error:
    if error.name != "slack_bolt":
        raise
    SlackBotService = None
try:
    from agent_core.integrations.discord_bot import DiscordBotService
except ModuleNotFoundError as error:
    if error.name != "discord":
        raise
    DiscordBotService = None
from agent_core.memory import long_term_memory, short_term_memory
from agent_core.models import (
    InboundEvent,
    TelegramInboundEvent,
    SlackInboundEvent,
    DiscordInboundEvent,
    EmailInboundEvent,
)
from agent_core.runtime import AgentRuntime
from agent_core.storage import store

_CODE_FENCE = re.compile(r"```[^\n]*\n.*?(?:```|$)", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_RAW_CODE = re.compile(
    r"(?im)^\s*(?:<!doctype html|<html\b|<script\b|(?:async\s+)?def\s+\w+\s*\(|"
    r"class\s+\w+\s*[:(]|(?:from\s+\S+\s+)?import\s+\w+|"
    r"(?:const|let|var)\s+\w+\s*=|function\s+\w+\s*\(|#include\s*[<\"]|#!/(?:usr/)?bin/)"
)


class AgentOrchestrator:
    def __init__(self) -> None:
        self._runtime = AgentRuntime()
        self.telegram = TelegramBotService(self.process_telegram_event)
        self.slack = SlackBotService(self.process_slack_event) if SlackBotService else None
        self.discord = DiscordBotService(self.process_discord_event) if DiscordBotService else None
        self.email = EmailGateway(self.process_email_event)
        self.channels = ChannelManager(self.telegram, self.slack, self.discord, self.email)

    async def process_whatsapp_event(self, event: InboundEvent) -> dict:
        return await self._process_event(event, "whatsapp")

    async def process_telegram_event(self, event: TelegramInboundEvent) -> dict:
        return await self._process_event(event, "telegram")

    async def process_slack_event(self, event: SlackInboundEvent) -> dict:
        return await self._process_event(event, "slack")

    async def process_discord_event(self, event: DiscordInboundEvent) -> dict:
        return await self._process_event(event, "discord")

    async def process_email_event(self, event: EmailInboundEvent) -> dict:
        return await self._process_event(event, "email")

    async def process_mcp_event(self, event: TelegramInboundEvent) -> dict:
        return await self._process_event(event, "mcp", deliver=False)

    async def process_local_event(self, event: InboundEvent) -> dict:
        if event.channel not in {"cli", "web"}:
            raise ValueError("Local event must use the cli or web channel")
        return await self._process_event(event, event.channel, deliver=False)

    async def send_manual_message(self, channel: str, chat_id: str, text: str) -> None:
        await self.channels.send(channel, chat_id, text)
        self._persist_outbound(channel, chat_id, text)
        await self._safe_append_short_term_message(channel, chat_id, "assistant", text)
        self._safe_add_long_term_node(channel, chat_id, "assistant", text)
        store.append_audit("manual_message_sent", {"channel": channel, "chat_id": chat_id, "text": text})

    def get_history(self, channel: str, chat_id: str, limit: int | None = None) -> list[dict]:
        return store.read_history(channel, chat_id, limit)

    async def _process_event(
        self,
        event: InboundEvent | TelegramInboundEvent,
        source: str,
        *,
        deliver: bool = True,
    ) -> dict:
        if store.is_duplicate_message(event.channel, event.chat_id, event.message_id):
            self._safe_audit(
                f"duplicate_{source}_message_ignored",
                {"chat_id": event.chat_id, "message_id": event.message_id},
            )
            return {"should_reply": False, "duplicate": True}

        store.mark_message_processed(event.channel, event.chat_id, event.message_id)

        self._safe_audit("inbound_request_started", {
            "channel": event.channel,
            "chat_id": event.chat_id,
            "message_id": event.message_id,
            "task": event.text[:500],
        })

        runtime_started = time.perf_counter()
        try:
            result = await self._runtime.run(event)
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
        self._finalize_workspace_response(event.text, result)
        runtime_duration_ms = round((time.perf_counter() - runtime_started) * 1000)

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
                if deliver:
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

        self._safe_audit(
            f"inbound_{source}_processed",
            {"channel": event.channel, "chat_id": event.chat_id, "message_id": event.message_id,
             "duration_ms": runtime_duration_ms, "result": result},
        )
        if self.telegram is not None and source != "telegram" and result.get("should_reply") and result.get("response_text"):
            await self.telegram.notify_completion(source, result.get("used_tools", []))
        if self.slack is not None and source != "slack" and result.get("should_reply") and result.get("response_text"):
            await self.slack.notify_completion(source, result.get("used_tools", []))
        if self.discord is not None and source != "discord" and result.get("should_reply") and result.get("response_text"):
            await self.discord.notify_completion(source, result.get("used_tools", []))
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
            safe_text = self._memory_safe_text(text)
            if safe_text:
                await short_term_memory.append_message(channel, chat_id, role, safe_text)
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
            safe_text = self._memory_safe_text(text)
            if safe_text:
                return long_term_memory.add_node(channel, chat_id, role, safe_text, source_message_id)
        except Exception:
            return None
        return None

    @staticmethod
    def _memory_safe_text(text: str) -> str:
        safe = _CODE_FENCE.sub("[code omitted from memory]", text)
        safe = _INLINE_CODE.sub("", safe)
        if _RAW_CODE.search(safe):
            return "[code omitted from memory]"
        return safe.strip()

    @staticmethod
    def _finalize_workspace_response(request_text: str, result: dict) -> None:
        lower = request_text.lower()
        create_request = any(word in lower for word in ("create", "build", "make", "write", "generate"))
        file_request = any(word in lower for word in ("html", "web page", "website", "folder", "file", "project"))
        if not (create_request and file_request):
            return
        calls = result.get("used_tools") or []
        writes = [
            call for call in calls
            if isinstance(call, dict) and call.get("name") == "write_workspace_file"
        ]
        if writes:
            paths = [
                call.get("args", {}).get("path")
                for call in writes
                if isinstance(call.get("args", {}), dict) and call.get("args", {}).get("path")
            ]
            if paths:
                result["file_changes"] = paths
                result["used_tools"] = [{"name": call.get("name")} for call in calls if isinstance(call, dict)]
                result["response_text"] = (
                    "Done — created " + ", ".join(paths)
                    + " in Aria’s workspace. Source is saved locally; I’m not pasting it into chat."
                )
                return
        result["used_tools"] = [{"name": call.get("name")} for call in calls if isinstance(call, dict)]
        result["response_text"] = "I didn’t save any files for that request. No workspace write was recorded, so nothing was changed."
