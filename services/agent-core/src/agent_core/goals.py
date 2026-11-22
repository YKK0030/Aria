from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from enum import Enum

from agent_core.config import settings
from agent_core.memory import long_term_memory
from agent_core.storage import store


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ABANDONED = "abandoned"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    SKIPPED = "skipped"


@dataclass
class Milestone:
    id: str
    goal_id: str
    title: str
    description: str
    status: MilestoneStatus = MilestoneStatus.PENDING
    due_date: str | None = None
    completed_at: str | None = None
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Milestone":
        return cls(**data)


@dataclass
class Goal:
    id: str
    channel: str
    chat_id: str
    title: str
    description: str
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    target_date: str | None = None
    milestones: list[Milestone] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    progress: float = 0.0  # 0-1

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["milestones"] = [m.to_dict() for m in self.milestones]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        milestones = [Milestone.from_dict(m) for m in data.get("milestones", [])]
        data["milestones"] = milestones
        return cls(**data)

    def recalc_progress(self) -> None:
        if not self.milestones:
            self.progress = 0.0
            return
        done = sum(1 for m in self.milestones if m.status == MilestoneStatus.DONE)
        self.progress = done / len(self.milestones)
        if self.progress >= 1.0 and self.status == GoalStatus.ACTIVE:
            self.status = GoalStatus.COMPLETED
            self.completed_at = datetime.now(UTC).isoformat()


