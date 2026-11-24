from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException

from agent_core.approvals import approval_store
from agent_core.commands import parse_command
from agent_core.config import settings
from agent_core.models import InboundEvent
from agent_core.policy import policy
from agent_core.storage import store


async def decide_approval(
    approval_id: str,
    decision: str,
    decided_by: str,
    send_message: Callable[[str, str, str], Awaitable[None]],
) -> dict:
    record = approval_store.decide(approval_id, decision, decided_by)
    store.append_audit("human_approval_decided", {
        "approval_id": record["id"], "action": record["action"],
        "decision": decision, "channel": decided_by.split(":", 1)[0],
    })
    if decision != "approved" or not record.get("parameters"):
        return record

    record = approval_store.claim_execution(record["id"])
    parameters = record["parameters"]
    try:
        if not settings.channel_enabled(parameters["channel"]):
            raise RuntimeError("Approved channel is disabled")
        await send_message(parameters["channel"], parameters["chat_id"], parameters["text"])
    except Exception as error:
        record = approval_store.finish_execution(record["id"], False, type(error).__name__)
        store.append_audit("approved_action_failed", {
            "approval_id": record["id"], "action": record["action"],
            "channel": parameters["channel"], "chat_id": parameters["chat_id"],
            "error_type": type(error).__name__,
        })
        return record

    record = approval_store.finish_execution(record["id"], True)
    store.append_audit("approved_action_executed", {
        "approval_id": record["id"], "action": record["action"],
        "channel": parameters["channel"], "chat_id": parameters["chat_id"],
    })
    return record


async def handle_whatsapp_approval_command(
    event: InboundEvent,
    send_message: Callable[[str, str, str], Awaitable[None]],
) -> str | None:
    parsed = parse_command(event.text)
    if not parsed or parsed[0] not in {"/approvals", "/approve", "/reject"}:
        return None
    if not _is_whatsapp_owner(event):
        return "Approval controls are available only in a configured owner private chat."

    command, argument = parsed
    if command == "/approvals":
        try:
            page = int(argument) if argument else 1
        except ValueError:
            return "Usage: /approvals [page]"
        if page < 1:
            return "Usage: /approvals [page]"
        pending = approval_store.list("pending")
        if not pending:
            return "No pending approvals."
        page_size = 2
        start = (page - 1) * page_size
        if start >= len(pending):
            return "No more pending approvals."
        entries = []
        for item in pending[start:start + page_size]:
            parameters = item.get("parameters")
            if item["action"] == "send_message" and isinstance(parameters, dict):
                description = (
                    f"Send via {parameters['channel']} to {parameters['chat_id']}\n"
                    f"Message: {parameters['text']}"
                )
            else:
                description = f"{item['action']}: {item['details']}\nApproval records a decision only."
            if len(description) > 1300:
                return (
                    f"Approval {item['id'][:8]} is too long to review safely in WhatsApp. "
                    "Inspect it through the authenticated admin API; no decision was made."
                )
            entries.append(
                f"{item['id'][:8]} — {item['summary']}\n{description}\n"
                f"Approve: /approve {item['id'][:8]} · Reject: /reject {item['id'][:8]}"
            )
        response = "Pending approvals\n\n" + "\n\n".join(entries)
        if start + page_size < len(pending):
            response += f"\n\nMore requests: /approvals {page + 1}"
        return response

    if not argument or len(argument.split()) != 1:
        return f"Usage: {command} APPROVAL_ID"
    decision = "approved" if command == "/approve" else "rejected"
    try:
        record = await decide_approval(
            argument, decision, f"whatsapp:{event.sender_id}", send_message
        )
    except HTTPException as error:
        if error.status_code == 404:
            return "Approval not found. Refresh /approvals and use its ID."
        if error.status_code == 409:
            return "Approval expired, already decided, or the short ID is ambiguous. Refresh /approvals."
        return "Could not process the approval safely."
    except Exception:
        return "Could not process the approval safely."

    if decision == "rejected":
        return f"Rejected: {record['summary']}. No action was sent."
    if record.get("execution_status") == "succeeded":
        return f"Approved and sent via {record['parameters']['channel']}."
    if record.get("execution_status") == "failed":
        return "Approval recorded, but message delivery failed. No automatic retry was made."
    return f"Approved: {record['summary']}. This request has no executable action attached."


def _is_whatsapp_owner(event: InboundEvent) -> bool:
    whatsapp_policy = policy.load().get("whatsapp", {})
    if (
        not whatsapp_policy.get("enabled", True)
        or event.chat_id in set(whatsapp_policy.get("blocked_chat_ids", []))
        or (
            whatsapp_policy.get("allowlist_managed")
            and event.chat_id not in set(whatsapp_policy.get("allowed_chat_ids", []))
        )
        or (
            not whatsapp_policy.get("allowlist_managed")
            and whatsapp_policy.get("allowed_chat_ids")
            and event.chat_id not in set(whatsapp_policy["allowed_chat_ids"])
        )
    ):
        return False
    return bool(
        event.channel == "whatsapp"
        and not event.is_group
        and event.sender_id == event.chat_id
        and event.chat_id in settings.allowed_whatsapp_owner_chat_ids
    )
