from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException

from agent_core.config import settings


class ToolProposalStore:
    def __init__(self) -> None:
        self.root = settings.resolved_tool_proposals_dir

    def create(
        self, name: str, description: str, source: str, tests: list[dict], replaces_tool: str | None = None
    ) -> dict:
        slug = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")
        if not slug or not re.fullmatch(r"[a-z][a-z0-9_]{1,47}", slug):
            raise HTTPException(status_code=422, detail="Tool name must be a 2-48 character identifier")
        if not description.strip() or len(description) > 500:
            raise HTTPException(status_code=422, detail="Tool description must be 1-500 characters")
        if replaces_tool is not None:
            target = re.sub(r"[^a-z0-9_]+", "_", replaces_tool.strip().lower()).strip("_")
            if target != slug or not re.fullmatch(r"[a-z][a-z0-9_]{1,47}", target):
                raise HTTPException(status_code=422, detail="Updates must keep the installed tool's name")
            path = settings.resolved_generated_tools_dir / f"{target}.py"
            if path.is_symlink() or not path.is_file():
                raise HTTPException(status_code=404, detail="Only installed generated tools can be updated")
        if not source.strip() or len(source.encode()) > 24000:
            raise HTTPException(status_code=422, detail="Tool source must be 1-24000 bytes")
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            raise HTTPException(status_code=422, detail=f"Tool source has a syntax error: {error.msg}") from error
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run" for node in tree.body):
            raise HTTPException(status_code=422, detail="Tool source must define a top-level run function")
        if (
            not isinstance(tests, list)
            or not 1 <= len(tests) <= 10
            or any(
                not isinstance(test, dict)
                or set(test) != {"args", "expected"}
                or not isinstance(test["args"], dict)
                for test in tests
            )
        ):
            raise HTTPException(status_code=422, detail="Provide 1-10 test cases with args and expected")

        proposal = {
            "id": str(uuid4()),
            "name": slug,
            "description": description.strip(),
            "source": source,
            "tests": tests,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
        }
        if replaces_tool is not None:
            proposal["replaces_tool"] = slug
        proposal["sha256"] = self._digest(proposal)
        self.root.mkdir(parents=True, exist_ok=True)
        self._write(proposal)
        return proposal

    def list(self) -> list[dict]:
        self.root.mkdir(parents=True, exist_ok=True)
        return [self.summary(self._read(path)) for path in sorted(self.root.glob("*.json"))]

    def get(self, proposal_id: str) -> dict:
        try:
            UUID(proposal_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Tool proposal not found") from error
        path = self.root / f"{proposal_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Tool proposal not found")
        return self._read(path)

    def delete_uninstalled(self, proposal_id: str) -> dict:
        proposal = self.get(proposal_id)
        if proposal["status"] == "approved" or proposal.get("installed_as"):
            raise HTTPException(status_code=409, detail="Installed tools cannot be deleted as pending drafts")
        (self.root / f"{proposal_id}.json").unlink()
        return self.summary(proposal)

    def update_tests(self, proposal_id: str, digest: str, tests: list[dict]) -> dict:
        proposal = self.get(proposal_id)
        if proposal["status"] not in {"pending", "tested"}:
            raise HTTPException(status_code=409, detail="Only pending drafts can change test cases")
        if digest != proposal["sha256"] or digest != self._digest(proposal):
            raise HTTPException(status_code=409, detail="Test cases do not match this proposal revision")
        if (
            not isinstance(tests, list)
            or not 1 <= len(tests) <= 10
            or any(not isinstance(test, dict) or set(test) != {"args", "expected"} or not isinstance(test["args"], dict) for test in tests)
        ):
            raise HTTPException(status_code=422, detail="Provide 1-10 test cases with args and expected")
        proposal["tests"] = tests
        proposal["status"] = "pending"
        for key in ("tested_at", "tested_sha256", "test_count", "test_run", "review", "reviewed_at", "reviewed_sha256"):
            proposal.pop(key, None)
        proposal["sha256"] = self._digest(proposal)
        self._write(proposal)
        return self.summary(proposal)

    def record_test_run(self, proposal_id: str, digest: str, outcome: dict) -> dict:
        proposal = self.get(proposal_id)
        if proposal["status"] != "pending":
            raise HTTPException(status_code=409, detail="Only pending tool proposals can be tested")
        if digest != proposal["sha256"] or digest != self._digest(proposal):
            raise HTTPException(status_code=409, detail="Test result does not match this proposal revision")
        results = outcome.get("results") if isinstance(outcome, dict) else None
        passed = (
            isinstance(results, list)
            and len(results) == len(proposal["tests"])
            and all(isinstance(item, dict) and item.get("passed") is True for item in results)
            and outcome.get("passed") is True
            and outcome.get("tests") == len(proposal["tests"])
        )
        proposal["test_run"] = {
            "passed": passed,
            "tests": len(proposal["tests"]),
            "results": results[:10] if isinstance(results, list) else [],
            "error": str(outcome.get("error", ""))[:400] if isinstance(outcome, dict) else "Invalid sandbox result",
            "finished_at": datetime.now(UTC).isoformat(),
        }
        if passed:
            proposal["status"] = "tested"
            proposal["tested_at"] = proposal["test_run"]["finished_at"]
            proposal["tested_sha256"] = digest
            proposal["test_count"] = len(proposal["tests"])
        self._write(proposal)
        return self.summary(proposal)

    def record_review(self, proposal_id: str, digest: str, test_count: int, review: dict) -> dict:
        proposal = self.get(proposal_id)
        if proposal["status"] not in {"pending", "tested"}:
            raise HTTPException(status_code=409, detail="Only unapproved proposals can be reviewed")
        if digest != proposal["sha256"] or digest != self._digest(proposal):
            raise HTTPException(status_code=409, detail="Review does not match this proposal revision")
        if test_count != len(proposal["tests"]):
            raise HTTPException(status_code=422, detail="All declared tests must pass before review")
        if (
            not isinstance(review, dict)
            or not isinstance(review.get("approved"), bool)
            or not isinstance(review.get("summary"), str)
            or not isinstance(review.get("findings"), list)
        ):
            raise HTTPException(status_code=422, detail="Invalid tool review result")
        proposal["review"] = review
        proposal["reviewed_at"] = datetime.now(UTC).isoformat()
        proposal["reviewed_sha256"] = digest
        proposal["test_count"] = test_count
        proposal["status"] = "reviewed" if review["approved"] and not review["findings"] else "needs_changes"
        self._write(proposal)
        return self.summary(proposal)

    def create_revision(self, proposal_id: str, digest: str, source: str, tests: list[dict]) -> dict:
        original = self.get(proposal_id)
        if original["status"] != "needs_changes" or digest != original["sha256"]:
            raise HTTPException(status_code=409, detail="Only the current rejected proposal can be revised")
        if original.get("revision_number", 0) >= 2:
            raise HTTPException(status_code=409, detail="This proposal already used its two revision attempts")
        proposal = self.create(
            original["name"], original["description"], source, tests,
            replaces_tool=original.get("replaces_tool"),
        )
        proposal["revision_of"] = original["id"]
        proposal["revision_number"] = original.get("revision_number", 0) + 1
        self._write(proposal)
        return proposal

    def approve(self, proposal_id: str) -> dict:
        proposal = self.get(proposal_id)
        if proposal["status"] != "reviewed" or proposal.get("reviewed_sha256") != self._digest(proposal):
            raise HTTPException(status_code=409, detail="The reviewer must approve this proposal before owner approval")
        from agent_core.tooling import dynamic_tool_registry

        destination = settings.resolved_generated_tools_dir / f"{proposal['name']}.py"
        specs = dynamic_tool_registry.list_tool_specs()
        current = next((spec for spec in specs if spec["name"] == proposal["name"]), None)
        replacing = proposal.get("replaces_tool") == proposal["name"]
        if replacing:
            if (
                destination.is_symlink()
                or not destination.is_file()
                or current is None
                or current["source"] != destination.name
            ):
                raise HTTPException(status_code=409, detail="The generated tool changed; update proposal is stale")
        elif current is not None or destination.exists():
            raise HTTPException(status_code=409, detail="A generated tool file with this name already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        code = (
            f"TOOL_NAME = {proposal['name']!r}\n"
            f"TOOL_DESCRIPTION = {proposal['description']!r}\n"
            "TOOL_ENABLED = True\nTOOL_APPROVAL_REQUIRED = False\n\n"
            f"{proposal['source'].rstrip()}\n"
        )
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(code, encoding="utf-8")
        temporary.replace(destination)
        proposal["status"] = "approved"
        proposal["approved_at"] = datetime.now(UTC).isoformat()
        proposal["installed_as"] = destination.name
        self._write(proposal)
        return self.summary(proposal)

    @staticmethod
    def _digest(proposal: dict) -> str:
        fields = {key: proposal[key] for key in ("name", "description", "source", "tests")}
        if "replaces_tool" in proposal:
            fields["replaces_tool"] = proposal["replaces_tool"]
        payload = json.dumps(
            fields,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def summary(proposal: dict) -> dict:
        return {**{key: value for key, value in proposal.items() if key not in {"source", "tests"}}, "case_count": len(proposal["tests"])}

    def _write(self, proposal: dict) -> None:
        path = self.root / f"{proposal['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


tool_proposals = ToolProposalStore()
