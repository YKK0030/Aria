from __future__ import annotations

import hashlib
import heapq
import json
import shlex
from pathlib import Path, PurePosixPath

from agent_core.config import settings

MAX_FILE_BYTES = 250_000


class Workspace:
    def __init__(self) -> None:
        self.root = settings.resolved_agent_data_dir / "workspace"
        self.project_state = settings.resolved_agent_data_dir / "active-projects"

    def path(self, relative: str) -> Path:
        if self.root.is_symlink():
            raise ValueError("Aria's workspace root cannot be a symbolic link.")
        candidate = PurePosixPath(relative)
        if not relative or candidate.is_absolute() or ".." in candidate.parts or "\\" in relative:
            raise ValueError("Use a non-empty relative path inside Aria's workspace.")
        target = self.root.joinpath(*candidate.parts)
        if not target.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Path must stay inside Aria's workspace.")
        return target

    def list(self, relative: str = ".") -> list[str]:
        if self.root.is_symlink():
            raise ValueError("Aria's workspace root cannot be a symbolic link.")
        self.root.mkdir(parents=True, exist_ok=True)
        directory = self.root if relative == "." else self.path(relative)
        if not directory.is_dir():
            raise ValueError("Workspace directory not found.")
        return [item.name + ("/" if item.is_dir() else "") for item in heapq.nsmallest(200, directory.iterdir())]

    def read(self, relative: str) -> str:
        target = self.path(relative)
        if not target.is_file():
            raise ValueError("Workspace file not found.")
        return target.read_text(encoding="utf-8")[:20_000]

    def run_command(self, command: str) -> str:
        """Run a small read-only, shell-like command set against the workspace."""
        if len(command) > 1000:
            raise ValueError("Command is too long.")
        try:
            args = shlex.split(command)
        except ValueError as exc:
            raise ValueError("Could not parse command.") from exc
        if not args:
            raise ValueError("Command is empty.")
        name, *parts = args
        if name not in {"ls", "find", "cat", "head", "tail", "wc", "grep", "mkdir", "touch", "write", "append"}:
            raise ValueError("Allowed commands: ls, find, cat, head, tail, wc, grep, mkdir, touch, write, append.")
        allowed_options = {"ls": {"-a", "-l", "-la", "-al"}, "wc": {"-l", "-w", "-c"}, "head": {"-n"}, "tail": {"-n"}}
        if any(part.startswith("-") and part not in allowed_options.get(name, set()) for part in parts):
            raise ValueError("Command options are not allowed.")

        def checked(path: str) -> Path:
            if path.startswith("-"):
                raise ValueError("Command option is not allowed here.")
            target = self.path(path)
            if target.is_symlink() or not target.resolve().is_relative_to(self.root.resolve()):
                raise ValueError("Path must stay inside Aria's workspace and cannot be a symlink.")
            return target

        if name == "mkdir":
            if len(parts) != 1:
                raise ValueError("Usage: mkdir path")
            target = checked(parts[0])
            target.mkdir(parents=True, exist_ok=True)
            return f"Created directory {target.relative_to(self.root).as_posix()}."
        if name == "touch":
            if len(parts) != 1:
                raise ValueError("Usage: touch path")
            target = checked(parts[0])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=True)
            return f"Created file {target.relative_to(self.root).as_posix()}."
        if name in {"write", "append"}:
            if len(parts) < 2:
                raise ValueError(f"Usage: {name} path text")
            target = checked(parts[0])
            content = " ".join(parts[1:])
            if len(content.encode("utf-8")) > MAX_FILE_BYTES:
                raise ValueError(f"File content must be at most {MAX_FILE_BYTES} bytes.")
            if name == "write" and target.exists():
                raise FileExistsError("File already exists; use write_workspace_file with explicit overwrite approval to replace it.")
            if name == "append" and target.exists() and target.stat().st_size + len(content.encode("utf-8")) > MAX_FILE_BYTES:
                raise ValueError(f"File content must be at most {MAX_FILE_BYTES} bytes.")
            target.parent.mkdir(parents=True, exist_ok=True)
            if name == "write":
                target.write_text(content, encoding="utf-8")
            else:
                with target.open("a", encoding="utf-8") as stream:
                    stream.write(content)
            return f"{'Created' if name == 'write' else 'Updated'} {target.relative_to(self.root).as_posix()}."

        if name == "ls":
            if len(parts) > 2 or (parts and parts[0].startswith("-") and len(parts) == 2 and parts[0] not in {"-a", "-l", "-la", "-al"}):
                raise ValueError("Usage: ls [path] (optional -a/-l/-la)")
            relative = parts[-1] if parts and not parts[-1].startswith("-") else "."
            return "\n".join(self.list(relative))
        if name == "find":
            if len(parts) > 1:
                raise ValueError("Usage: find [path]")
            root = checked(parts[0] if parts else ".")
            if not root.is_dir():
                raise ValueError("find path must be a directory.")
            paths = heapq.nsmallest(200, (p for p in root.rglob("*") if not p.is_symlink()))
            return "\n".join(p.relative_to(self.root).as_posix() for p in paths)
        if name in {"cat", "head", "tail", "wc"}:
            count = 10
            wc_modes: list[str] = []
            if parts[:1] == ["-n"]:
                if len(parts) < 3 or not parts[1].isdigit() or not 1 <= int(parts[1]) <= 200:
                    raise ValueError("Use -n with a line count from 1 to 200.")
                count, parts = int(parts[1]), parts[2:]
            if name == "wc":
                while parts[:1] and parts[0] in {"-l", "-w", "-c"}:
                    wc_modes.append(parts.pop(0))
            if not parts or len(parts) > 5:
                raise ValueError(f"Usage: {name} [options] file [file ...]")
            output = []
            for filename in parts:
                target = checked(filename)
                if not target.is_file():
                    raise ValueError(f"Not a workspace file: {filename}")
                content = target.read_text(encoding="utf-8", errors="replace")[:20_000]
                lines = content.splitlines()
                if name == "head":
                    content = "\n".join(lines[:count])
                elif name == "tail":
                    content = "\n".join(lines[-count:])
                elif name == "wc":
                    counts = {"-l": len(lines), "-w": len(content.split()), "-c": len(content.encode("utf-8"))}
                    modes = wc_modes or ["-l", "-w", "-c"]
                    content = " ".join(str(counts[mode]) for mode in modes)
                output.append(content)
            return "\n".join(output)
        if name == "grep":
            if len(parts) != 2:
                raise ValueError("Usage: grep pattern file")
            pattern, filename = parts
            target = checked(filename)
            if not target.is_file():
                raise ValueError(f"Not a workspace file: {filename}")
            return "\n".join(line for line in target.read_text(encoding="utf-8", errors="replace")[:20_000].splitlines() if pattern.casefold() in line.casefold())
        raise ValueError("Unsupported command.")

    def write(self, relative: str, content: str, overwrite: bool = False) -> str:
        target = self.path(relative)
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"File content must be at most {MAX_FILE_BYTES} bytes.")
        if target.exists() and not overwrite:
            raise FileExistsError("File already exists. Ask before replacing it; set overwrite=true only when explicitly requested.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target.relative_to(self.root).as_posix()

    def set_active_project(self, channel: str, chat_id: str, name: str, goal: str) -> dict:
        if not name.strip() or len(name) > 100 or len(goal) > 1200:
            raise ValueError("Project name must be 1-100 characters and goal at most 1200 characters.")
        if len(PurePosixPath(name.strip()).parts) != 1:
            raise ValueError("Use a single folder name for the active project.")
        directory = self.path(name.strip())
        directory.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256(f"{channel}:{chat_id}".encode()).hexdigest()
        state = {"name": name.strip(), "path": directory.relative_to(self.root).as_posix(), "goal": goal.strip()[:1200]}
        self.project_state.mkdir(parents=True, exist_ok=True)
        target = self.project_state / f"{identity}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        temporary.replace(target)
        return state

    def get_active_project(self, channel: str, chat_id: str) -> dict | None:
        identity = hashlib.sha256(f"{channel}:{chat_id}".encode()).hexdigest()
        try:
            state = json.loads((self.project_state / f"{identity}.json").read_text(encoding="utf-8"))
            if isinstance(state, dict) and isinstance(state.get("path"), str) and isinstance(state.get("goal"), str):
                return state
        except (OSError, json.JSONDecodeError):
            return None
        return None


workspace = Workspace()
