#!/usr/bin/env python3
"""Aria Developer CLI - Skill management, testing, and deployment."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

import httpx


class AriaCLI:
    def __init__(self, base_url: str = "http://127.0.0.1:8001", admin_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.admin_key = admin_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    def _headers(self) -> dict[str, str]:
        return {"x-admin-api-key": self.admin_key} if self.admin_key else {}

    # Skill commands
    async def skill_list(self) -> dict[str, Any]:
        resp = await self.client.get(f"{self.base_url}/admin/skills", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def skill_install(self, repo_url: str, version: str | None = None, subdir: str = "") -> dict[str, Any]:
        payload = {"repo_url": repo_url, "version": version, "subdir": subdir}
        resp = await self.client.post(f"{self.base_url}/admin/skills/remote/install", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def skill_uninstall(self, skill_name: str) -> dict[str, Any]:
        resp = await self.client.post(f"{self.base_url}/admin/skills/remote/uninstall/{skill_name}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def skill_update(self, skill_name: str) -> dict[str, Any]:
        resp = await self.client.post(f"{self.base_url}/admin/skills/remote/update/{skill_name}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def skill_verify(self, skill_name: str) -> dict[str, Any]:
        resp = await self.client.get(f"{self.base_url}/admin/skills/remote/verify/{skill_name}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # Tool commands
    async def tool_list(self) -> dict[str, Any]:
        resp = await self.client.get(f"{self.base_url}/admin/tools", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def tool_delete(self, tool_name: str) -> dict[str, Any]:
        resp = await self.client.delete(f"{self.base_url}/admin/tools/{tool_name}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # Consolidation commands
    async def consolidation_run(self) -> dict[str, Any]:
        resp = await self.client.post(f"{self.base_url}/admin/consolidation/run", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def consolidation_status(self) -> dict[str, Any]:
        resp = await self.client.get(f"{self.base_url}/admin/consolidation/status", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # Goal commands
    async def goal_create(self, channel: str, chat_id: str, title: str, description: str, target_date: str | None = None, milestones: list[dict] | None = None) -> dict[str, Any]:
        payload = {"channel": channel, "chat_id": chat_id, "title": title, "description": description, "target_date": target_date, "milestones": milestones or []}
        resp = await self.client.post(f"{self.base_url}/admin/goals", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def goal_list(self, channel: str, chat_id: str, status: str | None = None) -> dict[str, Any]:
        params = {"channel": channel, "chat_id": chat_id}
        if status:
            params["status"] = status
        resp = await self.client.get(f"{self.base_url}/admin/goals", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def goal_get(self, goal_id: str, channel: str, chat_id: str) -> dict[str, Any]:
        params = {"channel": channel, "chat_id": chat_id}
        resp = await self.client.get(f"{self.base_url}/admin/goals/{goal_id}", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def goal_update(self, goal_id: str, channel: str, chat_id: str, **kwargs) -> dict[str, Any]:
        params = {"channel": channel, "chat_id": chat_id}
        resp = await self.client.patch(f"{self.base_url}/admin/goals/{goal_id}", json=kwargs, params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def goal_delete(self, goal_id: str, channel: str, chat_id: str) -> dict[str, Any]:
        params = {"channel": channel, "chat_id": chat_id}
        resp = await self.client.delete(f"{self.base_url}/admin/goals/{goal_id}", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def goal_milestone_add(self, goal_id: str, channel: str, chat_id: str, title: str, description: str = "", due_date: str | None = None) -> dict[str, Any]:
        params = {"channel": channel, "chat_id": chat_id}
        payload = {"title": title, "description": description, "due_date": due_date}
        resp = await self.client.post(f"{self.base_url}/admin/goals/{goal_id}/milestones", json=payload, params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def goal_milestone_update(self, goal_id: str, milestone_id: str, channel: str, chat_id: str, **kwargs) -> dict[str, Any]:
        params = {"channel": channel, "chat_id": chat_id}
        resp = await self.client.patch(f"{self.base_url}/admin/goals/{goal_id}/milestones/{milestone_id}", json=kwargs, params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def goal_due_soon(self, channel: str, chat_id: str, days: int = 7) -> dict[str, Any]:
        params = {"channel": channel, "chat_id": chat_id, "days": days}
        resp = await self.client.get(f"{self.base_url}/admin/goals/due-soon", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # Background agent commands
    async def background_run_goal_step(self, channel: str, chat_id: str, goal_id: str) -> dict[str, Any]:
        payload = {"channel": channel, "chat_id": chat_id, "goal_id": goal_id}
        resp = await self.client.post(f"{self.base_url}/admin/background/run-goal-step", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def background_status(self) -> dict[str, Any]:
        resp = await self.client.get(f"{self.base_url}/admin/background/status", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # Trigger commands
    async def trigger_create(self, channel: str, chat_id: str, name: str, source: str, events: list[str], secret: str | None = None, filter_config: dict | None = None) -> dict[str, Any]:
        payload = {"channel": channel, "chat_id": chat_id, "name": name, "source": source, "events": events, "secret": secret, "filter_config": filter_config or {}}
        resp = await self.client.post(f"{self.base_url}/admin/triggers", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def trigger_list(self, channel: str, chat_id: str) -> dict[str, Any]:
        params = {"channel": channel, "chat_id": chat_id}
        resp = await self.client.get(f"{self.base_url}/admin/triggers", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def trigger_test(self, trigger_id: str, payload: dict) -> dict[str, Any]:
        resp = await self.client.post(f"{self.base_url}/admin/triggers/{trigger_id}/test", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # Vector memory commands
    async def vector_search(self, query: str, channel: str | None = None, chat_id: str | None = None, top_k: int = 10, min_score: float = 0.3) -> dict[str, Any]:
        payload = {"query": query, "top_k": top_k, "min_score": min_score}
        if channel:
            payload["channel"] = channel
        if chat_id:
            payload["chat_id"] = chat_id
        resp = await self.client.post(f"{self.base_url}/admin/vector/search", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def vector_rebuild(self, channel: str, chat_id: str, limit: int = 1000) -> dict[str, Any]:
        payload = {"channel": channel, "chat_id": chat_id, "limit": limit}
        resp = await self.client.post(f"{self.base_url}/admin/vector/rebuild", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # Voice commands
    async def voice_transcribe(self, audio_base64: str) -> dict[str, Any]:
        payload = {"audio": audio_base64, "is_base64": True}
        resp = await self.client.post(f"{self.base_url}/voice/transcribe", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def voice_synthesize(self, text: str, voice: str | None = None, speed: float | None = None) -> dict[str, Any]:
        payload = {"text": text}
        if voice:
            payload["voice"] = voice
        if speed:
            payload["speed"] = speed
        resp = await self.client.post(f"{self.base_url}/voice/synthesize", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # Vision commands
    async def vision_analyze(self, image_base64: str, prompt: str | None = None) -> dict[str, Any]:
        payload = {"image": image_base64, "is_base64": True}
        if prompt:
            payload["prompt"] = prompt
        resp = await self.client.post(f"{self.base_url}/vision/analyze", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()


async def main():
    parser = argparse.ArgumentParser(description="Aria Developer CLI")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="Aria base URL")
    parser.add_argument("--key", help="Admin API key (or set ARIA_ADMIN_KEY env var)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Skill commands
    skill_parser = subparsers.add_parser("skill", help="Skill management")
    skill_sub = skill_parser.add_subparsers(dest="skill_command", required=True)
    skill_sub.add_parser("list", help="List available skills")
    install = skill_sub.add_parser("install", help="Install skill from GitHub")
    install.add_argument("repo_url", help="GitHub repository URL")
    install.add_argument("--version", help="Git tag/branch")
    install.add_argument("--subdir", default="", help="Subdirectory in repo")
    skill_sub.add_parser("uninstall", help="Uninstall skill").add_argument("skill_name")
    skill_sub.add_parser("update", help="Update skill").add_argument("skill_name")
    skill_sub.add_parser("verify", help="Verify skill integrity").add_argument("skill_name")

    # Tool commands
    tool_parser = subparsers.add_parser("tool", help="Tool management")
    tool_sub = tool_parser.add_subparsers(dest="tool_command", required=True)
    tool_sub.add_parser("list", help="List installed tools")
    tool_sub.add_parser("delete", help="Delete tool").add_argument("tool_name")

    # Consolidation
    cons_parser = subparsers.add_parser("consolidation", help="Memory consolidation")
    cons_sub = cons_parser.add_subparsers(dest="cons_command", required=True)
    cons_sub.add_parser("run", help="Run consolidation now")
    cons_sub.add_parser("status", help="Show consolidation status")

    # Goals
    goal_parser = subparsers.add_parser("goal", help="Goal management")
    goal_sub = goal_parser.add_subparsers(dest="goal_command", required=True)
    create = goal_sub.add_parser("create", help="Create goal")
    create.add_argument("channel")
    create.add_argument("chat_id")
    create.add_argument("title")
    create.add_argument("description")
    create.add_argument("--target-date", help="Target date (YYYY-MM-DD)")
    create.add_argument("--milestones", help="JSON array of milestones")
    goal_sub.add_parser("list", help="List goals").add_argument("channel").add_argument("chat_id").add_argument("--status")
    goal_sub.add_parser("get", help="Get goal").add_argument("goal_id").add_argument("channel").add_argument("chat_id")
    goal_sub.add_parser("delete", help="Delete goal").add_argument("goal_id").add_argument("channel").add_argument("chat_id")
    milestone = goal_sub.add_parser("milestone-add", help="Add milestone to goal")
    milestone.add_argument("goal_id")
    milestone.add_argument("channel")
    milestone.add_argument("chat_id")
    milestone.add_argument("title")
    milestone.add_argument("--description", default="")
    milestone.add_argument("--due-date", help="Due date (YYYY-MM-DD)")
    goal_sub.add_parser("due-soon", help="Goals due soon").add_argument("channel").add_argument("chat_id").add_argument("--days", type=int, default=7)

    # Background agent
    bg_parser = subparsers.add_parser("background", help="Background agent")
    bg_sub = bg_parser.add_subparsers(dest="bg_command", required=True)
    bg_sub.add_parser("status", help="Show background agent status")
    run = bg_sub.add_parser("run-goal-step", help="Run autonomous step on goal")
    run.add_argument("channel")
    run.add_argument("chat_id")
    run.add_argument("goal_id")

    # Triggers
    trigger_parser = subparsers.add_parser("trigger", help="Webhook triggers")
    trigger_sub = trigger_parser.add_subparsers(dest="trigger_command", required=True)
    create_t = trigger_sub.add_parser("create", help="Create trigger")
    create_t.add_argument("channel")
    create_t.add_argument("chat_id")
    create_t.add_argument("name")
    create_t.add_argument("source")
    create_t.add_argument("events", nargs="+")
    create_t.add_argument("--secret")
    create_t.add_argument("--filter", help="JSON filter config")
    trigger_sub.add_parser("list", help="List triggers").add_argument("channel").add_argument("chat_id")
    test = trigger_sub.add_parser("test", help="Test trigger")
    test.add_argument("trigger_id")
    test.add_argument("payload", help="JSON payload")

    # Vector memory
    vec_parser = subparsers.add_parser("vector", help="Vector memory")
    vec_sub = vec_parser.add_subparsers(dest="vec_command", required=True)
    search = vec_sub.add_parser("search", help="Semantic search")
    search.add_argument("query")
    search.add_argument("--channel")
    search.add_argument("--chat-id")
    search.add_argument("--top-k", type=int, default=10)
    search.add_argument("--min-score", type=float, default=0.3)
    rebuild = vec_sub.add_parser("rebuild", help="Rebuild from long-term memory")
    rebuild.add_argument("channel")
    rebuild.add_argument("chat_id")
    rebuild.add_argument("--limit", type=int, default=1000)

    # Voice
    voice_parser = subparsers.add_parser("voice", help="Voice STT/TTS")
    voice_sub = voice_parser.add_subparsers(dest="voice_command", required=True)
    transcribe = voice_sub.add_parser("transcribe", help="Transcribe audio")
    transcribe.add_argument("audio_file", help="Path to audio file")
    synthesize = voice_sub.add_parser("synthesize", help="Synthesize speech")
    synthesize.add_argument("text")
    synthesize.add_argument("--voice")
    synthesize.add_argument("--speed", type=float)

    # Vision
    vision_parser = subparsers.add_parser("vision", help="Vision analysis")
    vision_sub = vision_parser.add_subparsers(dest="vision_command", required=True)
    analyze = vision_sub.add_parser("analyze", help="Analyze image")
    analyze.add_argument("image_file", help="Path to image file")
    analyze.add_argument("--prompt")

    args = parser.parse_args()

    admin_key = args.key or sys.environ.get("ARIA_ADMIN_KEY")
    if not admin_key and args.command not in ["skill"]:  # skill list doesn't need auth
        print("Error: Admin API key required (--key or ARIA_ADMIN_KEY env var)")
        sys.exit(1)

    cli = AriaCLI(args.url, admin_key)
    try:
        # Skill commands
        if args.command == "skill":
            if args.skill_command == "list":
                result = await cli.skill_list()
                for skill in result["skills"]:
                    status = "✓" if skill["loaded"] else " "
                    print(f"  [{status}] {skill['name']} v{skill['version']} - {skill['description']}")
            elif args.skill_command == "install":
                result = await cli.skill_install(args.repo_url, args.version, args.subdir)
                print(f"Skill installed: {result['result']['skill_name']} v{result['result']['version']}")
            elif args.skill_command == "uninstall":
                result = await cli.skill_uninstall(args.skill_name)
                print(f"Skill uninstalled: {result['skill']}")
            elif args.skill_command == "update":
                result = await cli.skill_update(args.skill_name)
                print(f"Skill updated: {result['result']['skill_name']} v{result['result']['version']}")
            elif args.skill_command == "verify":
                result = await cli.skill_verify(args.skill_name)
                print(json.dumps(result["verification"], indent=2))

        # Tool commands
        elif args.command == "tool":
            if args.tool_command == "list":
                result = await cli.tool_list()
                for tool in result["tools"]:
                    status = "✓" if tool["available"] else " "
                    print(f"  [{status}] {tool['name']} - {tool['description']}")
            elif args.tool_command == "delete":
                result = await cli.tool_delete(args.tool_name)
                print(f"Tool deleted: {result['tool']['name']}")

        # Consolidation
        elif args.command == "consolidation":
            if args.cons_command == "run":
                result = await cli.consolidation_run()
                print(f"Consolidation complete: {result['result']}")
            elif args.cons_command == "status":
                result = await cli.consolidation_status()
                print(f"Last run: {result['last_run']}")
                print(f"Processed chats: {result['processed_chats']}")

        # Goals
        elif args.command == "goal":
            if args.goal_command == "create":
                milestones = json.loads(args.milestones) if args.milestones else []
                result = await cli.goal_create(args.channel, args.chat_id, args.title, args.description, args.target_date, milestones)
                print(f"Goal created: {result['goal']['id']} - {result['goal']['title']}")
            elif args.goal_command == "list":
                result = await cli.goal_list(args.channel, args.chat_id, args.status)
                for goal in result["goals"]:
                    print(f"  {goal['id']} [{goal['status']}] {goal['title']} ({goal['progress']*100:.0f}%)")
            elif args.goal_command == "get":
                result = await cli.goal_get(args.goal_id, args.channel, args.chat_id)
                print(json.dumps(result["goal"], indent=2))
            elif args.goal_command == "delete":
                result = await cli.goal_delete(args.goal_id, args.channel, args.chat_id)
                print(f"Goal deleted: {result['goal_id']}")
            elif args.goal_command == "milestone-add":
                result = await cli.goal_milestone_add(args.goal_id, args.channel, args.chat_id, args.title, args.description, args.due_date)
                print(f"Milestone added: {result['milestone']['id']} - {result['milestone']['title']}")
            elif args.goal_command == "due-soon":
                result = await cli.goal_due_soon(args.channel, args.chat_id, args.days)
                for goal in result["goals"]:
                    print(f"  {goal['id']} - {goal['title']}")

        # Background agent
        elif args.command == "background":
            if args.bg_command == "status":
                result = await cli.background_status()
                print(f"Running: {result['running']}")
            elif args.bg_command == "run-goal-step":
                result = await cli.background_run_goal_step(args.channel, args.chat_id, args.goal_id)
                print(f"Result: {result['result']}")

        # Triggers
        elif args.command == "trigger":
            if args.trigger_command == "create":
                filter_config = json.loads(args.filter) if args.filter else {}
                result = await cli.trigger_create(args.channel, args.chat_id, args.name, args.source, args.events, args.secret, filter_config)
                print(f"Trigger created: {result['trigger']['id']} - {result['trigger']['name']}")
            elif args.trigger_command == "list":
                result = await cli.trigger_list(args.channel, args.chat_id)
                for t in result["triggers"]:
                    print(f"  {t['id']} [{t['source']}] {t['name']} - events: {', '.join(t['events'])}")
            elif args.trigger_command == "test":
                payload = json.loads(args.payload)
                result = await cli.trigger_test(args.trigger_id, payload)
                print(json.dumps(result, indent=2))

        # Vector
        elif args.command == "vector":
            if args.vec_command == "search":
                result = await cli.vector_search(args.query, args.channel, args.chat_id, args.top_k, args.min_score)
                for item in result["results"]:
                    doc = item["document"]
                    print(f"  [{item['score']:.3f}] {doc['channel']}/{doc['chat_id']} - {doc['text'][:100]}")
            elif args.vec_command == "rebuild":
                result = await cli.vector_rebuild(args.channel, args.chat_id, args.limit)
                print(f"Rebuilt index: {result['indexed']} documents")

        # Voice
        elif args.command == "voice":
            if args.voice_command == "transcribe":
                with open(args.audio_file, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                result = await cli.voice_transcribe(audio_b64)
                print(f"Transcription: {result['result'].get('text', '')}")
            elif args.voice_command == "synthesize":
                result = await cli.voice_synthesize(args.text, args.voice, args.speed)
                print(f"Audio generated: {result['result'].get('audio_path', 'N/A')}")

        # Vision
        elif args.command == "vision":
            if args.vision_command == "analyze":
                with open(args.image_file, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode()
                result = await cli.vision_analyze(image_b64, args.prompt)
                print(json.dumps(result["result"], indent=2))

    finally:
        await cli.close()


if __name__ == "__main__":
    import sys
    import asyncio
    asyncio.run(main())
