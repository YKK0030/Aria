import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_core.config import settings
from agent_core.storage import FileStore


class AuditTraceTests(unittest.TestCase):
    def test_read_audit_returns_recent_records_and_filters_nested_event_fields(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "enable_audit_logging", True):
            store = FileStore(directory)
            store.append_audit("inbound_web_processed", {
                "chat_id": "session-1",
                "result": {"event": {"channel": "web"}, "used_tools": [{"name": "add_numbers"}]},
            })
            store.append_audit("inbound_cli_processed", {
                "chat_id": "session-2", "result": {"event": {"channel": "cli"}},
            })

            web_events = store.read_audit(channel="web", chat_id="session-1")

        self.assertEqual(len(web_events), 1)
        self.assertEqual(web_events[0]["event_type"], "inbound_web_processed")


if __name__ == "__main__":
    unittest.main()
