from __future__ import annotations

import hashlib
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

    def create(
        self,
        action: str,
        summary: str,
        details: str,
        requested_by: dict,
        parameters: dict | None = None,
    ) -> dict:
        action = action.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", action):
            raise HTTPException(status_code=422, detail="Action must be a short identifier")
        if not summary.strip() or len(summary) > 300:
            raise HTTPException(status_code=422, detail="Summary must be 1-300 characters")
        if not details.strip() or len(details) > 5000:
            raise HTTPException(status_code=422, detail="Details must be 1-5000 characters")
        if parameters is not None and (
            not isinstance(parameters, dict)
            or action != "send_message"
            or set(parameters) != {"channel", "chat_id", "text"}
            or not isinstance(parameters.get("channel"), str)
            or parameters.get("channel") not in {"telegram", "whatsapp"}
            or not isinstance(parameters.get("chat_id"), str)
            or not parameters["chat_id"].strip()
            or len(parameters["chat_id"]) > 128
            or not isinstance(parameters.get("text"), str)
            or not parameters["text"].strip()
            or len(parameters["text"]) > 1000
        ):
            raise HTTPException(status_code=422, detail="Invalid approved message parameters")
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
        if parameters is not None:
            record["parameters"] = parameters
            record["parameters_sha256"] = self._parameters_sha256(parameters)
            record["execution_status"] = "pending"
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
            path = self.root / f"{request_id}.json"
        except ValueError:
            if not re.fullmatch(r"[0-9a-f]{8,32}", request_id):
                raise HTTPException(status_code=404, detail="Approval request not found")
            matches = list(self.root.glob(f"{request_id}*.json"))
            if len(matches) > 1:
                raise HTTPException(status_code=409, detail="Approval ID is ambiguous; use the full ID")
            path = matches[0] if matches else self.root / f"{request_id}.json"
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

    def claim_execution(self, request_id: str) -> dict:
        record = self.get(request_id)
        if record["status"] != "approved" or record.get("execution_status") != "pending":
            raise HTTPException(status_code=409, detail="Approval is not ready for execution")
        parameters = record.get("parameters")
        if (
            record.get("action") != "send_message"
            or not isinstance(parameters, dict)
            or self._parameters_sha256(parameters) != record.get("parameters_sha256")
        ):
            raise HTTPException(status_code=409, detail="Approved action parameters no longer match")
        if datetime.fromisoformat(record["expires_at"]) <= datetime.now(UTC):
            record["status"] = "expired"
            self._write(record)
            raise HTTPException(status_code=409, detail="Approval request expired")
        record["execution_status"] = "executing"
        record["execution_started_at"] = datetime.now(UTC).isoformat()
        self._write(record)
        return record

    def finish_execution(self, request_id: str, succeeded: bool, error_type: str | None = None) -> dict:
        record = self.get(request_id)
        if record.get("execution_status") != "executing":
            raise HTTPException(status_code=409, detail="Approval action is not executing")
        record["execution_status"] = "succeeded" if succeeded else "failed"
        record["executed_at"] = datetime.now(UTC).isoformat()
        if error_type:
            record["execution_error_type"] = error_type[:80]
        self._write(record)
        return record

    @staticmethod
    def _parameters_sha256(parameters: dict) -> str:
        encoded = json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _write(self, record: dict) -> None:
        path = self.root / f"{record['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


approval_store = ApprovalStore()
