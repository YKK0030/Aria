from contextlib import asynccontextmanager
import asyncio
import json
import logging
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_core.commands import capabilities_text
from agent_core.config import settings
from agent_core.memory import long_term_memory, short_term_memory
from agent_core.mcp_server import MCPBearerAuth, create_mcp_server
from agent_core.models import (
    AdminSendRequest,
    CodeChangeReviewRequest,
    InboundEvent,
    LocalChatRequest,
    ToolProposalRequest,
    ToolRevisionRequest,
    ToolReviewRequest,
    ToolTestResultRequest,
)
from agent_core.policy import policy
from agent_core.service import AgentOrchestrator
from agent_core.storage import store
from agent_core.tooling import dynamic_tool_registry
from agent_core.tooling.proposals import tool_proposals
from agent_core.tooling.reviewer import ToolReviewUnavailable, review_tool, revise_tool, review_code_change
from agent_core.tooling.code_changes import code_changes
from agent_core.self_improvement import pipeline
from agent_core.skills import skill_manager
from agent_core.consolidation import consolidator
from agent_core.scheduler import scheduler
from agent_core.metrics import metrics_endpoint, record_http_request
from agent_core.background_agent import background_agent
from agent_core.triggers import trigger_manager
from agent_core.vector_memory import get_vector_index, semantic_search, index_document
from agent_core.web_ui import chat_page, command_center_page, memory_page, trace_page, metrics_page, dashboard_page

logging.getLogger("httpx").setLevel(logging.WARNING)


class HealthResponse(BaseModel):
    ok: bool
    service: str


class StatusResponse(BaseModel):
    ok: bool
    service: str
    agent_name: str
    enabled_channels: list[str]
    default_reply_enabled: bool
    commands_enabled: bool
    audit_logging_enabled: bool
    model_provider: str
    groq_simple_model: str
    groq_complex_model: str
    redis_enabled: bool
    short_term_memory_turns: int
    long_term_memory_top_k: int
    long_term_memory_db_path: str
    tools_dir: str
    policy: dict


orchestrator = AgentOrchestrator()
mcp_server = create_mcp_server(orchestrator)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp_server.session_manager.run():
        await orchestrator.telegram.start()
        # Schedule nightly consolidation
        scheduler.add_daily_job("memory_consolidation", consolidator.run_consolidation)
        # Schedule self-improvement pipeline (run every 6 hours)
        scheduler.add_daily_job("self_improvement", pipeline.run_pipeline)
        # Start background agent for proactive actions
        background_task = asyncio.create_task(background_agent.start(interval_seconds=300))
        scheduler_task = asyncio.create_task(scheduler.start())
        try:
            yield
        finally:
            await background_agent.stop()
            background_task.cancel()
            scheduler.stop()
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
            await orchestrator.telegram.stop()


app = FastAPI(title="agent-core", lifespan=lifespan)
# FastMCP normally serves at /mcp; this app mounts it at /mcp, so its child
# route must be the mount root to keep the public endpoint at /mcp.
mcp_server.settings.streamable_http_path = "/"
DASHBOARD_DIR = Path("/app/dashboard")
if (DASHBOARD_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DASHBOARD_DIR / "assets"), name="dashboard-assets")


@app.middleware("http")
async def normalize_mcp_path(request, call_next):
    if request.url.path == "/mcp":
        request.scope["path"] = "/mcp/"
        request.scope["raw_path"] = b"/mcp/"
    return await call_next(request)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    # Normalize path for metrics (replace IDs with placeholders)
    path = request.url.path
    for param in request.path_params.values():
        path = path.replace(str(param), "{id}")
    record_http_request(request.method, path, response.status_code, duration)
    return response


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(ok=True, service="agent-core")


# WebSocket for live dashboard updates
@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Send a heartbeat / metrics snapshot every 5 seconds
            from agent_core.metrics import get_metrics_snapshot
            snap = get_metrics_snapshot()
            await websocket.send_json({"type": "metrics", "data": snap})
            await asyncio.sleep(5)
    except Exception:
        await websocket.close()


@app.get("/metrics")
async def metrics(request: Request):
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(metrics_page())
    return metrics_endpoint()


