import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from agent_core.policy import AccessPolicy


class AccessPolicyTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "base-policy.json"
        self.base.write_text(json.dumps({"whatsapp": {"allowed_chat_ids": ["base@s.whatsapp.net"]}}))

    def make_policy(self) -> AccessPolicy:
        access = AccessPolicy(str(self.base))
        access._override_path = self.root / "overrides.json"
        return access

    def test_dynamic_allowlist_replaces_base_and_persists(self) -> None:
        access = self.make_policy()
        channel = access.update_allowlist("whatsapp", ["  123@s.whatsapp.net "], ["blocked@g.us"])
        self.assertTrue(channel["allowlist_managed"])
        self.assertEqual(channel["allowed_chat_ids"], ["123@s.whatsapp.net"])
        self.assertEqual(access.load()["whatsapp"]["allowed_chat_ids"], ["123@s.whatsapp.net"])

    def test_empty_managed_allowlist_is_closed_and_reset_restores_base(self) -> None:
        access = self.make_policy()
        access.update_allowlist("telegram", [], [])
        self.assertTrue(access.load()["telegram"]["allowlist_managed"])
        self.assertEqual(access.load()["telegram"]["allowed_chat_ids"], [])
        access.reset_allowlist("telegram")
        self.assertNotIn("allowlist_managed", access.load()["telegram"])

    def test_invalid_or_overlapping_ids_are_rejected(self) -> None:
        access = self.make_policy()
        for allowed, blocked in ((["same"], ["same"]), (["   "], []), (["x" * 129], [])):
            with self.assertRaises(ValueError):
                access.update_allowlist("telegram", allowed, blocked)
        with self.assertRaises(ValueError):
            access.update_allowlist("email", [], [])


if __name__ == "__main__":
    import unittest

    unittest.main()
