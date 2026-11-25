import signal
import subprocess
import unittest
from unittest.mock import patch

from runner import run_proposal


class ProposalRunnerTests(unittest.TestCase):
    def test_reports_each_passing_and_failing_case(self):
        outcome = run_proposal({
            "source": "def run(value): return value * 2\n",
            "tests": [
                {"args": {"value": 3}, "expected": 6},
                {"args": {"value": 4}, "expected": 7},
            ],
        })
        self.assertFalse(outcome["passed"])
        self.assertEqual([case["passed"] for case in outcome["results"]], [True, False])

    def test_rejects_empty_or_oversized_test_suite(self):
        for tests in ([], [{}] * 11):
            self.assertFalse(run_proposal({"source": "def run(): return 1", "tests": tests})["passed"])

    @patch("runner.os.killpg")
    @patch("runner.subprocess.Popen")
    def test_timeout_kills_candidate_process_group(self, popen, kill_group):
        process = popen.return_value
        process.pid = 42
        process.communicate.side_effect = [subprocess.TimeoutExpired("candidate", 8), ("", "")]

        outcome = run_proposal({"source": "def run(): return 1", "tests": [{"args": {}, "expected": 1}]})

        self.assertFalse(outcome["passed"])
        kill_group.assert_called_once_with(42, signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
