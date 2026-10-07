from pathlib import Path

from agent_core.config import settings


PROMPT_DIR = Path(__file__).parent


def build_system_prompt() -> str:
    template = (PROMPT_DIR / "system.md").read_text(encoding="utf-8").strip()
    return f"{settings.system_prompt}\n{template}"


__all__ = ["build_system_prompt"]