@app.get("/admin/metrics/json")
async def admin_metrics_json(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.metrics import get_metrics_snapshot
    return {"ok": True, "metrics": get_metrics_snapshot()}


@app.get("/", response_class=HTMLResponse)
async def local_chat_ui():
    return HTMLResponse(chat_page())


@app.get("/aria-trace", response_class=HTMLResponse)
async def local_trace_ui():
    return HTMLResponse(trace_page())


@app.get("/command-center", response_class=HTMLResponse)
async def command_center_ui():
    return HTMLResponse(command_center_page())


@app.get("/memory", response_class=HTMLResponse)
async def memory_ui():
    return HTMLResponse(memory_page())


@app.get("/metrics/ui", response_class=HTMLResponse)
async def metrics_ui():
    return HTMLResponse(metrics_page())


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_ui():
    built_dashboard = DASHBOARD_DIR / "index.html"
    if built_dashboard.is_file():
        return FileResponse(built_dashboard)
    return HTMLResponse(dashboard_page())


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(event: InboundEvent, x_api_key: str = Header(default="")):
    if not settings.channel_enabled("whatsapp"):
        raise HTTPException(status_code=503, detail="WhatsApp channel is disabled")
    if not settings.has_whatsapp_webhook_api_key:
        raise HTTPException(status_code=503, detail="WhatsApp webhook API key is not configured")
    if x_api_key != settings.resolved_whatsapp_webhook_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    result = await orchestrator.process_whatsapp_event(event)
    return {"ok": True, "result": result}


@app.post("/webhooks/triggers/{trigger_id}")
async def trigger_webhook(
    trigger_id: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="x-hub-signature-256"),
    x_gitlab_token: str | None = Header(default=None, alias="x-gitlab-token"),
    x_github_event: str | None = Header(default=None, alias="x-github-event"),
    x_gitlab_event: str | None = Header(default=None, alias="x-gitlab-event"),
):
    from agent_core.triggers import trigger_manager
    body = await request.body()
    try:
        payload = json.loads(body)
    except Exception:
        payload = {}

    headers = dict(request.headers)
    result = await trigger_manager.process_webhook(trigger_id, payload, headers)
    return result


