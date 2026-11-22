from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from agent_core.storage import store


def trace_summary(window: str = "1h", records: list[dict] | None = None) -> str:
    if window.lower() == "today":
        now = datetime.now(UTC)
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "today (UTC)"
    else:
        match = re.fullmatch(r"(\d{1,5})(m|h|d)?", window.lower())
        if not match:
            return "Use /trace with 30m, 2h, 1d, or today."
        amount, unit = int(match.group(1)), match.group(2) or "h"
        minutes = amount * {"m": 1, "h": 60, "d": 1440}[unit]
        if amount < 1 or minutes > 10080:
            return "Trace window must be between 1 minute and 7 days."
        now = datetime.now(UTC)
        since = now - timedelta(minutes=minutes)
        label = f"last {window.lower()}"

    events = []
    for record in records if records is not None else store.read_audit(limit=500):
        try:
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        if timestamp >= since:
            events.append(record)

    completed = [item for item in events if _is_processed(item.get("event_type", ""))]
    completed_ids = {_request_id(item) for item in completed if _request_id(item)}
    started = [item for item in events if item.get("event_type") == "inbound_request_started"]
    active = [
        item for item in started
        if _request_id(item) and _request_id(item) not in completed_ids
    ]
    tools = [
        call.get("name", "tool")
        for item in completed
        for call in _result(item).get("used_tools", [])
        if isinstance(call, dict)
    ]
    specialists = [item for item in events if item.get("event_type") == "specialist_started"]
    review_results = [
        item for item in events
        if item.get("event_type") in {"task_tool_reviewed", "code_change_reviewed"}
    ]
    review_starts = [
        item for item in events
        if item.get("event_type") in {"task_tool_review_started", "code_change_review_started"}
    ]
    completed_reviews = {item.get("payload", {}).get("proposal_id") for item in review_results}
    active_reviews = [
        item for item in review_starts
        if item.get("payload", {}).get("proposal_id") not in completed_reviews
    ]
    file_writes = [item for item in events if item.get("event_type") == "workspace_file_written"]

    lines = [
        f"Aria activity · {label}",
        f"Requests completed: {len(completed)} · in progress: {len(active)} · "
        f"{len(tools)} tool calls · {len(specialists)} specialist runs · {len(review_results)} reviews "
        f"({len(active_reviews)} running) · "
        f"{len(file_writes)} file writes",
    ]
    for item in sorted(active, key=lambda row: row.get("ts", ""), reverse=True)[:3]:
        payload = item.get("payload", {})
        text = _short(payload.get("task", ""), 120)
        lines.append(f"⏳ {payload.get('channel', '?')} · {text or 'Request is processing'}")
    for item in completed[:5]:
        payload = item.get("payload", {})
        result = _result(item)
        event = result.get("event", {})
        text = _short(event.get("text", ""), 90)
        tool_names = [
            call.get("name", "tool") for call in result.get("used_tools", []) if isinstance(call, dict)
        ]
        model = result.get("selected_model", "model unavailable")
        files = result.get("file_changes", [])
        action = ", ".join(tool_names) if tool_names else (f"files: {', '.join(files)}" if files else "text response; no file action recorded")
        lines.append(f"✓ {payload.get('channel', '?')} · {text or 'Request'} · {model} · {action}")
        error = result.get("delivery_error") or result.get("error_message")
        if error:
            lines.append(f"  Delivery/processing issue: {_short(error, 180)}")
    for item in review_results[-3:]:
        payload = item.get("payload", {})
        lines.append(
            f"Review · {payload.get('name', 'code change')} · {payload.get('status', 'completed')} · "
            f"{_short(payload.get('summary', ''), 130)}"
        )
    for item in active_reviews[-3:]:
        payload = item.get("payload", {})
        lines.append(f"Review running · {payload.get('name', 'code change')} · {_short(payload.get('description', ''), 100)}")
    for item in file_writes[-3:]:
        payload = item.get("payload", {})
        lines.append(f"File saved · {_short(payload.get('path', ''), 120)}")
    if not completed and not active:
        lines.append("No requests recorded in this window.")
    return "\n".join(lines)[:3900]


def _is_processed(event_type: str) -> bool:
    return event_type.startswith("inbound_") and event_type.endswith("_processed")


def _result(record: dict) -> dict:
    payload = record.get("payload", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    return result if isinstance(result, dict) else {}


def _request_id(record: dict) -> str:
    payload = record.get("payload", {})
    if not isinstance(payload, dict):
        return ""
    result = _result(record)
    event = result.get("event", {})
    message_id = payload.get("message_id") or (event.get("message_id", "") if isinstance(event, dict) else "")
    if not message_id:
        return ""
    channel = payload.get("channel") or (event.get("channel", "") if isinstance(event, dict) else "")
    chat_id = payload.get("chat_id") or (event.get("chat_id", "") if isinstance(event, dict) else "")
    return f"{channel}:{chat_id}:{message_id}"


def _short(value: object, limit: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text[:limit] + ("…" if len(text) > limit else "")
