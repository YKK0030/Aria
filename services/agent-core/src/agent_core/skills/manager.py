from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent_core.config import settings
from agent_core.skills.types import LoadedSkill, SkillManifest, ModelProvider
from agent_core.skills.learning import skill_learning
from agent_core.metrics import record_skill_activation, record_skill_score

logger = logging.getLogger(__name__)


class SkillManager:
    def __init__(self) -> None:
        self.loaded_skills: dict[str, LoadedSkill] = {}
        # Find the skill bundle from either the repository or container image.
        current = Path(__file__).resolve()
        for parent in current.parents:
            if any((parent / "skills").glob("*/manifest.yaml")):
                self.skills_root = parent / "skills"
                break
        else:
            self.skills_root = Path("/home/yadnit/personal_projects/Aria/skills")
        self.registry: dict[str, SkillManifest] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        self.registry.clear()
        if not self.skills_root.exists():
            return
        for skill_dir in self.skills_root.iterdir():
            if not skill_dir.is_dir():
                continue
            manifest_path = skill_dir / "manifest.yaml"
            if not manifest_path.exists():
                continue
            try:
                manifest = SkillManifest.from_yaml(manifest_path)
                self.registry[manifest.name] = manifest
            except Exception as e:
                logger.warning("Failed to load skill manifest %s: %s", manifest_path, e)

    def list_available(self) -> list[dict[str, Any]]:
        return [
            {
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "category": m.category,
                "loaded": m.name in self.loaded_skills,
            }
            for m in self.registry.values()
        ]

    def ensure_skills_for_event(
        self, channel: str, chat_id: str, text: str, workspace_files: list[str] | None = None
    ) -> list[str]:
        scores: dict[str, float] = {}
        text_lower = text.lower()

        # Get learned preferences
        suggested_skills = skill_learning.get_suggested_skills(channel, chat_id, top_k=5)

        for name, manifest in self.registry.items():
            if name in self.loaded_skills:
                continue
            if any(c in self.loaded_skills for c in manifest.conflicts):
                continue

            score = 0.0
            # Keyword matching
            for kw in manifest.activation.keywords:
                if kw.lower() in text_lower:
                    score += 2.0
            # File extension matching
            if manifest.activation.file_extensions and workspace_files:
                for ext in manifest.activation.file_extensions:
                    if any(f.endswith(ext) for f in workspace_files):
                        score += 3.0
            # Channel affinity
            if channel in manifest.activation.channels:
                score += 1.0
            # Learned preference boost
            if name in suggested_skills:
                score += 5.0  # Strong boost for learned preferences

            if score >= 3.0:
                scores[name] = score

        selected = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)[:3]
        for name in selected:
            self.load_skill(name, channel, chat_id)
            # Record activation
            trigger = "learned" if name in suggested_skills else "keyword"
            record_skill_activation(name, trigger)
            # Record current score
            pref = skill_learning.get_preference(channel, chat_id)
            record_skill_score(channel, chat_id, name, pref.get_score(name))
        return list(self.loaded_skills.keys())

    def load_skill(self, name: str, channel: str, chat_id: str) -> LoadedSkill | None:
        if name in self.loaded_skills:
            return self.loaded_skills[name]
        manifest = self.registry.get(name)
        if not manifest:
            return None

        for dep in manifest.dependencies:
            if dep not in self.loaded_skills:
                self.load_skill(dep, channel, chat_id)

        skill_dir = self.skills_root / name
        system_prompt = ""
        task_prompts = {}

        for key, rel_path in manifest.prompt_files.items():
            prompt_path = skill_dir / rel_path
            if prompt_path.exists():
                content = prompt_path.read_text(encoding="utf-8")
                if key == "system":
                    system_prompt = content
                else:
                    task_prompts[key] = content

        loaded = LoadedSkill(
            manifest=manifest,
            skill_dir=skill_dir,
            system_prompt_addition=system_prompt,
            task_prompts=task_prompts,
        )
        self.loaded_skills[name] = loaded
        logger.info("Loaded skill: %s for %s/%s", name, channel, chat_id)
        return loaded

    def unload_skill(self, name: str) -> bool:
        if name in self.loaded_skills:
            del self.loaded_skills[name]
            return True
        return False

    def compose_system_prompt(self, base: str) -> str:
        additions = [s.system_prompt_addition for s in self.loaded_skills.values() if s.system_prompt_addition]
        if not additions:
            return base
        return base + "\n\n" + "\n\n".join(additions)

    def get_model_preferences(self) -> dict[str, Any]:
        prefs = {"preferred": "groq_complex", "fallback": "groq_simple", "temperature": 0.2}
        for skill in self.loaded_skills.values():
            m = skill.manifest.models
            prefs["preferred"] = m.preferred
            prefs["fallback"] = m.fallback
            prefs["temperature"] = m.temperature
        return prefs

    def get_active_skills(self) -> list[str]:
        return list(self.loaded_skills.keys())

    def clear_for_chat(self) -> None:
        self.loaded_skills.clear()


skill_manager = SkillManager()
