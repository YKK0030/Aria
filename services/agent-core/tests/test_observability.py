import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_core.config import settings
from agent_core.observability import (
    JsonLogFormatter,
    request_id_var,
    trace_id_var,
    reset_request_context,
    set_request_context,
)
from agent_core.storage import FileStore


class ObservabilityTests(unittest.TestCase):
    def test_json_formatter_includes_event_and_request_context(self):
        tokens = set_request_context("request-123")
        trace_token = trace_id_var.set("trace-456")
        try:
            record = logging.LogRecord("aria.events", logging.INFO, "", 1, "request done", (), None)
            record.aria_event = {"name": "http.request.completed", "status": 200}
            payload = json.loads(JsonLogFormatter().format(record))
        finally:
            trace_id_var.reset(trace_token)
            reset_request_context(tokens)

        self.assertEqual(payload["message"], "request done")
        self.assertEqual(payload["request_id"], "request-123")
        self.assertEqual(payload["trace_id"], "trace-456")
        self.assertEqual(payload["event"]["status"], 200)

    def test_invalid_client_request_id_is_replaced(self):
        tokens = set_request_context("bad request id")
        try:
            self.assertNotEqual(request_id_var.get(), "bad request id")
            self.assertTrue(request_id_var.get())
        finally:
            reset_request_context(tokens)

    def test_audit_record_includes_observability_ids(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "enable_audit_logging", True):
            store = FileStore(directory)
            request_token = request_id_var.set("req-audit")
            trace_token = trace_id_var.set("trace-audit")
            try:
                with patch("agent_core.storage.current_trace_id", return_value="trace-audit"):
                    store.append_audit("sample", {"safe": True})
            finally:
                request_id_var.reset(request_token)
                trace_id_var.reset(trace_token)
            record = json.loads(next(store.audit_dir.glob("*.jsonl")).read_text(encoding="utf-8"))

        self.assertEqual(record["request_id"], "req-audit")
        self.assertEqual(record["trace_id"], "trace-audit")
        self.assertEqual(record["payload"], {"safe": True})


if __name__ == "__main__":
    unittest.main()
