from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from agent_core.config import settings


class RedisShortTermMemory:
    def __init__(self) -> None:
        self._client: Redis | None = None
        self._disabled = not settings.redis_enabled

    async def get_messages(self, channel: str, chat_id: str, limit_turns: int | None = None) -> list[dict[str, Any]]:
        if self._disabled:
            return []

        client = await self._get_client()
        if not client:
            return []

        keep_count = max((limit_turns or settings.short_term_memory_turns) * 2, 1)
        try:
            raw_items = await client.lrange(self._key(channel, chat_id), -keep_count, -1)
        except Exception:
            return []

        messages: list[dict[str, Any]] = []
        for raw in raw_items:
            try:
                item = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                messages.append(item)
        return messages

    async def append_message(self, channel: str, chat_id: str, role: str, text: str) -> None:
        if self._disabled:
            return

        client = await self._get_client()
        if not client:
            return

        payload = {
            "role": role,
            "text": text,
            "ts": datetime.now(UTC).isoformat(),
        }
        keep_count = max(settings.short_term_memory_turns * 2, 1)
        key = self._key(channel, chat_id)

        try:
            await client.rpush(key, json.dumps(payload, ensure_ascii=True))
            await client.ltrim(key, -keep_count, -1)
            await client.expire(key, settings.short_term_memory_ttl_seconds)
        except Exception:
            return

    async def _get_client(self) -> Redis | None:
        if self._disabled:
            return None

        if self._client is None:
            try:
                self._client = Redis.from_url(settings.redis_url, decode_responses=True)
                await self._client.ping()
            except Exception:
                self._client = None
                return None

        return self._client

    @staticmethod
    def _key(channel: str, chat_id: str) -> str:
        return f"agent:memory:short:{channel}:{chat_id}"


short_term_memory = RedisShortTermMemory()

