import importlib.util
import json
import unittest

from agent_core.config import settings


class SystemUsageTests(unittest.TestCase):
    def test_system_usage_returns_read_only_resource_snapshot(self):
        path = settings.resolved_tools_dir / "system_usage.py"
        spec = importlib.util.spec_from_file_location("system_usage_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        result = json.loads(module.run())

        self.assertEqual(set(result), {"cpu", "memory", "battery", "disk"})
        self.assertEqual(set(result["cpu"]), {"percent", "logical_cores"})
        self.assertEqual(
            set(result["memory"]), {"total_bytes", "used_bytes", "available_bytes", "percent"}
        )
        self.assertTrue(result["memory"]["total_bytes"] is None or result["memory"]["total_bytes"] > 0)
        self.assertEqual(set(result["battery"]), {"available", "percent", "status", "plugged"})
        self.assertEqual(result["disk"]["scope"], "runtime root filesystem")
        self.assertGreaterEqual(result["disk"]["percent"], 0)
        self.assertLessEqual(result["disk"]["percent"], 100)
