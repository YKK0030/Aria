import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from agent_core.tooling.delegation import _is_robotics_task, run_specialists


class DelegationTests(IsolatedAsyncioTestCase):
    def test_recognizes_robotics_specialist_tasks(self) -> None:
        self.assertTrue(_is_robotics_task("Explain ROS2 motion planning for a robot arm"))
        self.assertFalse(_is_robotics_task("Summarize a short story"))

    async def test_runs_two_specialists_concurrently_and_returns_both_reports(self) -> None:
        entered = 0
        both_entered = asyncio.Event()

        async def specialist(task: str, role: str, trace_context: dict | None = None) -> str:
            nonlocal entered
            entered += 1
            if entered == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), timeout=1)
            return role

        with patch("agent_core.tooling.delegation._run_specialist", side_effect=specialist):
            result = await run_specialists("Compare two approaches")

        self.assertEqual(entered, 2)
        self.assertIn("Analyst:", result)
        self.assertIn("Reviewer:", result)

    async def test_rejects_empty_or_oversized_tasks_before_calling_agents(self) -> None:
        with patch("agent_core.tooling.delegation._run_specialist") as specialist:
            for task in (" ", "x" * 2001):
                with self.assertRaises(ValueError):
                    await run_specialists(task)
        specialist.assert_not_called()

    async def test_reports_partial_specialist_failure(self) -> None:
        async def specialist(task: str, role: str, trace_context: dict | None = None) -> str:
            if role.startswith("Critical"):
                raise TimeoutError
            return "useful finding"

        with patch("agent_core.tooling.delegation._run_specialist", side_effect=specialist):
            result = await run_specialists("Analyze a bounded problem")

        self.assertIn("useful finding", result)
        self.assertIn("Unavailable (TimeoutError)", result)
