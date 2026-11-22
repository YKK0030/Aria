from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from agent_core.config import settings
from agent_core.goals import goal_manager
from agent_core.storage import store

logger = logging.getLogger(__name__)


@dataclass
class WebhookTrigger:
    id: str
    name: str
    channel: str
    chat_id: str
    source: str  # "github", "gitlab", "calendar", "generic", "rss"
    events: list[str]  # e.g., ["push", "pull_request", "issue_created"]
    secret: str | None = None
    filter_config: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_triggered: str | None = None
    trigger_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "channel": self.channel,
            "chat_id": self.chat_id,
            "source": self.source,
            "events": self.events,
            "secret": "***" if self.secret else None,
            "filter_config": self.filter_config,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
        }


class TriggerManager:
    def __init__(self) -> None:
        self.triggers_dir = Path(settings.resolved_agent_data_dir) / "triggers"
        self.triggers_dir.mkdir(parents=True, exist_ok=True)
        self._handlers: dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._handlers["github"] = self._handle_github
        self._handlers["gitlab"] = self._handle_gitlab
        self._handlers["calendar"] = self._handle_calendar
        self._handlers["generic"] = self._handle_generic
        self._handlers["rss"] = self._handle_rss

    def _trigger_path(self, trigger_id: str) -> Path:
        return self.triggers_dir / f"{trigger_id}.json"

    def _index_path(self, channel: str, chat_id: str) -> Path:
        safe_chat = "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in chat_id)
        return self.triggers_dir / f"{channel}_{safe_chat}_index.json"

    def create_trigger(
        self,
        channel: str,
        chat_id: str,
        name: str,
        source: str,
        events: list[str],
        secret: str | None = None,
        filter_config: dict[str, Any] | None = None,
    ) -> WebhookTrigger:
        import uuid
        trigger = WebhookTrigger(
            id=uuid.uuid4().hex[:12],
            name=name,
            channel=channel,
            chat_id=chat_id,
            source=source,
            events=events,
            secret=secret,
            filter_config=filter_config or {},
        )
        self._save_trigger(trigger)
        self._update_index(channel, chat_id, trigger.id, "add")
        store.append_audit("trigger_created", {"trigger": trigger.to_dict()})
        return trigger

    def get_trigger(self, trigger_id: str) -> WebhookTrigger | None:
        for path in self.triggers_dir.glob("*.json"):
            if path.name.endswith("_index.json"):
                continue
            try:
                data = json.loads(path.read_text())
                if data.get("id") == trigger_id:
                    return WebhookTrigger(**data)
            except Exception:
                continue
        return None

    def list_triggers(self, channel: str, chat_id: str, active_only: bool = True) -> list[WebhookTrigger]:
        index_path = self._index_path(channel, chat_id)
        if not index_path.exists():
            return []
        try:
            index = json.loads(index_path.read_text())
            trigger_ids = index.get("triggers", [])
            triggers = []
            for tid in trigger_ids:
                t = self.get_trigger(tid)
                if t and (not active_only or t.is_active):
                    triggers.append(t)
            return triggers
        except Exception:
            return []

    def update_trigger(self, trigger_id: str, **kwargs) -> WebhookTrigger | None:
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return None
        for key, value in kwargs.items():
            if hasattr(trigger, key):
                setattr(trigger, key, value)
        self._save_trigger(trigger)
        return trigger

    def delete_trigger(self, trigger_id: str) -> bool:
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return False
        path = self._trigger_path(trigger_id)
        if path.exists():
            path.unlink()
        self._update_index(trigger.channel, trigger.chat_id, trigger_id, "remove")
        store.append_audit("trigger_deleted", {"trigger_id": trigger_id})
        return True

    def verify_signature(self, trigger: WebhookTrigger, payload: bytes, signature_header: str) -> bool:
        if not trigger.secret:
            return True  # No secret configured, accept
        try:
            # GitHub style: sha256=<hash>
            if signature_header.startswith("sha256="):
                expected = signature_header[7:]
            else:
                expected = signature_header
            computed = hmac.new(trigger.secret.encode(), payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(computed, expected)
        except Exception:
            return False

    async def process_webhook(self, trigger_id: str, payload: dict, headers: dict) -> dict[str, Any]:
        trigger = self.get_trigger(trigger_id)
        if not trigger or not trigger.is_active:
            return {"ok": False, "reason": "Trigger not found or inactive"}

        # Verify signature
        sig = headers.get("x-hub-signature-256") or headers.get("x-gitlab-token") or headers.get("x-signature")
        if sig and not self.verify_signature(trigger, json.dumps(payload).encode(), sig):
            return {"ok": False, "reason": "Invalid signature"}

        # Check event type
        event_type = headers.get("x-github-event") or headers.get("x-gitlab-event") or payload.get("event_type", "unknown")
        if trigger.events and event_type not in trigger.events:
            return {"ok": True, "ignored": True, "reason": f"Event {event_type} not in subscribed events"}

        # Apply filters
        if not self._matches_filters(trigger, payload):
            return {"ok": True, "ignored": True, "reason": "Failed filters"}

        # Process with handler
        handler = self._handlers.get(trigger.source, self._handle_generic)
        try:
            result = await handler(trigger, payload, event_type)

            # Update trigger stats
            trigger.last_triggered = datetime.now(UTC).isoformat()
            trigger.trigger_count += 1
            self._save_trigger(trigger)

            store.append_audit("trigger_fired", {
                "trigger_id": trigger_id,
                "event_type": event_type,
                "result": result,
            })
            return {"ok": True, "result": result}
        except Exception as e:
            logger.error("Trigger handler failed: %s", e)
            return {"ok": False, "reason": str(e)}

    def _matches_filters(self, trigger: WebhookTrigger, payload: dict) -> bool:
        filters = trigger.filter_config
        if not filters:
            return True

        # Repo filter
        if "repo" in filters:
            repo_name = payload.get("repository", {}).get("full_name") or payload.get("project", {}).get("path_with_namespace")
            if repo_name != filters["repo"]:
                return False

        # Branch filter
        if "branch" in filters:
            ref = payload.get("ref", "")
            branch = ref.replace("refs/heads/", "")
            if branch != filters["branch"]:
                return False

        # Author filter
        if "author" in filters:
            author = payload.get("sender", {}).get("login") or payload.get("user", {}).get("username")
            if author != filters["author"]:
                return False

        return True

    async def _handle_github(self, trigger: WebhookTrigger, payload: dict, event_type: str) -> dict[str, Any]:
        repo = payload.get("repository", {}).get("full_name", "unknown")
        sender = payload.get("sender", {}).get("login", "unknown")

        if event_type == "push":
            commits = payload.get("commits", [])
            branch = payload.get("ref", "").replace("refs/heads/", "")
            msg = f"📦 {sender} pushed {len(commits)} commit(s) to {repo}:{branch}"
            for c in commits[:3]:
                msg += f"\n  • {c.get('message', '')[:80]}"
            return {"action": "notify", "message": msg}

        elif event_type == "pull_request":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            msg = f"🔀 PR {action}: #{pr.get('number')} {pr.get('title')} in {repo}"
            return {"action": "notify", "message": msg}

        elif event_type == "issues":
            action = payload.get("action", "")
            issue = payload.get("issue", {})
            msg = f"🐛 Issue {action}: #{issue.get('number')} {issue.get('title')} in {repo}"
            return {"action": "notify", "message": msg}

        elif event_type == "workflow_run":
            run = payload.get("workflow_run", {})
            status = run.get("conclusion", run.get("status", "unknown"))
            msg = f"⚙️ Workflow {run.get('name')}: {status} in {repo}"
            return {"action": "notify", "message": msg}

        return {"action": "notify", "message": f"GitHub {event_type} in {repo}"}

    async def _handle_gitlab(self, trigger: WebhookTrigger, payload: dict, event_type: str) -> dict[str, Any]:
        project = payload.get("project", {}).get("path_with_namespace", "unknown")
        user = payload.get("user", {}).get("username", "unknown")
        return {"action": "notify", "message": f"🦊 GitLab {event_type} by {user} in {project}"}

    async def _handle_calendar(self, trigger: WebhookTrigger, payload: dict, event_type: str) -> dict[str, Any]:
        # Google Calendar / CalDAV webhook
        return {"action": "notify", "message": f"📅 Calendar event: {payload.get('summary', 'Event')}"}

    async def _handle_rss(self, trigger: WebhookTrigger, payload: dict, event_type: str) -> dict[str, Any]:
        # RSS feed update
        entries = payload.get("entries", [])
        if entries:
            latest = entries[0]
            return {"action": "notify", "message": f"📰 New post: {latest.get('title')} - {latest.get('link')}"}
        return {"action": "ignore", "message": "No new entries"}

    async def _handle_generic(self, trigger: WebhookTrigger, payload: dict, event_type: str) -> dict[str, Any]:
        return {"action": "notify", "message": f"🔔 {trigger.source} event: {event_type}"}

    def _save_trigger(self, trigger: WebhookTrigger) -> None:
        try:
            self._trigger_path(trigger.id).write_text(json.dumps(trigger.to_dict(), indent=2))
        except Exception:
            pass

    def _update_index(self, channel: str, chat_id: str, trigger_id: str, action: str) -> None:
        index_path = self._index_path(channel, chat_id)
        index = {"triggers": []}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text())
            except Exception:
                pass
        triggers = index.get("triggers", [])
        if action == "add" and trigger_id not in triggers:
            triggers.append(trigger_id)
        elif action == "remove" and trigger_id in triggers:
            triggers.remove(trigger_id)
        index["triggers"] = triggers
        try:
            index_path.write_text(json.dumps(index, indent=2))
        except Exception:
            pass


trigger_manager = TriggerManager()