class GoalManager:
    def __init__(self) -> None:
        self.goals_dir = Path(settings.resolved_agent_data_dir) / "goals"
        self.goals_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Goal] = {}

    def _goal_path(self, channel: str, chat_id: str, goal_id: str) -> Path:
        safe_chat = "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in chat_id)
        return self.goals_dir / f"{channel}_{safe_chat}_{goal_id}.json"

    def _index_path(self, channel: str, chat_id: str) -> Path:
        safe_chat = "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in chat_id)
        return self.goals_dir / f"{channel}_{safe_chat}_index.json"

    def create_goal(
        self,
        channel: str,
        chat_id: str,
        title: str,
        description: str,
        target_date: str | None = None,
        milestones: list[dict[str, Any]] | None = None,
    ) -> Goal:
        goal = Goal(
            id=uuid.uuid4().hex[:12],
            channel=channel,
            chat_id=chat_id,
            title=title,
            description=description,
            target_date=target_date,
            milestones=[
                Milestone(
                    id=uuid.uuid4().hex[:8],
                    goal_id="",
                    title=m.get("title", ""),
                    description=m.get("description", ""),
                    due_date=m.get("due_date"),
                    order=i,
                )
                for i, m in enumerate(milestones or [])
            ],
        )
        for m in goal.milestones:
            m.goal_id = goal.id
        goal.recalc_progress()
        self._save_goal(goal)
        self._update_index(channel, chat_id, goal.id, "add")

        # Store in long-term memory for retrieval
        long_term_memory.add_node(
            channel=channel,
            chat_id=chat_id,
            role="goal",
            text=f"Goal: {title}\n{description}",
            source_message_id=goal.id,
        )

        store.append_audit("goal_created", {"goal": goal.to_dict()})
        return goal

    def get_goal(self, channel: str, chat_id: str, goal_id: str) -> Goal | None:
        cache_key = f"{channel}:{chat_id}:{goal_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._goal_path(channel, chat_id, goal_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            goal = Goal.from_dict(data)
            self._cache[cache_key] = goal
            return goal
        except Exception:
            return None

    def list_goals(self, channel: str, chat_id: str, status: GoalStatus | None = None) -> list[Goal]:
        index_path = self._index_path(channel, chat_id)
        if not index_path.exists():
            return []
        try:
            index = json.loads(index_path.read_text())
            goal_ids = index.get("goals", [])
            goals = []
            for gid in goal_ids:
                goal = self.get_goal(channel, chat_id, gid)
                if goal and (status is None or goal.status == status):
                    goals.append(goal)
            return sorted(goals, key=lambda g: g.updated_at, reverse=True)
        except Exception:
            return []

    def update_goal(self, channel: str, chat_id: str, goal_id: str, **kwargs) -> Goal | None:
        goal = self.get_goal(channel, chat_id, goal_id)
        if not goal:
            return None

        for key, value in kwargs.items():
            if hasattr(goal, key):
                setattr(goal, key, value)

        goal.updated_at = datetime.now(UTC).isoformat()
        goal.recalc_progress()
        self._save_goal(goal)
        store.append_audit("goal_updated", {"goal_id": goal_id, "changes": kwargs})
        return goal

    def add_milestone(self, channel: str, chat_id: str, goal_id: str, title: str, description: str = "", due_date: str | None = None) -> Milestone | None:
        goal = self.get_goal(channel, chat_id, goal_id)
        if not goal:
            return None

        milestone = Milestone(
            id=uuid.uuid4().hex[:8],
            goal_id=goal_id,
            title=title,
            description=description,
            due_date=due_date,
            order=len(goal.milestones),
        )
        goal.milestones.append(milestone)
        goal.updated_at = datetime.now(UTC).isoformat()
        goal.recalc_progress()
        self._save_goal(goal)
        return milestone

    def update_milestone(self, channel: str, chat_id: str, goal_id: str, milestone_id: str, **kwargs) -> Milestone | None:
        goal = self.get_goal(channel, chat_id, goal_id)
        if not goal:
            return None

        for m in goal.milestones:
            if m.id == milestone_id:
                for key, value in kwargs.items():
                    if hasattr(m, key):
                        setattr(m, key, value)
                if m.status == MilestoneStatus.DONE and not m.completed_at:
                    m.completed_at = datetime.now(UTC).isoformat()
                goal.updated_at = datetime.now(UTC).isoformat()
                goal.recalc_progress()
                self._save_goal(goal)
                return m
        return None

    def delete_goal(self, channel: str, chat_id: str, goal_id: str) -> bool:
        path = self._goal_path(channel, chat_id, goal_id)
        if path.exists():
            path.unlink()
        self._update_index(channel, chat_id, goal_id, "remove")
        cache_key = f"{channel}:{chat_id}:{goal_id}"
        self._cache.pop(cache_key, None)
        store.append_audit("goal_deleted", {"goal_id": goal_id})
        return True

    def get_active_goals(self, channel: str, chat_id: str) -> list[Goal]:
        return self.list_goals(channel, chat_id, GoalStatus.ACTIVE)

    def get_goals_due_soon(self, channel: str, chat_id: str, days: int = 7) -> list[Goal]:
        cutoff = datetime.now(UTC) + timedelta(days=days)
        goals = self.get_active_goals(channel, chat_id)
        due_soon = []
        for g in goals:
            if g.target_date:
                try:
                    target = datetime.fromisoformat(g.target_date.replace("Z", "+00:00"))
                    if target <= cutoff:
                        due_soon.append(g)
                except Exception:
                    pass
            for m in g.milestones:
                if m.due_date and m.status != MilestoneStatus.DONE:
                    try:
                        due = datetime.fromisoformat(m.due_date.replace("Z", "+00:00"))
                        if due <= cutoff:
                            due_soon.append(g)
                            break
                    except Exception:
                        pass
        return due_soon

    def _save_goal(self, goal: Goal) -> None:
        path = self._goal_path(goal.channel, goal.chat_id, goal.id)
        try:
            path.write_text(json.dumps(goal.to_dict(), indent=2))
        except Exception:
            pass

    def _update_index(self, channel: str, chat_id: str, goal_id: str, action: str) -> None:
        index_path = self._index_path(channel, chat_id)
        index = {"goals": []}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text())
            except Exception:
                pass

        goals = index.get("goals", [])
        if action == "add" and goal_id not in goals:
            goals.append(goal_id)
        elif action == "remove" and goal_id in goals:
            goals.remove(goal_id)
        index["goals"] = goals
        try:
            index_path.write_text(json.dumps(index, indent=2))
        except Exception:
            pass


goal_manager = GoalManager()
