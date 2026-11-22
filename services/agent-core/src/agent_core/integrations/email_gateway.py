from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from agent_core.config import settings
from agent_core.models import EmailInboundEvent
from agent_core.storage import store

logger = logging.getLogger(__name__)


class EmailGateway:
    def __init__(self, event_callback):
        self._event_callback = event_callback
        self._app = FastAPI()
        self._register_routes()

    def _register_routes(self) -> None:
        @self._app.post("/webhooks/email")
        async def email_webhook(
            request: Request,
            x_webhook_key: str = Header(default="", alias="x-webhook-key"),
        ):
            if not settings.channel_enabled("email"):
                raise HTTPException(status_code=503, detail="Email channel is disabled")
            if not settings.email_webhook_key:
                raise HTTPException(status_code=503, detail="Email webhook key not configured")
            if x_webhook_key != settings.email_webhook_key:
                raise HTTPException(status_code=401, detail="Invalid webhook key")

            payload = await request.json()
            event = EmailInboundEvent(
                channel="email",
                chat_id=payload.get("from", "unknown"),
                sender_id=payload.get("from", "unknown"),
                push_name=payload.get("name", "Email"),
                group_name=payload.get("subject", "Email"),
                is_group=False,
                message_id=payload.get("message_id", ""),
                text=payload.get("text", "") or payload.get("html", ""),
                timestamp=int(payload.get("timestamp", datetime.now(UTC).timestamp())),
            )
            await self._event_callback(event)
            return {"ok": True}

    def get_app(self) -> FastAPI:
        return self._app
