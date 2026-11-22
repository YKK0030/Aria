from pathlib import Path

from agent_core.config import settings


PROMPT_DIR = Path(__file__).parent

_TASK_MARKERS = {
    "tool_creation": ("create a tool", "make a tool", "build a tool", "propose_task_tool"),
    "robotics": ("robot", "robotics", "robotic", "manipulator", "kinematics", "ros2", "motion planning"),
    "research": ("search", "look up", "latest", "current", "research", "http://", "https://"),
    "coding": (
        "code", "coding", "debug", "traceback", "exception", "implement", "fix this", "python", "typescript",
        "html", "web page", "website", "new project", "project folder", "create a folder", "create a file",
    ),
    "writing": ("write", "draft", "rewrite", "compose", "email", "blog post"),
}


def select_task_prompt(task: str) -> str:
    lowered = task.lower()
    return next(
        (name for name, markers in _TASK_MARKERS.items() if any(marker in lowered for marker in markers)),
        "general",
    )


def build_system_prompt(task: str = "") -> str:
    template = (PROMPT_DIR / "system.md").read_text(encoding="utf-8").strip()
    task_prompt = select_task_prompt(task)
    task_file = PROMPT_DIR / f"{task_prompt}.md"
    task_rules = task_file.read_text(encoding="utf-8").strip() if task_file.exists() else ""
    return "\n\n".join(part for part in (settings.system_prompt.strip(), template, task_rules) if part)


__all__ = ["build_system_prompt", "select_task_prompt"]
