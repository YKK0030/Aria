from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent_core.approvals import approval_store
from agent_core.config import settings
from agent_core.models import TelegramInboundEvent
from agent_core.policy import policy
from agent_core.storage import store
from agent_core.tracing import trace_summary
from agent_core.tooling.proposals import tool_proposals
from agent_core.tooling.reviewer import ToolReviewUnavailable, review_tool

logger = logging.getLogger(__name__)


class TelegramBotService:
    def __init__(self, event_callback):
        self._event_callback = event_callback
        self._app: Application | None = None

    async def start(self) -> None:
        if not settings.channel_enabled("telegram"):
            return
        if not settings.telegram_bot_token:
            logger.error("Telegram is enabled but TELEGRAM_BOT_TOKEN is missing; bot polling was not started")
            return
        if not settings.allowed_telegram_chat_ids:
            logger.error(
                "Telegram is enabled but TELEGRAM_ALLOWED_CHAT_IDS is empty; bot polling was not started. "
                "Set your private Telegram chat ID to enable access."
            )
            return

        self._app = Application.builder().token(settings.telegram_bot_token).build()
        self._app.add_handler(CommandHandler(
            ["help", "status", "tools", "pending", "review", "approve", "approvals", "trace"], self._on_command
        ))
        self._app.add_handler(CallbackQueryHandler(
            self._on_approval,
            pattern=r"^(?:tool_(?:approve|cancel)|action_(?:approve|reject)):[0-9a-f-]{36}$",
        ))
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

    async def notify_completion(self, channel: str, tool_calls: list[dict]) -> None:
        if not self._app:
            return
        tool_names = sorted({str(item.get("name", "tool")) for item in tool_calls if isinstance(item, dict)})
        details = "Tools: " + (", ".join(tool_names) if tool_names else "none")
        text = f"✅ Aria finished a request from {channel}.\n{details}\nSee /trace 1h for recent activity."
        for chat_id in sorted(settings.allowed_telegram_chat_ids):
            try:
                await self.send_message(str(chat_id), text)
            except Exception as error:
                store.append_audit("telegram_task_notification_failed", {
                    "channel": channel, "chat_id": str(chat_id), "error": type(error).__name__,
                })

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if not update.effective_chat or not update.effective_user or not update.effective_message:
            return

        allowed_ids = settings.allowed_telegram_chat_ids
        telegram_policy = policy.load().get("telegram", {})
        if telegram_policy.get("allowlist_managed"):
            allowed_chat_ids = set(telegram_policy.get("allowed_chat_ids", []))
            is_allowed = str(update.effective_chat.id) in allowed_chat_ids
        else:
            is_allowed = bool(allowed_ids) and update.effective_chat.id in allowed_ids
        if not is_allowed:
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

    async def _on_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if not message:
            return
        if not self._is_authorized_owner(update):
            await message.reply_text("Admin commands work only in your allowlisted direct chat with Aria.")
            return

        command = (message.text or "").split()[0].split("@", 1)[0].lower().lstrip("/")
        if command == "help":
            await message.reply_text(
                "Aria Telegram controls\n"
                "/status — runtime and enabled channels\n"
                "/tools — installed tools\n"
                "/pending — tool drafts and review status\n"
                "/review NAME — run reviewer after isolated tests pass\n"
                "/approve NAME — confirm installation of a reviewed tool\n"
                "/approvals — review pending sensitive-action requests\n"
                "/trace [30m|2h|1d|today] — requests, agents, tools, and reviews"
            )
        elif command == "status":
            await message.reply_text(
                f"{settings.agent_name} is online.\nProvider: {settings.model_provider}\n"
                f"Channels: {', '.join(sorted(settings.enabled_channels))}\n"
                f"Short memory: {'on' if settings.redis_enabled else 'off'} · Long memory: SQLite graph"
            )
        elif command == "tools":
            from agent_core.tooling import dynamic_tool_registry

            tools = [item for item in dynamic_tool_registry.list_tool_specs() if item.get("available")]
            await message.reply_text("Installed tools:\n" + ("\n".join(f"• {item['name']}" for item in tools) or "None"))
        elif command == "pending":
            proposals = [item for item in tool_proposals.list() if item.get("status") != "approved"]
            body = "\n".join(f"• {item['name']} — {item['status']}" for item in proposals)
            await message.reply_text("Tool drafts:\n" + (body or "No uninstalled tool drafts."))
        elif command == "review":
            await self._review_proposal(update, context.args)
        elif command == "approve":
            await self._request_approval(update, context.args)
        elif command == "approvals":
            await self._list_action_approvals(update)
        elif command == "trace":
            await message.reply_text(self._trace_summary(context.args[0] if context.args else "1h"))

    async def _review_proposal(self, update: Update, args: list[str]) -> None:
        message = update.effective_message
        if not message:
            return
        proposal = self._proposal_named(" ".join(args)) if args else None
        if not proposal:
            await message.reply_text("Use /review TOOL_NAME. See /pending for draft names.")
            return
        if proposal["status"] == "reviewed":
            await message.reply_text(f"{proposal['name']} passed review. Use /approve {proposal['name']} to install it.")
            return
        if proposal["status"] != "tested" or proposal.get("tested_sha256") != proposal["sha256"]:
            await message.reply_text(
                f"{proposal['name']} is {proposal['status']}. Run its isolated tests from the Aria CLI first; "
                "Telegram cannot start the host Docker sandbox."
            )
            return

        test_count = proposal.get("test_count", 0)
        if test_count != len(proposal["tests"]):
            await message.reply_text("Test record is incomplete or stale. Re-run the isolated tests first.")
            return
        await message.reply_text(f"Independent review started for {proposal['name']}…")
        started = datetime.now(UTC)
        reviewer_model = (
            settings.ollama_model if settings.model_provider == "ollama"
            else settings.nvidia_super_model if settings.model_provider == "nvidia"
            else settings.groq_complex_model
        )
        store.append_audit("task_tool_review_started", {
            "proposal_id": proposal["id"], "name": proposal["name"], "model": reviewer_model,
            "description": proposal.get("description", ""), "channel": "telegram",
        })
        try:
            review = await review_tool(proposal, test_count)
        except ToolReviewUnavailable as error:
            store.append_audit("task_tool_review_failed", {
                "proposal_id": proposal["id"], "name": proposal["name"], "error": str(error),
            })
            await message.reply_text(f"Review failed; draft remains inactive. {error}")
            return
        reviewed = tool_proposals.record_review(
            proposal["id"], proposal["sha256"], test_count, review.model_dump()
        )
        store.append_audit("task_tool_reviewed", {
            "proposal_id": proposal["id"], "name": proposal["name"], "status": reviewed["status"],
            "model": reviewer_model, "description": proposal.get("description", ""),
            "summary": review.summary, "findings": review.findings,
            "duration_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
        })
        outcome = "Ready for your approval with /approve " + proposal["name"] if reviewed["status"] == "reviewed" else "Needs changes; it was not installed."
        findings = "\n".join(f"• {item}" for item in review.findings)
        await message.reply_text(f"Review: {review.summary}\n{outcome}" + (f"\n{findings}" if findings else ""))

    async def _request_approval(self, update: Update, args: list[str]) -> None:
        message = update.effective_message
        if not message:
            return
        proposal = self._proposal_named(" ".join(args)) if args else None
        if not proposal:
            await message.reply_text("Use /approve TOOL_NAME. See /pending for draft names.")
            return
        if proposal["status"] != "reviewed" or proposal.get("reviewed_sha256") != proposal.get("sha256"):
            await message.reply_text(
                f"{proposal['name']} is {proposal['status']}. It must pass isolated tests and independent review first."
            )
            return
        source = proposal["source"]
        summary = (
            f"Install {proposal['name']}?\n{proposal['description']}\n"
            f"Review: {proposal.get('review', {}).get('summary', 'passed')}\n"
            f"Tests passed: {proposal.get('test_count', 0)}\n\nSource:\n{source}"
        )
        if len(summary) > 3800:
            await message.reply_text("This proposal is too large to inspect safely in Telegram. Review and approve it from the local CLI.")
            return
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Approve & install", callback_data=f"tool_approve:{proposal['id']}"),
            InlineKeyboardButton("Cancel", callback_data=f"tool_cancel:{proposal['id']}"),
        ]])
        await message.reply_text(summary, reply_markup=keyboard)

    async def _on_approval(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        query = update.callback_query
        if not query:
            return
        if not self._is_authorized_owner(update):
            await query.answer("Owner approval is allowed only in your approved direct chat.", show_alert=True)
            return
        await query.answer()
        action, proposal_id = query.data.split(":", 1)
        if action in {"action_approve", "action_reject"}:
            decision = "approved" if action == "action_approve" else "rejected"
            try:
                approval = approval_store.decide(proposal_id, decision, f"telegram:{update.effective_user.id}")
            except Exception as error:
                await query.edit_message_text(f"Could not record the decision. {error}")
                return
            store.append_audit("human_approval_decided", {
                "approval_id": proposal_id, "action": approval["action"],
                "decision": decision, "channel": "telegram",
            })
            await query.edit_message_text(
                f"Request {approval['summary']} {decision}. This records owner approval only; no action was executed."
            )
            return
        if action == "tool_cancel":
            await query.edit_message_text("Approval cancelled; the tool remains inactive.")
            return
        try:
            proposal = tool_proposals.get(proposal_id)
            if proposal["status"] != "reviewed" or proposal.get("reviewed_sha256") != proposal.get("sha256"):
                await query.edit_message_text("This draft changed or is no longer review-approved. Nothing was installed.")
                return
            installed = tool_proposals.approve(proposal_id)
        except Exception as error:
            await query.edit_message_text(f"Could not install the tool. Nothing was approved. {error}")
            return
        store.append_audit("task_tool_approved", {
            "proposal_id": proposal_id, "name": installed["name"], "channel": "telegram",
        })
        await query.edit_message_text(
            f"Approved and installed {installed['name']}. Aria can use it on her next request."
        )

    async def _list_action_approvals(self, update: Update) -> None:
        message = update.effective_message
        if not message:
            return
        pending = approval_store.list("pending")[:10]
        if not pending:
            await message.reply_text("No pending sensitive-action requests.")
            return
        for item in pending:
            if len(item["details"]) > 3500:
                await message.reply_text(
                    f"{item['action']}: {item['summary']}\n"
                    "Details are too long to review safely in Telegram. Inspect the full request and decide "
                    "through the authenticated admin approvals API. No decision was made."
                )
                continue
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("Approve", callback_data=f"action_approve:{item['id']}"),
                InlineKeyboardButton("Reject", callback_data=f"action_reject:{item['id']}"),
            ]])
            await message.reply_text(
                f"Sensitive action request\n{item['action']}: {item['summary']}\n\n"
                f"Details: {item['details']}\nRequested via: {item['requested_by']['channel']}\n"
                "Approval records authorization only; it does not run the action.",
                reply_markup=keyboard,
            )

    def _is_authorized_owner(self, update: Update) -> bool:
        chat, user = update.effective_chat, update.effective_user
        allowed_ids = settings.allowed_telegram_chat_ids
        return bool(
            chat and user and chat.type == "private" and allowed_ids
            and chat.id in allowed_ids and user.id in allowed_ids
        )

    @staticmethod
    def _proposal_named(name: str) -> dict | None:
        selector = name.strip().lower()
        matches = [item for item in tool_proposals.list() if item["name"] == selector]
        if not matches:
            return None
        selected = max(matches, key=lambda item: item.get("created_at", ""))
        return tool_proposals.get(selected["id"])

    @staticmethod
    def _trace_summary(window: str) -> str:
        return trace_summary(window)
