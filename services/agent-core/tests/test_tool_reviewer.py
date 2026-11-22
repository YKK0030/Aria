from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agent_core.tooling.reviewer import ToolReview, ToolReviewUnavailable, ToolRevision, review_tool, revise_tool


class ToolReviewerTests(IsolatedAsyncioTestCase):
    async def test_reviewer_uses_no_tools_and_returns_structured_verdict(self):
        agent = SimpleNamespace(
            arun=AsyncMock(
                return_value=SimpleNamespace(
                    content=ToolReview(approved=True, summary="Pure addition function.", findings=[])
                )
            )
        )
        proposal = {"name": "add_values", "description": "Add numbers.", "source": "def run(a,b): return a+b", "tests": []}

        with patch("agent_core.tooling.reviewer.create_agent", return_value=agent) as create_agent:
            result = await review_tool(proposal, 1)

        self.assertTrue(result.approved)
        self.assertEqual(create_agent.call_args.args[1], [])
        self.assertEqual(agent.arun.call_args.kwargs["output_schema"], ToolReview)

    async def test_review_with_findings_can_never_be_approved(self):
        agent = SimpleNamespace(
            arun=AsyncMock(
                return_value=SimpleNamespace(
                    content=ToolReview(approved=True, summary="Potentially unsafe.", findings=["Uses eval."])
                )
            )
        )
        proposal = {"name": "unsafe", "description": "Run code.", "source": "def run(): pass", "tests": []}
        with patch("agent_core.tooling.reviewer.create_agent", return_value=agent):
            result = await review_tool(proposal, 1)
        self.assertFalse(result.approved)

    async def test_unavailable_reviewer_fails_closed(self):
        agent = SimpleNamespace(arun=AsyncMock(return_value=SimpleNamespace(content="not JSON")))
        proposal = {"name": "x", "description": "x", "source": "def run(): pass", "tests": []}
        with patch("agent_core.tooling.reviewer.create_agent", return_value=agent):
            with self.assertRaises(ToolReviewUnavailable):
                await review_tool(proposal, 1)

    async def test_reviser_receives_review_feedback_and_has_no_tools(self):
        revision = ToolRevision(
            source="def run(a: int, b: int) -> int:\n    return a + b\n",
            tests=[{"args": {"a": 1, "b": 2}, "expected": 3}],
        )
        agent = SimpleNamespace(arun=AsyncMock(return_value=SimpleNamespace(content=revision)))
        proposal = {
            "name": "add_values",
            "description": "Add values.",
            "source": "def run(a, b): return a + b",
            "tests": [],
            "review": {"approved": False, "findings": ["Use type annotations."]},
        }
        with patch("agent_core.tooling.reviewer.create_agent", return_value=agent) as create_agent:
            result = await revise_tool(proposal)

        self.assertEqual(result, revision)
        self.assertEqual(create_agent.call_args.args[1], [])
        self.assertEqual(agent.arun.call_args.kwargs["output_schema"], ToolRevision)
        self.assertIn("Use type annotations", agent.arun.call_args.args[0])


if __name__ == "__main__":
    import unittest

    unittest.main()
