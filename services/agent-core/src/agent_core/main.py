from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent_core.commands import capabilities_text
from agent_core.config import settings
from agent_core.memory import long_term_memory
from agent_core.models import AdminSendRequest, InboundEvent
from agent_core.policy import policy
from agent_core.service import AgentOrchestrator
from agent_core.tooling import dynamic_tool_registry


class HealthResponse(BaseModel):
    ok: bool
    service: str


class StatusResponse(BaseModel):
    ok: bool
    service: str
    agent_name: str
    default_reply_enabled: bool
    commands_enabled: bool
    audit_logging_enabled: bool
    groq_simple_model: str
    groq_complex_model: str
    redis_enabled: bool
    short_term_memory_turns: int
    long_term_memory_top_k: int
    long_term_memory_db_path: str
    tools_dir: str
    policy: dict


orchestrator = AgentOrchestrator()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await orchestrator.telegram.start()
    yield
    await orchestrator.telegram.stop()


app = FastAPI(title="agent-core", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(ok=True, service="agent-core")


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(event: InboundEvent, x_api_key: str = Header(default="")):
    if not settings.has_whatsapp_webhook_api_key:
        raise HTTPException(status_code=503, detail="WhatsApp webhook API key is not configured")
    if x_api_key != settings.resolved_whatsapp_webhook_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    result = await orchestrator.process_whatsapp_event(event)
    return {"ok": True, "result": result}


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
        default_reply_enabled=settings.default_reply_enabled,
        commands_enabled=settings.enable_commands,
        audit_logging_enabled=settings.enable_audit_logging,
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
