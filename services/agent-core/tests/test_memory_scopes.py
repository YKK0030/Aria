import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, PropertyMock, patch

from agent_core.config import settings
from agent_core.memory.long_term import SQLiteLongTermGraphMemory
from agent_core.memory.short_term import RedisShortTermMemory


class MemoryScopeTests(TestCase):
    def test_sqlite_search_stays_within_channel_and_chat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                type(settings),
                "resolved_long_term_memory_db_path",
                new_callable=PropertyMock,
                return_value=Path(directory) / "memory.sqlite3",
            ):
                memory = SQLiteLongTermGraphMemory()
                memory.add_node("telegram", "chat-a", "user", "private phrase")
                memory.add_node("telegram", "chat-b", "user", "private phrase")

                results = memory.search_nodes("telegram", "chat-a", "private phrase")

        self.assertEqual([item["text"] for item in results], ["private phrase"])

    def test_mcp_memory_delete_is_identity_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                type(settings),
                "resolved_long_term_memory_db_path",
                new_callable=PropertyMock,
                return_value=Path(directory) / "memory.sqlite3",
            ):
                memory = SQLiteLongTermGraphMemory()
                memory_id = memory.add_node("mcp", "mcp:alice", "memory", "alice secret")
                memory.add_node("mcp", "mcp:bob", "memory", "bob secret")

                denied = memory.delete_node("mcp", "mcp:bob", memory_id)
                deleted = memory.delete_node("mcp", "mcp:alice", memory_id)
                alice_results = memory.search_nodes("mcp", "mcp:alice", "alice secret")
                bob_results = memory.search_nodes("mcp", "mcp:bob", "bob secret")

        self.assertFalse(denied)
        self.assertTrue(deleted)
        self.assertEqual(alice_results, [])
        self.assertEqual([item["text"] for item in bob_results], ["bob secret"])

    def test_valkey_key_is_channel_and_chat_scoped(self) -> None:
        self.assertNotEqual(
            RedisShortTermMemory._key("telegram", "chat-a"),
            RedisShortTermMemory._key("telegram", "chat-b"),
        )
        self.assertNotEqual(
            RedisShortTermMemory._key("telegram", "chat-a"),
            RedisShortTermMemory._key("whatsapp", "chat-a"),
        )

class ValkeyMemoryTests(IsolatedAsyncioTestCase):
    async def test_valkey_keeps_four_turns_and_sets_ttl(self) -> None:
        memory = RedisShortTermMemory()
        memory._disabled = False
        client = AsyncMock()
        with (
            patch.object(settings, "short_term_memory_turns", 4),
            patch.object(settings, "short_term_memory_ttl_seconds", 60),
            patch.object(memory, "_get_client", AsyncMock(return_value=client)),
        ):
            await memory.append_message("telegram", "chat-a", "user", "hello")

        key = "agent:memory:short:telegram:chat-a"
        client.ltrim.assert_awaited_once_with(key, -8, -1)
        client.expire.assert_awaited_once_with(key, 60)
