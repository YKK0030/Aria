from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from agent_core.config import settings


@dataclass
class SkillInteraction:
    skill_name: str
    channel: str
    chat_id: str
    timestamp: float
    success: bool
    user_feedback: str | None = None
    tools_used: list[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class SkillPreference:
    channel: str
    chat_id: str
    skill_scores: dict[str, float] = field(default_factory=dict)
    total_interactions: dict[str, int] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

    def get_score(self, skill: str) -> float:
        return self.skill_scores.get(skill, 0.0)

    def record_interaction(self, skill: str, success: bool) -> None:
        self.total_interactions[skill] = self.total_interactions.get(skill, 0) + 1
        current = self.skill_scores.get(skill, 0.5)
        # Exponential moving average
        alpha = 0.3
        self.skill_scores[skill] = current * (1 - alpha) + (1.0 if success else 0.0) * alpha
        self.last_updated = time.time()


class SkillLearning:
    def __init__(self) -> None:
        self.data_dir = Path(settings.resolved_agent_data_dir) / "skill_learning"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._preferences: dict[str, SkillPreference] = {}
        self._interactions: list[SkillInteraction] = []

    def _key(self, channel: str, chat_id: str) -> str:
        return f"{channel}:{chat_id}"

    def get_preference(self, channel: str, chat_id: str) -> SkillPreference:
        key = self._key(channel, chat_id)
        if key not in self._preferences:
            self._preferences[key] = self._load_preference(channel, chat_id)
        return self._preferences[key]

    def record_interaction(
        self,
        skill_name: str,
        channel: str,
        chat_id: str,
        success: bool,
        user_feedback: str | None = None,
        tools_used: list[str] | None = None,
        duration_ms: int = 0,
    ) -> None:
        interaction = SkillInteraction(
            skill_name=skill_name,
            channel=channel,
            chat_id=chat_id,
            timestamp=time.time(),
            success=success,
            user_feedback=user_feedback,
            tools_used=tools_used or [],
            duration_ms=duration_ms,
        )
        self._interactions.append(interaction)

        pref = self.get_preference(channel, chat_id)
        pref.record_interaction(skill_name, success)
        self._save_preference(pref)

        # Keep only recent interactions in memory
        if len(self._interactions) > 1000:
            self._interactions = self._interactions[-500:]

    def get_skill_ranking(self, channel: str, chat_id: str) -> list[tuple[str, float]]:
        pref = self.get_preference(channel, chat_id)
        return sorted(pref.skill_scores.items(), key=lambda x: x[1], reverse=True)

    def should_suggest_skill(self, channel: str, chat_id: str, skill: str, threshold: float = 0.6) -> bool:
        score = self.get_preference(channel, chat_id).get_score(skill)
        return score >= threshold

    def get_suggested_skills(self, channel: str, chat_id: str, top_k: int = 3) -> list[str]:
        ranking = self.get_skill_ranking(channel, chat_id)
        return [skill for skill, score in ranking[:top_k] if score > 0.5]

    def _pref_path(self, channel: str, chat_id: str) -> Path:
        safe_chat = "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in chat_id)
        return self.data_dir / f"pref_{channel}_{safe_chat}.json"

    def _load_preference(self, channel: str, chat_id: str) -> SkillPreference:
        path = self._pref_path(channel, chat_id)
        if not path.exists():
            return SkillPreference(channel=channel, chat_id=chat_id)
        try:
            data = json.loads(path.read_text())
            return SkillPreference(**data)
        except Exception:
            return SkillPreference(channel=channel, chat_id=chat_id)

    def _save_preference(self, pref: SkillPreference) -> None:
        path = self._pref_path(pref.channel, pref.chat_id)
        try:
            path.write_text(json.dumps(asdict(pref), indent=2))
        except Exception:
            pass

    def get_stats(self, channel: str | None = None, chat_id: str | None = None) -> dict[str, Any]:
        interactions = self._interactions
        if channel:
            interactions = [i for i in interactions if i.channel == channel]
        if chat_id:
            interactions = [i for i in interactions if i.chat_id == chat_id]

        by_skill: dict[str, dict] = defaultdict(lambda: {"total": 0, "success": 0, "avg_duration": 0})
        for i in interactions:
            by_skill[i.skill_name]["total"] += 1
            if i.success:
                by_skill[i.skill_name]["success"] += 1
            by_skill[i.skill_name]["avg_duration"] = (
                by_skill[i.skill_name]["avg_duration"] * (by_skill[i.skill_name]["total"] - 1) + i.duration_ms
            ) / by_skill[i.skill_name]["total"]

        return {
            "total_interactions": len(interactions),
            "by_skill": {
                skill: {**stats, "success_rate": stats["success"] / stats["total"] if stats["total"] else 0}
                for skill, stats in by_skill.items()
            },
        }


skill_learning = SkillLearning()
