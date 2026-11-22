from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agent_core.agent import create_agent
from agent_core.config import settings
from agent_core.memory import long_term_memory, short_term_memory
from agent_core.skills.learning import skill_learning
from agent_core.storage import store

logger = logging.getLogger(__name__)


class MemoryConsolidator:
    def __init__(self) -> None:
        self.consolidation_dir = Path(settings.resolved_agent_data_dir) / "consolidation"
        self.consolidation_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.consolidation_dir / "state.json"
        self._load_state()

    def _load_state(self) -> None:
        if self.state_file.exists():
            try:
                self.state = json.loads(self.state_file.read_text())
            except Exception:
                self.state = {"last_run": 0, "processed_chats": {}}
        else:
            self.state = {"last_run": 0, "processed_chats": {}}

    def _save_state(self) -> None:
        try:
            self.state_file.write_text(json.dumps(self.state, indent=2))
        except Exception:
            pass

    async def run_consolidation(self) -> dict[str, Any]:
        """Run nightly consolidation across all chats."""
        started = time.time()
        results = {
            "chats_processed": 0,
            "memories_created": 0,
            "patterns_detected": 0,
            "skills_proposed": 0,
            "errors": [],
        }

        try:
            # Get all chat histories
            history_dir = Path(settings.resolved_agent_data_dir) / "history"
            if not history_dir.exists():
                return results

            for hist_file in history_dir.glob("*.jsonl"):
                try:
                    chat_result = await self._consolidate_chat(hist_file)
                    results["chats_processed"] += 1
                    results["memories_created"] += chat_result.get("memories_created", 0)
                    results["patterns_detected"] += chat_result.get("patterns_detected", 0)
                    results["skills_proposed"] += chat_result.get("skills_proposed", 0)
                except Exception as e:
                    results["errors"].append(f"{hist_file.name}: {e}")
                    logger.warning("Consolidation failed for %s: %s", hist_file, e)

            self.state["last_run"] = time.time()
            self._save_state()

            # Store consolidation event in long-term memory
            long_term_memory.add_node(
                channel="system",
                chat_id="consolidation",
                role="system",
                text=f"Nightly consolidation: {results['chats_processed']} chats, "
                     f"{results['memories_created']} memories, "
                     f"{results['patterns_detected']} patterns, "
                     f"{results['skills_proposed']} skill proposals",
            )

        except Exception as e:
            results["errors"].append(f"Global error: {e}")
            logger.error("Consolidation run failed: %s", e)

        results["duration_ms"] = round((time.time() - started) * 1000)
        return results

    async def _consolidate_chat(self, hist_file: Path) -> dict[str, Any]:
        """Consolidate a single chat's history."""
        # Parse channel and chat_id from filename
        # Format: {channel}-{safe_chat_id}.jsonl
        stem = hist_file.stem
        parts = stem.split("-", 1)
        if len(parts) != 2:
            return {"memories_created": 0, "patterns_detected": 0, "skills_proposed": 0}

        channel, safe_chat_id = parts

        # Read recent history (last 7 days)
        cutoff = datetime.now(UTC) - timedelta(days=7)
        messages = []
        with hist_file.open() as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    msg_time = datetime.fromisoformat(msg.get("ts", "").replace("Z", "+00:00"))
                    if msg_time >= cutoff:
                        messages.append(msg)
                except Exception:
                    continue

        if len(messages) < 5:  # Not enough to consolidate
            return {"memories_created": 0, "patterns_detected": 0, "skills_proposed": 0}

        # Group by day
        daily_groups = defaultdict(list)
        for msg in messages:
            try:
                msg_time = datetime.fromisoformat(msg.get("ts", "").replace("Z", "+00:00"))
                day_key = msg_time.date().isoformat()
                daily_groups[day_key].append(msg)
            except Exception:
                continue

        memories_created = 0
        patterns_detected = 0
        skills_proposed = 0

        # Process each day's conversations
        for day, day_messages in daily_groups.items():
            # Create daily summary
            summary = await self._create_daily_summary(channel, safe_chat_id, day, day_messages)
            if summary:
                node_id = long_term_memory.add_node(
                    channel=channel,
                    chat_id=safe_chat_id,
                    role="summary",
                    text=summary,
                )
                if node_id:
                    memories_created += 1

            # Detect patterns
            patterns = await self._detect_patterns(channel, safe_chat_id, day_messages)
            for pattern in patterns:
                node_id = long_term_memory.add_node(
                    channel=channel,
                    chat_id=safe_chat_id,
                    role="pattern",
                    text=pattern,
                )
                if node_id:
                    patterns_detected += 1

        # Check for skill gaps
        skill_gaps = await self._detect_skill_gaps(channel, safe_chat_id, messages)
        for gap in skill_gaps:
            # This would create a tool proposal
            skills_proposed += 1

        return {
            "memories_created": memories_created,
            "patterns_detected": patterns_detected,
            "skills_proposed": skills_proposed,
        }

    async def _create_daily_summary(
        self, channel: str, chat_id: str, day: str, messages: list[dict]
    ) -> str | None:
        """Create a concise summary of a day's conversation."""
        if not self._model_configured():
            return None

        # Build conversation text
        conv_text = "\n".join(
            f"{m.get('direction', m.get('role', 'unknown'))}: {m.get('text', '')[:500]}"
            for m in messages[-50:]  # Limit context
        )

        prompt = f"""Summarize this day's conversation in 3-5 bullet points.
Focus on: decisions made, facts learned, tasks created, questions raised, commitments.
Channel: {channel}, Date: {day}

Conversation:
{conv_text}

Summary:"""

        try:
            agent = create_agent(
                settings.groq_complex_model if settings.model_provider != "ollama" else settings.ollama_model,
                [],
                "Create concise daily conversation summaries. Extract key facts, decisions, and action items.",
            )
            response = await agent.arun(prompt)
            content = response.content if isinstance(response.content, str) else str(response.content)
            return f"[{day}] {content.strip()}"
        except Exception as e:
            logger.warning("Failed to create daily summary: %s", e)
            return None

    async def _detect_patterns(
        self, channel: str, chat_id: str, messages: list[dict]
    ) -> list[str]:
        """Detect recurring patterns in conversation."""
        if not self._model_configured() or len(messages) < 10:
            return []

        conv_text = "\n".join(
            f"{m.get('direction', m.get('role', 'unknown'))}: {m.get('text', '')[:300]}"
            for m in messages[-30:]
        )

        prompt = f"""Identify 1-3 recurring patterns in this conversation.
Patterns could be: repeated question types, workflow patterns, topic clusters, tool usage habits.
Return as JSON array of strings, or empty array if none.

Conversation:
{conv_text}

Patterns:"""

        try:
            agent = create_agent(
                settings.groq_complex_model if settings.model_provider != "ollama" else settings.ollama_model,
                [],
                "Identify behavioral patterns in conversation history.",
            )
            response = await agent.arun(prompt)
            content = response.content if isinstance(response.content, str) else str(response.content)
            patterns = json.loads(content)
            return patterns if isinstance(patterns, list) else []
        except Exception:
            return []

    async def _detect_skill_gaps(
        self, channel: str, chat_id: str, messages: list[dict]
    ) -> list[dict]:
        """Detect missing capabilities that could be new skills."""
        # Simple heuristic: look for "I wish I could" or "it would be nice if" patterns
        gaps = []
        for msg in messages:
            if msg.get("direction") == "inbound":
                text = msg.get("text", "").lower()
                if any(p in text for p in [
                    "wish i could", "would be nice", "can you add", "missing feature",
                    "need a tool", "automate this", "repetitive task"
                ]):
                    gaps.append({
                        "trigger": msg.get("text", "")[:200],
                        "timestamp": msg.get("ts"),
                    })
        return gaps[:3]  # Limit proposals

    def _model_configured(self) -> bool:
        if settings.model_provider == "ollama":
            return bool(settings.ollama_host.strip() and settings.ollama_model.strip())
        if settings.model_provider == "nvidia":
            return bool(settings.nvidia_api_key.strip())
        return bool(settings.groq_api_key.strip())


consolidator = MemoryConsolidator()
