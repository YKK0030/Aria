from datetime import UTC, datetime
import unittest

from agent_core.service import AgentOrchestrator
from agent_core.tracing import trace_summary


class TraceAndMemoryTests(unittest.TestCase):
    def test_memory_filter_omits_fenced_and_raw_code(self) -> None:
        fenced = AgentOrchestrator._memory_safe_text("Here is the page:\n```html\n<html>secret</html>\n```")
        raw = AgentOrchestrator._memory_safe_text("Here is the page:\n<html>secret</html>")
        self.assertNotIn("secret", fenced)
        self.assertNotIn("secret", raw)
        self.assertIn("code omitted", fenced)
        self.assertEqual(raw, "[code omitted from memory]")

    def test_memory_filter_keeps_non_code_and_drops_inline_code(self) -> None:
        self.assertEqual(
            AgentOrchestrator._memory_safe_text("Please use `add_numbers` for my sums."),
            "Please use  for my sums.",
        )
        self.assertEqual(AgentOrchestrator._memory_safe_text("Remember I prefer concise answers."),
                         "Remember I prefer concise answers.")

    def test_file_creation_requests_only_acknowledge_confirmed_writes(self) -> None:
        failed = {"response_text": "```html\nsecret\n```", "used_tools": []}
        AgentOrchestrator._finalize_workspace_response("Create an HTML page", failed)
        self.assertIn("didn’t save any files", failed["response_text"])
        self.assertNotIn("secret", failed["response_text"])

        completed = {"response_text": "```html\nsecret\n```", "used_tools": [{
            "name": "write_workspace_file", "args": {"path": "Aria_test/index.html", "content": "secret"},
        }]}
        AgentOrchestrator._finalize_workspace_response("Create an HTML page", completed)
        self.assertEqual(completed["file_changes"], ["Aria_test/index.html"])
        self.assertIn("Aria_test/index.html", completed["response_text"])
        self.assertNotIn("secret", str(completed))

    def test_trace_reports_active_request_and_delivery_error(self) -> None:
        ts = datetime.now(UTC).isoformat()
        records = [
            {"ts": ts, "event_type": "inbound_request_started", "payload": {
                "channel": "web", "chat_id": "session", "message_id": "active", "task": "Make a page",
            }},
            {"ts": ts, "event_type": "inbound_telegram_processed", "payload": {
                "channel": "telegram", "chat_id": "chat", "message_id": "done", "result": {
                    "event": {"message_id": "done", "channel": "telegram", "chat_id": "chat", "text": "Create a page"},
                    "selected_model": "test-model", "used_tools": [], "response_text": "HTML sample",
                    "delivery_error": "Message is too long",
                },
            }},
        ]
        summary = trace_summary("1h", records)
        self.assertIn("Requests completed: 1 · in progress: 1", summary)
        self.assertIn("Delivery/processing issue: Message is too long", summary)

    def test_request_identity_is_scoped_by_channel_and_chat(self) -> None:
        ts = datetime.now(UTC).isoformat()
        started = lambda channel, chat: {"ts": ts, "event_type": "inbound_request_started", "payload": {
            "channel": channel, "chat_id": chat, "message_id": "same", "task": "task",
        }}
        completed = {"ts": ts, "event_type": "inbound_cli_processed", "payload": {
            "channel": "cli", "chat_id": "one", "message_id": "same", "result": {},
        }}
        self.assertIn("Requests completed: 1 · in progress: 1", trace_summary("1h", [started("cli", "one"), started("web", "two"), completed]))


if __name__ == "__main__":
    unittest.main()
