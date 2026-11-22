from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from agent_core.models import InboundEvent
from agent_core.runtime import AgentRuntime
from agent_core.tooling.code_changes import CodeChangeStore, is_allowed_source_path
from agent_core.tooling.reviewer import CodeReview, review_code_change


RUNTIME = "services/agent-core/src/agent_core/runtime.py"
PATCH = f"""diff --git a/{RUNTIME} b/{RUNTIME}
index 1111111..2222222 100644
--- a/{RUNTIME}
+++ b/{RUNTIME}
@@ -1 +1 @@
-old = 1
+new = 2
"""


class CodeChangeTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.store = CodeChangeStore()
        self.store.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_application_source_changes_are_accepted_and_readable(self):
        proposal = self.store.create("Support a changed model response format", PATCH)
        self.assertEqual(proposal["status"], "pending")
        self.assertIn("patch", self.store.get(proposal["id"]))
        self.assertTrue(is_allowed_source_path("services/agent-core/src/agent_core/integrations/telegram_bot.py"))
        self.assertIn("class AgentRuntime", self.store.read_source_file(RUNTIME))
        self.assertIn(RUNTIME, self.store.list_source_files())

    def test_prompt_memory_database_and_new_file_patches_are_rejected(self):
        for path in (
            "services/agent-core/src/agent_core/prompts/system.md",
            "services/agent-core/src/agent_core/config.py",
            "services/agent-core/src/agent_core/policy.py",
            "services/agent-core/src/agent_core/storage.py",
            "services/agent-core/src/agent_core/memory/long_term.py",
            "services/agent-core/src/agent_core/../config.py",
            "tools/aria",
        ):
            with self.subTest(path=path), self.assertRaises(HTTPException):
                self.store.create("change protected path", PATCH.replace(RUNTIME, path))
        deleted = PATCH.replace(f"--- a/{RUNTIME}", "--- /dev/null")
        with self.assertRaises(HTTPException):
            self.store.create("add file", deleted)
        mismatch = PATCH.replace(
            f"+++ b/{RUNTIME}", "+++ b/services/agent-core/src/agent_core/main.py"
        )
        with self.assertRaises(HTTPException):
            self.store.create("mismatched patch headers", mismatch)
        with self.assertRaises(HTTPException):
            self.store.create("empty", "")

    def test_review_is_bound_to_unchanged_patch(self):
        proposal = self.store.create("Adapt runtime", PATCH)
        reviewed = self.store.record_review(
            proposal["id"], proposal["sha256"],
            {"approved": True, "summary": "Narrow change.", "findings": []},
        )
        self.assertEqual(reviewed["status"], "reviewed")
        path = Path(self.temp.name) / f"{proposal['id']}.json"
        saved = self.store._read(path)
        saved["patch"] += "# tampered"
        path.write_text(__import__("json").dumps(saved), encoding="utf-8")
        with self.assertRaises(HTTPException):
            self.store.get(proposal["id"])

    def test_code_inspection_and_proposals_are_available_in_owner_channels_only(self):
        event = InboundEvent(
            channel="cli", chatId="local", senderId="owner", messageId="one", text="adapt", timestamp=1,
        )
        local = {tool.name for tool in AgentRuntime()._tools_for(event, [])}
        telegram = {
            tool.name for tool in AgentRuntime()._tools_for(event.model_copy(update={"channel": "telegram"}), [])
        }
        remote = {tool.name for tool in AgentRuntime()._tools_for(event.model_copy(update={"channel": "whatsapp"}), [])}
        self.assertIn("propose_code_change", local)
        self.assertIn("read_aria_source_file", local)
        self.assertIn("propose_code_change", telegram)
        self.assertIn("read_aria_source_file", telegram)
        self.assertNotIn("propose_code_change", remote)


class CodeReviewerTests(IsolatedAsyncioTestCase):
    async def test_code_reviewer_has_no_tools_and_returns_structured_verdict(self):
        agent = SimpleNamespace(arun=AsyncMock(return_value=SimpleNamespace(
            content=CodeReview(approved=True, summary="Narrow runtime edit.", findings=[]),
        )))
        proposal = {"description": "Adapt parsing", "patch": PATCH}
        with patch("agent_core.tooling.reviewer.create_agent", return_value=agent) as factory:
            result = await review_code_change(proposal)
        self.assertTrue(result.approved)
        self.assertEqual(factory.call_args.args[1], [])
        self.assertEqual(agent.arun.call_args.kwargs["output_schema"], CodeReview)


if __name__ == "__main__":
    import unittest

    unittest.main()
