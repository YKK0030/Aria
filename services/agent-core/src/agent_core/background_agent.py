from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from agent_core.agent import create_agent
from agent_core.config import settings
from agent_core.goals import goal_manager, Goal, GoalStatus, MilestoneStatus
from agent_core.memory import long_term_memory, short_term_memory
from agent_core.skills import skill_manager
from agent_core.storage import store

logger = logging.getLogger(__name__)


@dataclass
class ProactiveAction:
    type: str  # "remind", "suggest", "execute", "summarize"
    channel: str
    chat_id: str
    payload: dict[str, Any]
    priority: int = 1  # 1=high, 2=medium, 3=low
    created_at: float = field(default_factory=time.time)


class BackgroundAgent:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._action_queue: asyncio.Queue[ProactiveAction] = asyncio.Queue()
        self._last_check: dict[str, float] = {}

    async def start(self, interval_seconds: int = 300) -> None:  # 5 min default
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(interval_seconds))
        logger.info("Background agent started (interval: %ds)", interval_seconds)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background agent stopped")

    async def _run_loop(self, interval: int) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error("Background agent tick failed: %s", e)
            await asyncio.sleep(interval)

    async def _tick(self) -> None:
        now = time.time()

        # Check each active chat for proactive actions
        await self._check_due_goals()
        await self._check_stale_conversations()
        await self._check_skill_opportunities()
        await self._generate_daily_briefings()

        # Process queued actions
        await self._process_actions()

    async def _check_due_goals(self) -> None:
        """Find goals/milestones due soon and queue reminders."""
        # This would iterate over all known channels/chats
        # For now, we'll rely on the scheduler to call this per chat
        pass

    async def check_chat(self, channel: str, chat_id: str) -> list[ProactiveAction]:
        """Run proactive checks for a specific chat. Called by scheduler."""
        actions = []

        # 1. Goals due soon
        due_goals = goal_manager.get_goals_due_soon(channel, chat_id, days=3)
        for goal in due_goals:
            actions.append(ProactiveAction(
                type="remind",
                channel=channel,
                chat_id=chat_id,
                payload={
                    "goal_id": goal.id,
                    "goal_title": goal.title,
                    "message": f"Goal '{goal.title}' has upcoming deadlines",
                    "due_milestones": [
                        {"title": m.title, "due": m.due_date}
                        for m in goal.milestones
                        if m.due_date and m.status != MilestoneStatus.DONE
                    ][:3],
                },
                priority=1,
            ))

        # 2. Stale active goals (no progress in 7 days)
        active_goals = goal_manager.get_active_goals(channel, chat_id)
        for goal in active_goals:
            try:
                updated = datetime.fromisoformat(goal.updated_at.replace("Z", "+00:00"))
                if (datetime.now(UTC) - updated).days >= 7 and goal.progress < 1.0:
                    actions.append(ProactiveAction(
                        type="suggest",
                        channel=channel,
                        chat_id=chat_id,
                        payload={
                            "goal_id": goal.id,
                            "goal_title": goal.title,
                            "message": f"Goal '{goal.title}' hasn't progressed in a week. Want to break it down?",
                            "suggestion": "break_down",
                        },
                        priority=2,
                    ))
            except Exception:
                pass

        # 3. Overdue milestones
        for goal in active_goals:
            for m in goal.milestones:
                if m.due_date and m.status != MilestoneStatus.DONE:
                    try:
                        due = datetime.fromisoformat(m.due_date.replace("Z", "+00:00"))
                        if due < datetime.now(UTC):
                            actions.append(ProactiveAction(
                                type="remind",
                                channel=channel,
                                chat_id=chat_id,
                                payload={
                                    "goal_id": goal.id,
                                    "milestone_id": m.id,
                                    "message": f"Milestone '{m.title}' is overdue",
                                },
                                priority=1,
                            ))
                    except Exception:
                        pass

        return actions

    async def _check_stale_conversations(self) -> None:
        # Would check for chats that haven't had activity but have pending context
        pass

    async def _check_skill_opportunities(self) -> None:
        # Detect repetitive patterns that could use a new skill
        pass

    async def _generate_daily_briefings(self) -> None:
        # Generate morning briefings for active chats
        pass

    async def _process_actions(self) -> None:
        while not self._action_queue.empty():
            action = await self._action_queue.get()
            await self._execute_action(action)

    async def _execute_action(self, action: ProactiveAction) -> None:
        """Execute a proactive action - send notification, create summary, etc."""
        try:
            if action.type == "remind":
                await self._send_reminder(action)
            elif action.type == "suggest":
                await self._send_suggestion(action)
            elif action.type == "summarize":
                await self._send_summary(action)

            store.append_audit("proactive_action_executed", {
                "type": action.type,
                "channel": action.channel,
                "chat_id": action.chat_id,
                "payload": action.payload,
            })
        except Exception as e:
            logger.error("Failed to execute proactive action: %s", e)

    async def _send_reminder(self, action: ProactiveAction) -> None:
        # Queue a message to be sent via the channel
        # This integrates with the orchestrator's send_manual_message
        from agent_core.service import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        message = action.payload.get("message", "Reminder")
        await orchestrator.send_manual_message(action.channel, action.chat_id, f"🔔 {message}")

    async def _send_suggestion(self, action: ProactiveAction) -> None:
        from agent_core.service import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        message = action.payload.get("message", "Suggestion")
        await orchestrator.send_manual_message(action.channel, action.chat_id, f"💡 {message}")

    async def _send_summary(self, action: ProactiveAction) -> None:
        from agent_core.service import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        message = action.payload.get("message", "Summary")
        await orchestrator.send_manual_message(action.channel, action.chat_id, f"📋 {message}")

    def queue_action(self, action: ProactiveAction) -> None:
        self._action_queue.put_nowait(action)

    async def run_goal_step(self, channel: str, chat_id: str, goal_id: str) -> dict[str, Any]:
        """Autonomously work on a goal's next pending milestone."""
        goal = goal_manager.get_goal(channel, chat_id, goal_id)
        if not goal or goal.status != GoalStatus.ACTIVE:
            return {"success": False, "reason": "Goal not found or not active"}

        # Find next pending milestone
        next_milestone = None
        for m in goal.milestones:
            if m.status == MilestoneStatus.PENDING:
                next_milestone = m
                break

        if not next_milestone:
            return {"success": False, "reason": "No pending milestones"}

        # Mark in progress
        goal_manager.update_milestone(channel, chat_id, goal_id, next_milestone.id, status=MilestoneStatus.IN_PROGRESS)

        # Use agent to work on it
        try:
            # Load relevant skills
            skill_manager.ensure_skills_for_event(channel, chat_id, f"Work on: {next_milestone.title}", [])

            # Create agent with goal context
            model_prefs = skill_manager.get_model_preferences()
            model_id = model_prefs["preferred"]

            agent = create_agent(
                model_id,
                skill_manager.loaded_skills.get(list(skill_manager.loaded_skills.keys())[0], {}).tools if skill_manager.loaded_skills else [],
                f"You are working autonomously on a milestone for goal: {goal.title}\n\nMilestone: {next_milestone.title}\nDescription: {next_milestone.description}\n\nMake progress and report what you did.",
            )

            # This would actually execute - for now return plan
            return {
                "success": True,
                "milestone": next_milestone.title,
                "action": "started",
                "next_steps": "Would execute tools here",
            }
        except Exception as e:
            goal_manager.update_milestone(channel, chat_id, goal_id, next_milestone.id, status=MilestoneStatus.PENDING)
            return {"success": False, "reason": str(e)}


background_agent = BackgroundAgent()
