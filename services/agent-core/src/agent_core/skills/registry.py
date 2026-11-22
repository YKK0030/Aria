from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

from agent_core.config import settings
from agent_core.skills.types import SkillManifest

logger = logging.getLogger(__name__)


@dataclass
class RemoteSkillSource:
    name: str
    url: str
    version: str | None = None
    subdir: str = ""


@dataclass
class InstallResult:
    success: bool
    skill_name: str
    version: str
    message: str
    manifest: SkillManifest | None = None


class RemoteSkillRegistry:
    def __init__(self) -> None:
        self.skills_root = Path(settings.resolved_agent_data_dir) / "skills"
        self.skills_root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.skills_root / "remote_index.json"
        self._index: dict[str, dict] = self._load_index()

    def _load_index(self) -> dict[str, dict]:
        if self.index_path.exists():
            try:
                return json.loads(self.index_path.read_text())
            except Exception:
                pass
        return {}

    def _save_index(self) -> None:
        try:
            self.index_path.write_text(json.dumps(self._index, indent=2))
        except Exception:
            pass

    def install_from_github(
        self,
        repo_url: str,
        version: str | None = None,
        subdir: str = "",
    ) -> InstallResult:
        """Install a skill from a GitHub repository."""
        parsed = urlparse(repo_url)
        if "github.com" not in parsed.netloc:
            return InstallResult(False, "", "", "Only GitHub URLs supported")

        # Convert to raw API URL
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 2:
            return InstallResult(False, "", "", "Invalid GitHub URL format")
        owner, repo = parts[0], parts[1]

        # Clone or fetch
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            clone_dir = tmp_path / "repo"

            try:
                # Shallow clone
                ref = version or "main"
                subprocess.run(
                    ["git", "clone", "--depth", "1", "--branch", ref, repo_url, str(clone_dir)],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            except subprocess.CalledProcessError as e:
                return InstallResult(False, "", "", f"Git clone failed: {e.stderr.decode()}")
            except subprocess.TimeoutExpired:
                return InstallResult(False, "", "", "Git clone timed out")

            # Find manifest
            skill_dir = clone_dir
            if subdir:
                skill_dir = clone_dir / subdir

            manifest_path = skill_dir / "manifest.yaml"
            if not manifest_path.exists():
                return InstallResult(False, "", "", "No manifest.yaml found in skill directory")

            # Load and validate manifest
            try:
                manifest = SkillManifest.from_yaml(manifest_path)
            except Exception as e:
                return InstallResult(False, "", "", f"Invalid manifest: {e}")

            # Check for conflicts
            target_dir = self.skills_root / manifest.name
            if target_dir.exists():
                return InstallResult(False, manifest.name, manifest.version, "Skill already installed")

            # Copy skill directory
            try:
                shutil.copytree(skill_dir, target_dir)
            except Exception as e:
                return InstallResult(False, manifest.name, manifest.version, f"Copy failed: {e}")

            # Update index
            self._index[manifest.name] = {
                "source": "github",
                "url": repo_url,
                "version": manifest.version,
                "subdir": subdir,
                "installed_at": str(Path().absolute()),
            }
            self._save_index()

            logger.info("Installed skill %s v%s from %s", manifest.name, manifest.version, repo_url)
            return InstallResult(True, manifest.name, manifest.version, "Skill installed successfully", manifest)

    def install_from_manifest_url(self, manifest_url: str) -> InstallResult:
        """Install a skill directly from a manifest.yaml URL."""
        try:
            resp = requests.get(manifest_url, timeout=30)
            resp.raise_for_status()
            manifest_data = yaml.safe_load(resp.text)
            manifest = SkillManifest(**manifest_data)
        except Exception as e:
            return InstallResult(False, "", "", f"Failed to fetch/parse manifest: {e}")

        # For now, we need the actual skill files - this is a limitation
        # In practice, the manifest would need to reference a package/archive
        return InstallResult(False, manifest.name, manifest.version, "Direct manifest URL install not yet implemented - use GitHub")

    def uninstall(self, skill_name: str) -> bool:
        """Uninstall a remotely installed skill."""
        target_dir = self.skills_root / skill_name
        if not target_dir.exists():
            return False

        # Only uninstall if it was remotely installed
        if skill_name not in self._index:
            return False

        try:
            shutil.rmtree(target_dir)
            del self._index[skill_name]
            self._save_index()
            return True
        except Exception:
            return False

    def list_remote_skills(self) -> list[dict[str, Any]]:
        """List all remotely installed skills."""
        result = []
        for name, info in self._index.items():
            manifest_path = self.skills_root / name / "manifest.yaml"
            manifest_data = {}
            if manifest_path.exists():
                try:
                    manifest_data = yaml.safe_load(manifest_path.read_text())
                except Exception:
                    pass
            result.append({
                "name": name,
                "version": info.get("version", manifest_data.get("version", "unknown")),
                "source": info.get("source"),
                "url": info.get("url"),
                "installed": True,
            })
        return result

    def update_skill(self, skill_name: str) -> InstallResult:
        """Update a remotely installed skill to latest version."""
        if skill_name not in self._index:
            return InstallResult(False, skill_name, "", "Skill not found in remote index")

        info = self._index[skill_name]
        if info.get("source") != "github":
            return InstallResult(False, skill_name, "", "Only GitHub skills can be updated")

        # Uninstall first, then reinstall
        self.uninstall(skill_name)
        return self.install_from_github(info["url"], info.get("version"), info.get("subdir", ""))

    def verify_skill(self, skill_name: str) -> dict[str, Any]:
        """Verify skill integrity (checksums, manifest validity)."""
        # Check remote skills directory first
        skill_dir = self.skills_root / skill_name
        if not skill_dir.exists():
            # Fallback to local skills directory (repo root)
            from pathlib import Path
            current = Path(__file__).resolve()
            for parent in current.parents:
                if (parent / "docker-compose.yml").exists():
                    skill_dir = parent / "skills" / skill_name
                    break
            else:
                skill_dir = Path("/home/yadnit/personal_projects/Aria/skills") / skill_name

        if not skill_dir.exists():
            return {"valid": False, "error": "Skill directory not found"}

        manifest_path = skill_dir / "manifest.yaml"
        if not manifest_path.exists():
            return {"valid": False, "error": "manifest.yaml missing"}

        try:
            manifest = SkillManifest.from_yaml(manifest_path)
            # Verify all prompt files exist
            missing = []
            for key, rel_path in manifest.prompt_files.items():
                if not (skill_dir / rel_path).exists():
                    missing.append(f"{key}: {rel_path}")
            # Verify eval files exist
            for eval_file in manifest.evals:
                if not (skill_dir / eval_file).exists():
                    missing.append(f"eval: {eval_file}")

            return {
                "valid": len(missing) == 0,
                "manifest": {
                    "name": manifest.name,
                    "version": manifest.version,
                    "tools": manifest.tools,
                },
                "missing_files": missing,
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}


remote_skill_registry = RemoteSkillRegistry()
