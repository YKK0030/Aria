import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from agent_core.config import settings
from agent_core.main import admin_mark_tool_tested, admin_review_tool_proposal
from agent_core.models import InboundEvent, ToolReviewRequest, ToolTestResultRequest
from agent_core.runtime import AgentRuntime
from agent_core.tooling.loader import DynamicToolRegistry
from agent_core.tooling.proposals import tool_proposals


class ToolProposalTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        root = Path(self.temp.name)
        self.proposals = root / "proposals"
        self.generated = root / "generated"
        self.original_root = tool_proposals.root
        tool_proposals.root = self.proposals
        self.settings_patch = patch.object(settings, "generated_tools_dir", str(self.generated))
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(setattr, tool_proposals, "root", self.original_root)

    def create(self) -> dict:
        return tool_proposals.create(
            "Add Values",
            "Add two integers.",
            "def run(a: int, b: int) -> int:\n    return a + b\n",
            [{"args": {"a": 2, "b": 3}, "expected": 5}],
        )

    @staticmethod
    def mark_tested(proposal: dict) -> dict:
        return tool_proposals.record_test_run(proposal["id"], proposal["sha256"], {
            "passed": True,
            "tests": len(proposal["tests"]),
            "results": [{"case": index, "passed": True, "actual": "expected"} for index, _ in enumerate(proposal["tests"], 1)],
        })

    def test_agent_can_propose_locally_but_not_from_messaging_channels(self) -> None:
        runtime = AgentRuntime()
        local = InboundEvent(
            channel="cli", chatId="local", senderId="owner", messageId="one", text="make a tool", timestamp=1
        )
        remote = local.model_copy(update={"channel": "whatsapp"})
        local_names = {tool.name for tool in runtime._tools_for(local, [])}
        remote_names = {tool.name for tool in runtime._tools_for(remote, [])}
        self.assertIn("propose_task_tool", local_names)
        self.assertIn("list_available_tools", local_names)
        self.assertIn("update_task_tool", local_names)
        self.assertNotIn("propose_task_tool", remote_names)
        self.assertNotIn("update_task_tool", remote_names)

    def test_agent_accepts_json_string_test_cases_from_local_model(self) -> None:
        event = InboundEvent(
            channel="cli", chatId="local", senderId="owner", messageId="one", text="make a tool", timestamp=1
        )
        proposal_tool = next(tool for tool in AgentRuntime()._tools_for(event, []) if tool.name == "propose_task_tool")
        result = proposal_tool.entrypoint(
            name="add_two_integers",
            description="Add two integers.",
            source="def run(a: int, b: int) -> int:\n    return a + b\n",
            tests='[{"args":{"a":1,"b":2},"expected":3}]',
        )
        self.assertIn("saved as pending", str(result))
        self.assertEqual(tool_proposals.list()[0]["name"], "add_two_integers")

    def test_proposal_requires_matching_test_and_owner_approval(self) -> None:
        proposal = self.create()
        self.assertEqual(proposal["status"], "pending")
        self.assertFalse(self.generated.exists())

        with self.assertRaises(HTTPException) as untested:
            tool_proposals.approve(proposal["id"])
        self.assertEqual(untested.exception.status_code, 409)

        with self.assertRaises(HTTPException) as mismatch:
            tool_proposals.record_test_run(proposal["id"], "0" * 64, {"passed": True, "tests": 1, "results": [{"case": 1, "passed": True}]})
        self.assertEqual(mismatch.exception.status_code, 409)

        incomplete = tool_proposals.record_test_run(
            proposal["id"], proposal["sha256"], {"passed": True, "tests": 0, "results": []}
        )
        self.assertEqual(incomplete["status"], "pending")
        self.assertFalse(incomplete["test_run"]["passed"])

        self.mark_tested(proposal)
        with self.assertRaises(HTTPException) as not_reviewed:
            tool_proposals.approve(proposal["id"])
        self.assertEqual(not_reviewed.exception.status_code, 409)
        reviewed = tool_proposals.record_review(
            proposal["id"],
            proposal["sha256"],
            len(proposal["tests"]),
            {"approved": True, "summary": "Small pure function; no issues found.", "findings": []},
        )
        self.assertEqual(reviewed["status"], "reviewed")
        approved = tool_proposals.approve(proposal["id"])
        self.assertEqual(approved["status"], "approved")
        self.assertTrue((self.generated / "add_values.py").exists())
        registry = DynamicToolRegistry()
        specs = registry.list_tool_specs()
        self.assertIn("add_values", {spec["name"] for spec in specs})
        agno_tool = next(tool for tool in registry.get_agno_tools() if tool.name == "add_values")
        result = asyncio.run(agno_tool.entrypoint(a=2, b=3))
        self.assertIn("5", str(result))
        with self.assertRaises(HTTPException):
            tool_proposals.delete_uninstalled(proposal["id"])

    def test_agent_lists_pending_drafts_and_deletes_only_on_explicit_request(self) -> None:
        first = self.create()
        self.create()
        event = InboundEvent(
            channel="cli", chatId="local", senderId="owner", messageId="manage", text="manage tools", timestamp=1
        )
        tools = {tool.name: tool for tool in AgentRuntime()._tools_for(event, [])}

        listed = tools["list_pending_tool_drafts"].entrypoint()
        ambiguous = tools["delete_pending_tool_draft"].entrypoint(name="add_values")
        self.assertIn('"status": "pending"', listed)
        self.assertIn("nothing was deleted", ambiguous)
        self.assertEqual(len(tool_proposals.list()), 2)

        deleted = tools["delete_pending_tool_draft"].entrypoint(name="add_values", all_matching=True)
        self.assertIn("Deleted 2", deleted)
        self.assertEqual(tool_proposals.list(), [])

    def test_uninstalled_draft_can_be_deleted(self) -> None:
        proposal = self.create()
        deleted = tool_proposals.delete_uninstalled(proposal["id"])
        self.assertEqual(deleted["name"], "add_values")
        self.assertEqual(tool_proposals.list(), [])

    def test_update_replaces_only_an_installed_generated_tool_after_review(self) -> None:
        self.generated.mkdir()
        installed = self.generated / "add_values.py"
        installed.write_text(
            'TOOL_NAME="add_values"\nTOOL_DESCRIPTION="Old behavior."\n'
            'TOOL_ENABLED=True\nTOOL_APPROVAL_REQUIRED=False\n'
            'def run(a: int, b: int) -> int: return a + b\n',
            encoding="utf-8",
        )
        proposal = tool_proposals.create(
            "Add Values",
            "Add and include a bonus.",
            "def run(a: int, b: int, bonus: int = 1) -> int:\n    return a + b + bonus\n",
            [{"args": {"a": 2, "b": 3}, "expected": 6}],
            replaces_tool="add_values",
        )
        self.mark_tested(proposal)
        tool_proposals.record_review(
            proposal["id"], proposal["sha256"], 1,
            {"approved": True, "summary": "Updated behavior is bounded.", "findings": []},
        )

        approved = tool_proposals.approve(proposal["id"])

        self.assertEqual(approved["status"], "approved")
        self.assertIn("bonus", installed.read_text(encoding="utf-8"))

    def test_update_proposal_must_target_existing_generated_tool(self) -> None:
        with self.assertRaises(HTTPException) as error:
            tool_proposals.create(
                "Missing Tool", "Update.", "def run(): return 1\n",
                [{"args": {}, "expected": 1}], replaces_tool="missing_tool",
            )
        self.assertEqual(error.exception.status_code, 404)

    def test_rejects_invalid_source_and_test_cases(self) -> None:
        with self.assertRaises(HTTPException):
            tool_proposals.create("broken", "Broken", "not python", [{"args": {}, "expected": None}])
        with self.assertRaises(HTTPException):
            tool_proposals.create("missing", "Missing run", "VALUE = 1", [{"args": {}, "expected": 1}])
        with self.assertRaises(HTTPException):
            tool_proposals.create("bad_cases", "Bad cases", "def run(): return 1", ["not an object"])

    def test_test_result_cannot_be_reused_after_proposal_changes(self) -> None:
        proposal = self.create()
        tool_proposals.record_review(
            proposal["id"],
            proposal["sha256"],
            len(proposal["tests"]),
            {"approved": True, "summary": "Looks good.", "findings": []},
        )
        path = self.proposals / f"{proposal['id']}.json"
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["source"] = "def run(): return 'changed'\n"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(HTTPException) as error:
            tool_proposals.approve(proposal["id"])
        self.assertEqual(error.exception.status_code, 409)

    def test_editing_tests_invalidates_prior_test_and_review(self) -> None:
        proposal = self.create()
        tool_proposals.record_test_run(proposal["id"], proposal["sha256"], {
            "passed": True, "tests": 1, "results": [{"case": 1, "passed": True, "actual": "5"}],
        })
        changed = tool_proposals.update_tests(
            proposal["id"], proposal["sha256"],
            [{"args": {"a": 1, "b": 2}, "expected": 3}, {"args": {"a": -1, "b": 1}, "expected": 0}],
        )
        self.assertNotEqual(changed["sha256"], proposal["sha256"])
        self.assertEqual(changed["status"], "pending")
        self.assertNotIn("test_run", changed)
        with self.assertRaises(HTTPException):
            tool_proposals.update_tests(proposal["id"], proposal["sha256"], proposal["tests"])

    def test_failed_or_incomplete_sandbox_outcome_never_marks_draft_tested(self) -> None:
        proposal = self.create()
        result = tool_proposals.record_test_run(proposal["id"], proposal["sha256"], {
            "passed": True, "tests": 1, "results": [{"case": 1, "passed": False, "actual": "4"}],
        })
        self.assertEqual(result["status"], "pending")
        self.assertFalse(result["test_run"]["passed"])
        with self.assertRaises(HTTPException):
            tool_proposals.approve(proposal["id"])

    def test_test_api_uses_isolated_runner_before_marking_current_revision_tested(self) -> None:
        proposal = self.create()
        outcome = {"passed": True, "tests": 1, "results": [{"case": 1, "passed": True, "actual": "5"}]}
        with (
            patch("agent_core.main._verify_admin_api_key"),
            patch("agent_core.main.run_tool_tests", new_callable=AsyncMock, return_value=outcome) as runner,
            patch("agent_core.main.store.append_audit"),
        ):
            response = asyncio.run(admin_mark_tool_tested(
                proposal["id"], ToolTestResultRequest(sha256=proposal["sha256"], test_count=1), "admin"
            ))
        runner.assert_awaited_once_with(proposal)
        self.assertEqual(response["proposal"]["status"], "tested")
        self.assertTrue(response["proposal"]["test_run"]["passed"])

    def test_review_with_findings_cannot_be_approved(self) -> None:
        proposal = self.create()
        reviewed = tool_proposals.record_review(
            proposal["id"],
            proposal["sha256"],
            len(proposal["tests"]),
            {"approved": False, "summary": "Review found a concern.", "findings": ["Avoid file deletion."]},
        )
        self.assertEqual(reviewed["status"], "needs_changes")
        with self.assertRaises(HTTPException):
            tool_proposals.approve(proposal["id"])

    def test_revisions_are_new_pending_proposals_with_a_two_revision_limit(self) -> None:
        proposal = self.create()
        rejected = tool_proposals.record_review(
            proposal["id"],
            proposal["sha256"],
            len(proposal["tests"]),
            {"approved": False, "summary": "Revise.", "findings": ["Use clearer parameter names."]},
        )
        self.assertEqual(rejected["status"], "needs_changes")

        first = tool_proposals.create_revision(
            proposal["id"], proposal["sha256"], proposal["source"], proposal["tests"]
        )
        self.assertEqual(first["status"], "pending")
        self.assertEqual(first["revision_of"], proposal["id"])
        self.assertEqual(first["revision_number"], 1)
        with self.assertRaises(HTTPException):
            tool_proposals.create_revision(proposal["id"], "0" * 64, proposal["source"], proposal["tests"])

        tool_proposals.record_review(
            first["id"],
            first["sha256"],
            len(first["tests"]),
            {"approved": False, "summary": "Revise once more.", "findings": ["Clarify behavior."]},
        )
        second = tool_proposals.create_revision(first["id"], first["sha256"], first["source"], first["tests"])
        self.assertEqual(second["revision_number"], 2)
        tool_proposals.record_review(
            second["id"],
            second["sha256"],
            len(second["tests"]),
            {"approved": False, "summary": "Still not accepted.", "findings": ["Unresolved."]},
        )
        with self.assertRaises(HTTPException):
            tool_proposals.create_revision(second["id"], second["sha256"], second["source"], second["tests"])

    def test_approval_does_not_overwrite_existing_generated_file(self) -> None:
        proposal = self.create()
        self.mark_tested(proposal)
        self.generated.mkdir()
        existing = self.generated / "add_values.py"
        existing.write_text(
            'TOOL_NAME="other_tool"\nTOOL_DESCRIPTION="Disabled."\n'
            'TOOL_ENABLED=False\ndef run(): return None\n',
            encoding="utf-8",
        )
        original = existing.read_text(encoding="utf-8")
        with self.assertRaises(HTTPException) as error:
            tool_proposals.approve(proposal["id"])
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(existing.read_text(encoding="utf-8"), original)

    def test_api_refuses_reviewer_until_current_revision_has_passed_sandbox(self) -> None:
        proposal = self.create()
        with patch("agent_core.main._verify_admin_api_key"):
            with self.assertRaises(HTTPException) as rejected:
                asyncio.run(admin_review_tool_proposal(
                    proposal["id"], ToolReviewRequest(sha256=proposal["sha256"], test_count=1), "admin"
                ))
        self.assertEqual(rejected.exception.status_code, 409)
