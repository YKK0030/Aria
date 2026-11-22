from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException

from agent_core.config import settings


class ApprovalStore:
    """Durable owner decisions for proposed sensitive actions; never executes them."""

    def __init__(self) -> None:
        self.root = settings.resolved_agent_data_dir / "approvals"

    def create(self, action: str, summary: str, details: str, requested_by: dict) -> dict:
        action = action.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", action):
            raise HTTPException(status_code=422, detail="Action must be a short identifier")
        if not summary.strip() or len(summary) > 300:
            raise HTTPException(status_code=422, detail="Summary must be 1-300 characters")
        if not details.strip() or len(details) > 5000:
            raise HTTPException(status_code=422, detail="Details must be 1-5000 characters")
        record = {
            "id": str(uuid4()),
            "action": action,
            "summary": summary.strip(),
            "details": details.strip(),
            "requested_by": {
                "channel": str(requested_by.get("channel", "unknown"))[:32],
                "chat_id": str(requested_by.get("chat_id", ""))[:128],
            },
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self._write(record)
        return record

    def list(self, status: str | None = None) -> list[dict]:
        self.root.mkdir(parents=True, exist_ok=True)
        records = [self._read(path) for path in self.root.glob("*.json")]
        if status:
            records = [record for record in records if record["status"] == status]
        return sorted(records, key=lambda record: record["created_at"], reverse=True)

    def get(self, request_id: str) -> dict:
        try:
            UUID(request_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Approval request not found") from error
        path = self.root / f"{request_id}.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Approval request not found")
        return self._read(path)

    def decide(self, request_id: str, decision: str, decided_by: str) -> dict:
        if decision not in {"approved", "rejected"}:
            raise HTTPException(status_code=422, detail="Decision must be approved or rejected")
        record = self.get(request_id)
        if record["status"] != "pending":
            raise HTTPException(status_code=409, detail="Approval request is no longer pending")
        if datetime.fromisoformat(record["expires_at"]) <= datetime.now(UTC):
            record["status"] = "expired"
            self._write(record)
            raise HTTPException(status_code=409, detail="Approval request expired")
        record["status"] = decision
        record["decided_at"] = datetime.now(UTC).isoformat()
        record["decided_by"] = decided_by[:128]
        self._write(record)
        return record

    def _write(self, record: dict) -> None:
        path = self.root / f"{record['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


approval_store = ApprovalStore()
