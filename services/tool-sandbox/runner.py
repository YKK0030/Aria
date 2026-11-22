from __future__ import annotations

import json
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
for index, case in enumerate(cases):
    actual = function(**case["args"])
    if inspect.isawaitable(actual): actual = asyncio.run(actual)
    if actual != case["expected"]:
        raise AssertionError(f"case {index + 1} returned a different result")
print("ARIA_CASES_PASSED=" + str(len(cases)))
'''


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: runner.py PROPOSAL.json|-", file=sys.stderr)
        return 2
    try:
        proposal_json = sys.stdin.read() if sys.argv[1] == "-" else Path(sys.argv[1]).read_text(encoding="utf-8")
        proposal = json.loads(proposal_json)
        with tempfile.TemporaryDirectory(prefix="aria-tool-") as directory:
            root = Path(directory)
            source = root / "candidate.py"
            cases = root / "tests.json"
            source.write_text(proposal["source"], encoding="utf-8")
            cases.write_text(json.dumps(proposal["tests"]), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-I", "-c", HARNESS, str(source), str(cases)],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        if result.returncode != 0 or "ARIA_CASES_PASSED=" not in result.stdout:
            detail = (result.stderr or "Candidate did not complete its tests.").strip()[-500:]
            print(f"{MARKER}{json.dumps({'passed': False, 'detail': detail})}")
            return 1
        count = int(result.stdout.rsplit("ARIA_CASES_PASSED=", 1)[1].splitlines()[0])
        print(f"{MARKER}{json.dumps({'passed': True, 'tests': count})}")
        return 0
    except subprocess.TimeoutExpired:
        print(f"{MARKER}{json.dumps({'passed': False, 'detail': 'Tool test exceeded 8 seconds.'})}")
        return 1
    except Exception as error:
        print(f"{MARKER}{json.dumps({'passed': False, 'detail': type(error).__name__})}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
