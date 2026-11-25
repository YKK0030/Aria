from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path


MARKER = "ARIA_TOOL_TEST_RESULT="
HARNESS = r'''import asyncio, importlib.util, inspect, json, sys
source_path, cases_path = sys.argv[1:]
spec = importlib.util.spec_from_file_location("candidate_tool", source_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
function = getattr(module, "run", None)
if not callable(function): raise TypeError("run function missing")
cases = json.load(open(cases_path, encoding="utf-8"))
results = []
for index, case in enumerate(cases):
    try:
        actual = function(**case["args"])
        if inspect.isawaitable(actual): actual = asyncio.run(actual)
        results.append({"case": index + 1, "passed": actual == case["expected"], "actual": repr(actual)[:300]})
    except Exception as error:
        results.append({"case": index + 1, "passed": False, "error": f"{type(error).__name__}: {str(error)[:240]}"})
print("ARIA_TOOL_TEST_RESULT=" + json.dumps({"passed": all(item["passed"] for item in results), "tests": len(results), "results": results}))
if not all(item["passed"] for item in results): sys.exit(1)
'''


def run_proposal(proposal: dict, demote: bool = False) -> dict:
    if not isinstance(proposal, dict) or not isinstance(proposal.get("source"), str):
        return {"passed": False, "tests": 0, "results": [], "error": "Invalid proposal source."}
    tests = proposal.get("tests")
    if not isinstance(tests, list) or not 1 <= len(tests) <= 10:
        return {"passed": False, "tests": 0, "results": [], "error": "A suite must contain 1–10 test cases."}
    try:
        with tempfile.TemporaryDirectory(prefix="aria-tool-") as directory:
            root = Path(directory)
            source = root / "candidate.py"
            cases = root / "tests.json"
            source.write_text(proposal["source"], encoding="utf-8")
            cases.write_text(json.dumps(tests), encoding="utf-8")
            if demote:
                root.chmod(0o755)
                source.chmod(0o644)
                cases.chmod(0o644)
            process = subprocess.Popen(
                [sys.executable, "-I", "-c", HARNESS, str(source), str(cases)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                user=65534 if demote and os.geteuid() == 0 else None,
                group=65534 if demote and os.geteuid() == 0 else None,
                extra_groups=() if demote and os.geteuid() == 0 else None,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
                return {"passed": False, "tests": len(tests), "results": [], "error": "Test suite exceeded 8 seconds."}
        payload_line = next(
            (line for line in reversed(stdout.splitlines()) if line.startswith(MARKER)), None
        )
        if payload_line:
            outcome = json.loads(payload_line[len(MARKER):])
            outcome["passed"] = bool(outcome.get("passed")) and process.returncode == 0
            if not outcome["passed"]:
                outcome["error"] = "One or more test cases failed."
            return outcome
        return {
            "passed": False,
            "tests": len(tests),
            "results": [],
            "error": (stderr or "Candidate did not return test results.").strip()[-400:],
        }
    except Exception as error:
        return {"passed": False, "tests": len(tests), "results": [], "error": type(error).__name__}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: runner.py PROPOSAL.json|-", file=sys.stderr)
        return 2
    try:
        proposal_json = sys.stdin.read() if sys.argv[1] == "-" else Path(sys.argv[1]).read_text(encoding="utf-8")
        outcome = run_proposal(json.loads(proposal_json))
        print(f"{MARKER}{json.dumps(outcome)}")
        return 0 if outcome["passed"] else 1
    except Exception as error:
        print(f"{MARKER}{json.dumps({'passed': False, 'tests': 0, 'results': [], 'error': type(error).__name__})}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
