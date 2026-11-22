from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
import yaml


@dataclass
class SkillActivation:
    keywords: list[str] = field(default_factory=list)
    file_extensions: list[str] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)
    auto_trigger: bool = True


@dataclass
class SkillModelPrefs:
    preferred: str = "groq_complex"
    fallback: str = "groq_simple"
    temperature: float = 0.2


@dataclass
class SkillConfig:
    max_file_size_kb: int = 100
    allow_shell: bool = False
    sandbox_profile: str = "default"


@dataclass
class SkillManifest:
    name: str
    version: str
    description: str
    category: str
    activation: SkillActivation
    tools: list[str] = field(default_factory=list)
    prompt_files: dict[str, str] = field(default_factory=dict)
    models: SkillModelPrefs = field(default_factory=SkillModelPrefs)
    config: SkillConfig = field(default_factory=SkillConfig)
    evals: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> SkillManifest:
        with path.open() as f:
            data = yaml.safe_load(f)
        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            category=data["category"],
            activation=SkillActivation(**data.get("activation", {})),
            tools=data.get("tools", []),
            prompt_files=data.get("prompts", {}),
            models=SkillModelPrefs(**data.get("models", {})),
            config=SkillConfig(**data.get("config", {})),
            evals=data.get("evals", []),
            dependencies=data.get("dependencies", []),
            conflicts=data.get("conflicts", []),
        )


@dataclass
class LoadedSkill:
    manifest: SkillManifest
    skill_dir: Path
    system_prompt_addition: str = ""
    task_prompts: dict[str, str] = field(default_factory=dict)


ModelProvider = Literal["groq", "ollama", "nvidia"]
