import json
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest import TestCase


RUNNER = Path(__file__).resolve().parents[1] / "runner.py"


class ToolSandboxRunnerTests(TestCase):
    def run_candidate(self, source: str, expected: int) -> subprocess.CompletedProcess[str]:
        with NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as proposal:
            json.dump(
                {
                    "source": source,
                    "tests": [{"args": {"value": 4}, "expected": expected}],
                },
                proposal,
            )
            proposal.flush()
            return subprocess.run(
                [sys.executable, str(RUNNER), proposal.name],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
            )

    def test_valid_candidate_passes_declared_tests(self) -> None:
        result = self.run_candidate("def run(value: int) -> int:\n    return value + 1\n", 5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"passed": true', result.stdout)

    def test_wrong_result_fails_declared_tests(self) -> None:
        result = self.run_candidate("def run(value: int) -> int:\n    return value - 1\n", 5)
        self.assertEqual(result.returncode, 1)
        self.assertIn('"passed": false', result.stdout)
