from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import HTTPException

from agent_core.config import settings


SOURCE_PREFIX = "services/agent-core/src/agent_core/"
PROTECTED_FILES = {"config.py", "policy.py", "storage.py"}
PROTECTED_DIRS = {"memory", "prompts"}


def is_allowed_source_path(path: str) -> bool:
    pure_path = PurePosixPath(path)
    return bool(
        not pure_path.is_absolute()
        and ".." not in pure_path.parts
        and "\\" not in path
        and path.startswith(SOURCE_PREFIX)
        and path.endswith(".py")
        and pure_path.name not in PROTECTED_FILES
        and not (set(pure_path.parts) & PROTECTED_DIRS)
    )


class CodeChangeStore:
    def __init__(self) -> None:
        self.root = settings.resolved_tool_proposals_dir.parent / "code-change-proposals"

    @staticmethod
    def validate_patch(patch: str) -> None:
        if not patch.strip() or len(patch.encode()) > 100_000:
            raise HTTPException(status_code=422, detail="Patch must be 1-100000 bytes")
        paths = re.findall(r"^diff --git a/(\S+) b/(\S+)$", patch, re.MULTILINE)
        if not paths or any(left != right or not is_allowed_source_path(left) for left, right in paths):
            raise HTTPException(status_code=422, detail="Patch may change only unprotected agent-core Python source files")
        if len(paths) > 16 or len(set(paths)) != len(paths):
            raise HTTPException(status_code=422, detail="Patch contains duplicate or more than 16 file entries")
        if re.search(r"^(?:new file mode|deleted file mode|rename from|rename to|GIT binary patch)", patch, re.MULTILINE):
            raise HTTPException(status_code=422, detail="New, deleted, renamed, or binary files are not allowed")
        headers = re.findall(r"^---\s+([^\t\n]+)\n\+\+\+\s+([^\t\n]+)", patch, re.MULTILINE)
        if len(headers) != len(paths):
            raise HTTPException(status_code=422, detail="Patch file headers do not match its diff entries")
        for old_path, new_path in headers:
            old_path = old_path.removeprefix("a/")
            new_path = new_path.removeprefix("b/")
            if old_path != new_path or old_path not in {left for left, _ in paths}:
                raise HTTPException(status_code=422, detail="Patch contains a protected or unsupported path")

    @staticmethod
    def list_source_files() -> list[str]:
        source_root = Path(__file__).resolve().parents[1]
        return sorted(
            f"{SOURCE_PREFIX}{path.relative_to(source_root).as_posix()}"
            for path in source_root.rglob("*.py")
            if not path.is_symlink() and is_allowed_source_path(
                f"{SOURCE_PREFIX}{path.relative_to(source_root).as_posix()}"
            )
        )

    @staticmethod
    def read_source_file(path: str) -> str:
        if not is_allowed_source_path(path):
            raise HTTPException(status_code=422, detail="That source path is protected or unsupported")
        source_root = Path(__file__).resolve().parents[2]
        relative_path = PurePosixPath(path).relative_to("services/agent-core/src")
        target = source_root.joinpath(*relative_path.parts)
        if target.is_symlink() or not target.is_file():
            raise HTTPException(status_code=404, detail="Source file not found")
        try:
            content = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise HTTPException(status_code=404, detail="Source file could not be read") from error
        return content[:20_000]

    def create(self, description: str, patch: str) -> dict:
        if not description.strip() or len(description) > 1000:
            raise HTTPException(status_code=422, detail="Description must be 1-1000 characters")
        self.validate_patch(patch)
        proposal = {
            "id": str(uuid4()),
            "description": description.strip(),
            "patch": patch,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
        }
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
            raise HTTPException(status_code=404, detail="Code change proposal not found") from error
        path = self.root / f"{proposal_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Code change proposal not found")
        proposal = self._read(path)
        if proposal["sha256"] != self._digest(proposal):
            raise HTTPException(status_code=409, detail="Proposal was modified")
        self.validate_patch(proposal["patch"])
        return proposal

    def record_review(self, proposal_id: str, digest: str, review: dict) -> dict:
        proposal = self.get(proposal_id)
        if proposal["status"] != "pending" or digest != proposal["sha256"]:
            raise HTTPException(status_code=409, detail="Proposal revision is not eligible for review")
        if not isinstance(review.get("approved"), bool) or not isinstance(review.get("summary"), str) or not isinstance(review.get("findings"), list):
            raise HTTPException(status_code=422, detail="Invalid code review result")
        proposal["review"] = review
        proposal["reviewed_at"] = datetime.now(UTC).isoformat()
        proposal["reviewed_sha256"] = digest
        proposal["status"] = "reviewed" if review["approved"] and not review["findings"] else "needs_changes"
        self._write(proposal)
        return self.summary(proposal)

    @staticmethod
    def _digest(proposal: dict) -> str:
        return hashlib.sha256(json.dumps(
            {key: proposal[key] for key in ("description", "patch")},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()

    @staticmethod
    def summary(proposal: dict) -> dict:
        return {key: value for key, value in proposal.items() if key != "patch"}

    def _write(self, proposal: dict) -> None:
        path = self.root / f"{proposal['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


code_changes = CodeChangeStore()