@app.post("/chat")
async def local_chat(payload: LocalChatRequest, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    if not settings.channel_enabled("web"):
        raise HTTPException(status_code=503, detail="Web/API channel is disabled")
    event = InboundEvent(
        channel="web",
        chatId=payload.session_id,
        senderId="local-user",
        messageId=uuid4().hex,
        text=payload.text,
        timestamp=int(time.time()),
        voice_mode=payload.voice_mode,
    )
    return {"ok": True, **await orchestrator.process_local_event(event)}


def _verify_admin_api_key(x_admin_api_key: str) -> None:
    if not settings.has_admin_api_key:
        raise HTTPException(status_code=503, detail="Admin API key is not configured")
    if x_admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin API key")


@app.get("/admin/status", response_model=StatusResponse)
async def admin_status(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return StatusResponse(
        ok=True,
        service="agent-core",
        agent_name=settings.agent_name,
        enabled_channels=sorted(settings.enabled_channels),
        default_reply_enabled=settings.default_reply_enabled,
        commands_enabled=settings.enable_commands,
        audit_logging_enabled=settings.enable_audit_logging,
        model_provider=settings.model_provider,
        groq_simple_model=settings.groq_simple_model,
        groq_complex_model=settings.groq_complex_model,
        redis_enabled=settings.redis_enabled,
        short_term_memory_turns=settings.short_term_memory_turns,
        long_term_memory_top_k=settings.long_term_memory_top_k,
        long_term_memory_db_path=str(settings.resolved_long_term_memory_db_path),
        tools_dir=str(settings.resolved_tools_dir),
        policy=policy.load(),
    )


@app.post("/admin/messages/send")
async def admin_send_message(payload: AdminSendRequest, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    await orchestrator.send_manual_message(payload.channel, payload.chat_id, payload.text)
    return {"ok": True}


@app.get("/admin/history/{channel}/{chat_id}")
async def admin_history(
    channel: str,
    chat_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    return {
        "ok": True,
        "channel": channel,
        "chat_id": chat_id,
        "history": orchestrator.get_history(channel, chat_id, limit),
    }


@app.get("/admin/audit")
async def admin_audit(
    limit: int = Query(default=200, ge=1, le=500),
    channel: str | None = Query(default=None, min_length=1, max_length=32),
    chat_id: str | None = Query(default=None, min_length=1, max_length=128),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "events": store.read_audit(limit=limit, channel=channel, chat_id=chat_id)}


@app.get("/admin/memory/short-term")
async def admin_short_term_memory(
    channel: str = Query(min_length=1, max_length=32),
    chat_id: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=4, ge=1, le=20),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    messages = await short_term_memory.get_messages(channel, chat_id, limit_turns=limit)
    return {"ok": True, "channel": channel, "chat_id": chat_id, "messages": messages}


@app.get("/admin/capabilities")
async def admin_capabilities(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {
        "ok": True,
        "capabilities": capabilities_text().splitlines(),
    }


@app.get("/admin/tools")
async def admin_tools(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {
        "ok": True,
        "tools": dynamic_tool_registry.list_tool_specs(),
    }


@app.delete("/admin/tools/{tool_name}")
async def admin_delete_tool(tool_name: str, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    try:
        removed = dynamic_tool_registry.delete_generated_tool(tool_name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Generated tool not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    store.append_audit("generated_tool_deleted", {"name": tool_name})
    return {"ok": True, "tool": {"name": removed["name"], "source": removed["source"]}}


@app.get("/admin/tool-proposals")
async def admin_tool_proposals(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "proposals": tool_proposals.list()}


@app.post("/admin/tool-proposals")
async def admin_create_tool_proposal(
    payload: ToolProposalRequest,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    proposal = tool_proposals.create(
        payload.name, payload.description, payload.source, payload.tests, payload.replaces_tool
    )
    store.append_audit("task_tool_proposed", {"proposal_id": proposal["id"], "name": proposal["name"]})
    return {"ok": True, "proposal": tool_proposals.summary(proposal)}


@app.get("/admin/tool-proposals/{proposal_id}")
async def admin_get_tool_proposal(proposal_id: str, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "proposal": tool_proposals.get(proposal_id)}


@app.delete("/admin/tool-proposals/{proposal_id}")
async def admin_delete_tool_proposal(proposal_id: str, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    proposal = tool_proposals.delete_uninstalled(proposal_id)
    store.append_audit("tool_draft_deleted", {"proposal_id": proposal_id, "name": proposal["name"]})
    return {"ok": True, "proposal": proposal}


@app.post("/admin/tool-proposals/{proposal_id}/tested")
async def admin_mark_tool_tested(
    proposal_id: str,
    payload: ToolTestResultRequest,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "proposal": tool_proposals.record_test(proposal_id, payload.sha256, payload.test_count)}


@app.post("/admin/tool-proposals/{proposal_id}/review")
async def admin_review_tool_proposal(
    proposal_id: str,
    payload: ToolReviewRequest,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    proposal = tool_proposals.get(proposal_id)
    if payload.sha256 != proposal["sha256"]:
        raise HTTPException(status_code=409, detail="Review does not match this proposal revision")
    review_started = time.perf_counter()
    reviewer_model = (
        settings.ollama_model if settings.model_provider == "ollama"
        else settings.nvidia_super_model if settings.model_provider == "nvidia"
        else settings.groq_complex_model
    )
    store.append_audit(
        "task_tool_review_started",
        {"proposal_id": proposal_id, "name": proposal["name"], "description": proposal["description"], "model": reviewer_model},
    )
    try:
        review = await review_tool(proposal, payload.test_count)
    except ToolReviewUnavailable as error:
        store.append_audit(
            "task_tool_review_failed",
            {"proposal_id": proposal_id, "name": proposal["name"], "error": str(error),
             "duration_ms": round((time.perf_counter() - review_started) * 1000)},
        )
        raise HTTPException(status_code=503, detail=str(error)) from error
    reviewed = tool_proposals.record_review(proposal_id, payload.sha256, payload.test_count, review.model_dump())
    store.append_audit(
        "task_tool_reviewed",
        {"proposal_id": proposal_id, "name": proposal["name"], "status": reviewed["status"],
         "model": reviewer_model, "description": proposal["description"],
         "summary": review.summary, "findings": review.findings,
         "duration_ms": round((time.perf_counter() - review_started) * 1000)},
    )
    return {"ok": True, "proposal": reviewed}


@app.post("/admin/tool-proposals/{proposal_id}/revise")
async def admin_revise_tool_proposal(
    proposal_id: str,
    payload: ToolRevisionRequest,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    proposal = tool_proposals.get(proposal_id)
    if payload.sha256 != proposal["sha256"]:
        raise HTTPException(status_code=409, detail="Revision does not match this proposal revision")
    if proposal["status"] != "needs_changes":
        raise HTTPException(status_code=409, detail="Only rejected proposals can be revised")
    try:
        revision = await revise_tool(proposal)
        revised = tool_proposals.create_revision(
            proposal_id,
            payload.sha256,
            revision.source,
            revision.tests,
        )
    except ToolReviewUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    store.append_audit(
        "task_tool_revised",
        {"proposal_id": revised["id"], "revision_of": proposal_id, "name": revised["name"]},
    )
    return {"ok": True, "proposal": tool_proposals.summary(revised)}


@app.post("/admin/tool-proposals/{proposal_id}/approve")
async def admin_approve_tool(proposal_id: str, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    proposal = tool_proposals.approve(proposal_id)
    store.append_audit("task_tool_approved", {"proposal_id": proposal_id, "name": proposal["name"]})
    return {"ok": True, "tool": proposal}


@app.get("/admin/code-change-proposals")
async def admin_code_change_proposals(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "proposals": code_changes.list()}


@app.get("/admin/code-change-proposals/{proposal_id}")
async def admin_get_code_change(proposal_id: str, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "proposal": code_changes.get(proposal_id)}


@app.post("/admin/code-change-proposals/{proposal_id}/review")
async def admin_review_code_change(
    proposal_id: str,
    payload: CodeChangeReviewRequest,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    proposal = code_changes.get(proposal_id)
    if payload.sha256 != proposal["sha256"]:
        raise HTTPException(status_code=409, detail="Review does not match this proposal revision")
    review_started = time.perf_counter()
    reviewer_model = (
        settings.ollama_model if settings.model_provider == "ollama"
        else settings.nvidia_code_model if settings.model_provider == "nvidia"
        else settings.groq_complex_model
    )
    store.append_audit(
        "code_change_review_started",
        {"proposal_id": proposal_id, "description": proposal["description"], "model": reviewer_model},
    )
    try:
        review = await review_code_change(proposal)
    except ToolReviewUnavailable as error:
        store.append_audit(
            "code_change_review_failed",
            {"proposal_id": proposal_id, "error": str(error),
             "duration_ms": round((time.perf_counter() - review_started) * 1000)},
        )
        raise HTTPException(status_code=503, detail=str(error)) from error
    reviewed = code_changes.record_review(proposal_id, payload.sha256, review.model_dump())
    store.append_audit(
        "code_change_reviewed",
        {"proposal_id": proposal_id, "status": reviewed["status"], "description": proposal["description"], "model": reviewer_model,
         "summary": review.summary, "findings": review.findings,
         "duration_ms": round((time.perf_counter() - review_started) * 1000)},
    )
    return {"ok": True, "proposal": reviewed}


@app.get("/admin/skills")
async def admin_list_skills(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "skills": skill_manager.list_available()}


@app.post("/admin/skills/{skill_name}/load")
async def admin_load_skill(skill_name: str, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    # Skills are loaded per chat, so this is a no-op for global loading
    # but we can validate the skill exists
    if skill_name not in skill_manager.registry:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"ok": True, "skill": skill_name, "message": "Skills are loaded per chat context"}


@app.post("/admin/skills/{skill_name}/unload")
async def admin_unload_skill(skill_name: str, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    skill_manager.unload_skill(skill_name)
    return {"ok": True, "skill": skill_name}


@app.get("/admin/skills/active")
async def admin_active_skills(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "active_skills": skill_manager.get_active_skills()}


@app.get("/admin/skills/learning/stats")
async def admin_skill_learning_stats(
    channel: str | None = Query(default=None),
    chat_id: str | None = Query(default=None),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.skills.learning import skill_learning
    return {"ok": True, "stats": skill_learning.get_stats(channel, chat_id)}


@app.get("/admin/skills/learning/preferences/{channel}/{chat_id}")
async def admin_skill_preferences(
    channel: str,
    chat_id: str,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.skills.learning import skill_learning
    pref = skill_learning.get_preference(channel, chat_id)
    return {
        "ok": True,
        "channel": channel,
        "chat_id": chat_id,
        "skill_scores": pref.skill_scores,
        "total_interactions": pref.total_interactions,
        "suggested_skills": skill_learning.get_suggested_skills(channel, chat_id),
        "last_updated": pref.last_updated,
    }


@app.post("/admin/skills/learning/feedback")
async def admin_skill_feedback(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.skills.learning import skill_learning
    skill_learning.record_interaction(
        skill_name=payload["skill_name"],
        channel=payload["channel"],
        chat_id=payload["chat_id"],
        success=payload["success"],
        user_feedback=payload.get("feedback"),
    )
    return {"ok": True}


@app.get("/admin/skills/remote")
async def admin_list_remote_skills(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.skills.registry import remote_skill_registry
    return {"ok": True, "skills": remote_skill_registry.list_remote_skills()}


@app.post("/admin/skills/remote/install")
async def admin_install_remote_skill(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.skills.registry import remote_skill_registry
    repo_url = payload.get("repo_url")
    version = payload.get("version")
    subdir = payload.get("subdir", "")
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url required")
    result = remote_skill_registry.install_from_github(repo_url, version, subdir)
    return {"ok": result.success, "result": {
        "skill_name": result.skill_name,
        "version": result.version,
        "message": result.message,
    }}


@app.post("/admin/skills/remote/uninstall/{skill_name}")
async def admin_uninstall_remote_skill(
    skill_name: str,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.skills.registry import remote_skill_registry
    success = remote_skill_registry.uninstall(skill_name)
    return {"ok": success, "skill": skill_name}


@app.post("/admin/skills/remote/update/{skill_name}")
async def admin_update_remote_skill(
    skill_name: str,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.skills.registry import remote_skill_registry
    result = remote_skill_registry.update_skill(skill_name)
    return {"ok": result.success, "result": {
        "skill_name": result.skill_name,
        "version": result.version,
        "message": result.message,
    }}


@app.get("/admin/skills/remote/verify/{skill_name}")
async def admin_verify_remote_skill(
    skill_name: str,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.skills.registry import remote_skill_registry
    return {"ok": True, "verification": remote_skill_registry.verify_skill(skill_name)}


@app.post("/admin/consolidation/run")
async def admin_run_consolidation(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    result = await consolidator.run_consolidation()
    return {"ok": True, "result": result}


@app.get("/admin/consolidation/status")
async def admin_consolidation_status(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {
        "ok": True,
        "last_run": consolidator.state.get("last_run"),
        "processed_chats": len(consolidator.state.get("processed_chats", {})),
    }


@app.get("/admin/scheduler/jobs")
async def admin_scheduler_jobs(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "jobs": scheduler.get_next_runs()}


@app.get("/admin/goals")
async def admin_list_goals(
    channel: str,
    chat_id: str,
    status: str | None = Query(default=None),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.goals import goal_manager, GoalStatus
    st = GoalStatus(status) if status else None
    goals = goal_manager.list_goals(channel, chat_id, st)
    return {"ok": True, "goals": [g.to_dict() for g in goals]}


@app.post("/admin/goals")
async def admin_create_goal(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.goals import goal_manager
    goal = goal_manager.create_goal(
        channel=payload["channel"],
        chat_id=payload["chat_id"],
        title=payload["title"],
        description=payload.get("description", ""),
        target_date=payload.get("target_date"),
        milestones=payload.get("milestones"),
    )
    return {"ok": True, "goal": goal.to_dict()}


@app.get("/admin/goals/{goal_id}")
async def admin_get_goal(
    goal_id: str,
    channel: str = Query(...),
    chat_id: str = Query(...),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.goals import goal_manager
    goal = goal_manager.get_goal(channel, chat_id, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"ok": True, "goal": goal.to_dict()}


@app.patch("/admin/goals/{goal_id}")
async def admin_update_goal(
    goal_id: str,
    payload: dict,
    channel: str = Query(...),
    chat_id: str = Query(...),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.goals import goal_manager
    goal = goal_manager.update_goal(channel, chat_id, goal_id, **payload)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"ok": True, "goal": goal.to_dict()}


@app.delete("/admin/goals/{goal_id}")
async def admin_delete_goal(
    goal_id: str,
    channel: str = Query(...),
    chat_id: str = Query(...),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.goals import goal_manager
    goal_manager.delete_goal(channel, chat_id, goal_id)
    return {"ok": True, "goal_id": goal_id}


@app.post("/admin/goals/{goal_id}/milestones")
async def admin_add_milestone(
    goal_id: str,
    payload: dict,
    channel: str = Query(...),
    chat_id: str = Query(...),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.goals import goal_manager
    milestone = goal_manager.add_milestone(
        channel, chat_id, goal_id,
        title=payload["title"],
        description=payload.get("description", ""),
        due_date=payload.get("due_date"),
    )
    if not milestone:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"ok": True, "milestone": milestone.to_dict()}


@app.patch("/admin/goals/{goal_id}/milestones/{milestone_id}")
async def admin_update_milestone(
    goal_id: str,
    milestone_id: str,
    payload: dict,
    channel: str = Query(...),
    chat_id: str = Query(...),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.goals import goal_manager
    milestone = goal_manager.update_milestone(channel, chat_id, goal_id, milestone_id, **payload)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return {"ok": True, "milestone": milestone.to_dict()}


@app.get("/admin/goals/due-soon")
async def admin_goals_due_soon(
    channel: str,
    chat_id: str,
    days: int = Query(default=7, ge=1, le=30),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.goals import goal_manager
    goals = goal_manager.get_goals_due_soon(channel, chat_id, days)
    return {"ok": True, "goals": [g.to_dict() for g in goals]}


@app.post("/admin/background/run-goal-step")
async def admin_run_goal_step(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.background_agent import background_agent
    result = await background_agent.run_goal_step(
        payload["channel"], payload["chat_id"], payload["goal_id"]
    )
    return {"ok": True, "result": result}


@app.get("/admin/background/status")
async def admin_background_status(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {"ok": True, "running": background_agent._running}


@app.get("/admin/triggers")
async def admin_list_triggers(
    channel: str,
    chat_id: str,
    active_only: bool = Query(default=True),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.triggers import trigger_manager
    triggers = trigger_manager.list_triggers(channel, chat_id, active_only)
    return {"ok": True, "triggers": [t.to_dict() for t in triggers]}


@app.post("/admin/triggers")
async def admin_create_trigger(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.triggers import trigger_manager
    trigger = trigger_manager.create_trigger(
        channel=payload["channel"],
        chat_id=payload["chat_id"],
        name=payload["name"],
        source=payload["source"],
        events=payload.get("events", []),
        secret=payload.get("secret"),
        filter_config=payload.get("filter_config"),
    )
    return {"ok": True, "trigger": trigger.to_dict()}


@app.get("/admin/triggers/{trigger_id}")
async def admin_get_trigger(
    trigger_id: str,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.triggers import trigger_manager
    trigger = trigger_manager.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"ok": True, "trigger": trigger.to_dict()}


@app.patch("/admin/triggers/{trigger_id}")
async def admin_update_trigger(
    trigger_id: str,
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.triggers import trigger_manager
    trigger = trigger_manager.update_trigger(trigger_id, **payload)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"ok": True, "trigger": trigger.to_dict()}


@app.delete("/admin/triggers/{trigger_id}")
async def admin_delete_trigger(
    trigger_id: str,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.triggers import trigger_manager
    trigger_manager.delete_trigger(trigger_id)
    return {"ok": True, "trigger_id": trigger_id}


@app.post("/admin/triggers/{trigger_id}/test")
async def admin_test_trigger(
    trigger_id: str,
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.triggers import trigger_manager
    # Simulate a webhook call with test payload
    result = await trigger_manager.process_webhook(trigger_id, payload, {})
    return {"ok": True, "result": result}


@app.post("/admin/vector/search")
async def admin_vector_search(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.vector_memory import semantic_search
    results = await semantic_search(
        query=payload["query"],
        channel=payload.get("channel"),
        chat_id=payload.get("chat_id"),
        top_k=payload.get("top_k", 10),
        min_score=payload.get("min_score", 0.3),
    )
    return {"ok": True, "results": results}


@app.get("/admin/vector/stats")
async def admin_vector_stats(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.vector_memory import get_vector_index
    index = get_vector_index()
    return {"ok": True, "stats": index.get_stats()}


@app.post("/admin/vector/rebuild")
async def admin_vector_rebuild(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.vector_memory import get_vector_index
    index = get_vector_index()
    count = index.rebuild_from_long_term_memory(
        payload["channel"],
        payload["chat_id"],
        payload.get("limit", 1000),
    )
    return {"ok": True, "indexed": count}


@app.post("/admin/vector/index")
async def admin_vector_index(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    from agent_core.vector_memory import index_document
    doc_id = index_document(
        channel=payload["channel"],
        chat_id=payload["chat_id"],
        text=payload["text"],
        metadata=payload.get("metadata", {}),
        source_type=payload.get("source_type", "memory"),
        doc_id=payload.get("doc_id"),
    )
    return {"ok": True, "doc_id": doc_id}


@app.post("/admin/self-improvement/run")
async def admin_run_self_improvement(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    result = await pipeline.run_pipeline()
    return {"ok": True, "result": result}


@app.get("/admin/self-improvement/status")
async def admin_self_improvement_status(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {
        "ok": True,
        "ab_tests": {
            name: {
                "variants": [
                    {
                        "name": v.name,
                        "trials": v.stats["trials"],
                        "successes": v.stats["successes"],
                        "avg_score": v.stats["avg_score"],
                        "avg_latency_ms": v.stats["avg_latency"],
                    }
                    for v in test.variants
                ],
                "traffic_split": test.traffic_split,
            }
            for name, test in pipeline.ab_tests.items()
        },
        "benchmark_history_count": len(pipeline.benchmark_history),
        "recent_regressions": pipeline.check_regressions(),
        "tool_gaps": pipeline.detect_tool_gaps(),
        "proposals": pipeline.generate_improvement_proposals(),
    }


@app.post("/admin/self-improvement/ab-test/record")
async def admin_ab_test_record(
    payload: dict,
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    pipeline.record_result(
        test_name=payload["test_name"],
        variant_name=payload["variant_name"],
        success=payload["success"],
        latency_ms=payload["latency_ms"],
        score=payload.get("score", 0.0),
    )
    return {"ok": True}


@app.get("/admin/self-improvement/ab-tests")
async def admin_list_ab_tests(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    return {
        "ok": True,
        "tests": {
            name: {
                "variants": [
                    {
                        "name": v.name,
                        "trials": v.stats["trials"],
                        "successes": v.stats["successes"],
                        "avg_score": v.stats["avg_score"],
                        "avg_latency_ms": v.stats["avg_latency"],
                        "success_rate": v.stats["successes"] / v.stats["trials"] if v.stats["trials"] > 0 else 0,
                    }
                    for v in test.variants
                ],
                "traffic_split": test.traffic_split,
                "min_trials_per_variant": test.min_trials_per_variant,
            }
            for name, test in pipeline.ab_tests.items()
        }
    }


@app.post("/admin/self-improvement/benchmarks/run")
async def admin_run_benchmarks(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    results = pipeline.run_benchmarks()
    return {"ok": True, "results": [vars(r) for r in results]}


@app.get("/admin/self-improvement/regressions")
async def admin_check_regressions(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    regressions = pipeline.check_regressions()
    return {"ok": True, "regressions": regressions}


@app.get("/admin/self-improvement/tool-gaps")
async def admin_tool_gaps(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    gaps = pipeline.detect_tool_gaps()
    return {"ok": True, "gaps": gaps}


@app.get("/admin/self-improvement/proposals")
async def admin_improvement_proposals(x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    proposals = pipeline.generate_improvement_proposals()
    return {"ok": True, "proposals": proposals}


@app.get("/admin/graph/search")
async def admin_graph_search(
    channel: str,
    chat_id: str,
    query: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    return {
        "ok": True,
        "results": long_term_memory.search_nodes(channel, chat_id, query, limit),
    }


@app.get("/admin/graph/node/{node_id}")
async def admin_graph_node(node_id: int, x_admin_api_key: str = Header(default="")):
    _verify_admin_api_key(x_admin_api_key)
    details = long_term_memory.get_node_details(node_id)
    if not details:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"ok": True, **details}


@app.get("/admin/graph/chat/{channel}/{chat_id}")
async def admin_graph_chat(
    channel: str,
    chat_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    x_admin_api_key: str = Header(default=""),
):
    _verify_admin_api_key(x_admin_api_key)
    graph = long_term_memory.get_chat_graph(channel, chat_id, limit)
    return {"ok": True, **graph}


@app.get("/admin/graph-ui", response_class=HTMLResponse)
async def admin_graph_ui():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Graph Memory UI</title>
  <style>
    body { font-family: Segoe UI, sans-serif; margin: 24px; background: #f7f7f9; color: #111; }
    input, button, select { padding: 8px; margin: 4px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    .panel { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin-top: 16px; }
    .list-item { border-bottom: 1px solid #eee; padding: 10px 0; cursor: pointer; }
    pre { white-space: pre-wrap; word-break: break-word; background: #f3f4f6; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>Graph Memory UI</h1>
  <div class="row">
    <input id="apiKey" type="password" placeholder="Admin API Key" />
    <input id="channel" value="whatsapp" placeholder="channel" />
    <input id="chatId" placeholder="chat_id" />
    <input id="query" placeholder="search query (optional)" />
    <button onclick="searchGraph()">Search</button>
    <button onclick="loadChatGraph()">Load Chat Graph</button>
  </div>

  <div class="panel">
    <h2>Results</h2>
    <div id="results"></div>
  </div>

  <div class="panel">
    <h2>Node Details</h2>
    <pre id="details">Select a node to inspect relations.</pre>
  </div>

  <script>
    async function apiFetch(path) {
      const apiKey = document.getElementById('apiKey').value;
      const response = await fetch(path, {
        headers: { 'x-admin-api-key': apiKey }
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text);
      }
      return response.json();
    }

    function renderResults(items) {
      const container = document.getElementById('results');
      container.innerHTML = '';
      if (!items.length) {
        container.textContent = 'No results found.';
        return;
      }
      for (const item of items) {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `<strong>#${item.id}</strong> [${item.role}] ${item.text}`;
        div.onclick = () => loadNode(item.id);
        container.appendChild(div);
      }
    }

    async function searchGraph() {
      const channel = document.getElementById('channel').value;
      const chatId = document.getElementById('chatId').value;
      const query = encodeURIComponent(document.getElementById('query').value);
      const data = await apiFetch(`/admin/graph/search?channel=${encodeURIComponent(channel)}&chat_id=${encodeURIComponent(chatId)}&query=${query}`);
      renderResults(data.results || []);
    }

    async function loadChatGraph() {
      const channel = document.getElementById('channel').value;
      const chatId = document.getElementById('chatId').value;
      const data = await apiFetch(`/admin/graph/chat/${encodeURIComponent(channel)}/${encodeURIComponent(chatId)}`);
      renderResults(data.nodes || []);
      document.getElementById('details').textContent = JSON.stringify({ edges: data.edges || [] }, null, 2);
    }

    async function loadNode(nodeId) {
      const data = await apiFetch(`/admin/graph/node/${nodeId}`);
      document.getElementById('details').textContent = JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>
"""


app.mount("/mcp", MCPBearerAuth(mcp_server.streamable_http_app()))
