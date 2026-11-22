from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from agent_core.commands import handle_builtin_command, parse_command
from agent_core.config import settings
from agent_core.memory import long_term_memory, short_term_memory
from agent_core.models import AgentState
from agent_core.policy import policy
from agent_core.prompts import build_system_prompt
from agent_core.tooling import dynamic_tool_registry


def build_graph():
    simple_llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_simple_model,
        temperature=0.2,
    )
    complex_llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_complex_model,
        temperature=0.2,
    )

    def select_reasoning_model(event_text: str, history: list[dict]) -> tuple[ChatGroq, str]:
        lowered = event_text.lower()
        complexity_keywords = (
            "analyze",
            "analysis",
            "compare",
            "plan",
            "strategy",
            "design",
            "architecture",
            "debug",
            "fix",
            "step by step",
            "why",
            "how",
            "optimize",
            "refactor",
            "summarize",
            "summary",
        )
        is_complex = (
            len(event_text) >= settings.groq_complex_message_length
            or len(history) >= settings.groq_complex_history_threshold
            or any(keyword in lowered for keyword in complexity_keywords)
            or "\n" in event_text
            or "```" in event_text
            or event_text.count("?") > 1
        )
        if is_complex:
            return complex_llm, settings.groq_complex_model
        return simple_llm, settings.groq_simple_model

    def fallback_reasoning_text() -> str:
        if not settings.groq_api_key.strip():
            return (
                "I am connected, but the Groq model key is not configured yet. "
                "Built-in commands like /help, /note, /todo, and /memory still work."
            )
        return (
            "I hit a temporary AI processing issue, but I am still online. "
            "Please retry in a moment, or use /help for built-in commands."
        )

    def fallback_summary_text(history: list[dict]) -> str:
        if not history:
            return "I could not build an AI summary right now, and there is no recent history saved for this chat."

        recent = history[-5:]
        bullets = "\n".join(
            f"- {item.get('role', item.get('direction', 'unknown'))}: {str(item.get('text', ''))[:160]}"
            for item in recent
        )
        return "AI summary is temporarily unavailable. Recent conversation snapshot:\n" + bullets

    def format_short_term_memory(messages: list[dict]) -> str:
        if not messages:
            return "No short-term memory."
        return "\n".join(
            f"{item.get('role', 'unknown')}: {str(item.get('text', ''))[:240]}" for item in messages[-8:]
        )

    async def load_context(state: AgentState) -> AgentState:
        event = state["event"]
        short_messages = await short_term_memory.get_messages(event.channel, event.chat_id, settings.short_term_memory_turns)
        state["history"] = short_messages
        state["short_term_memory"] = short_messages
        state["long_term_nodes"] = []
        return state

    def route_message(state: AgentState) -> AgentState:
        event = state["event"]
        active_policy = policy.load()
        channel_policy = active_policy.get(event.channel, {})
        behavior_policy = active_policy.get("behavior", {})

        if not channel_policy.get("enabled", True):
            state["route"] = "blocked"
            state["should_reply"] = False
            return state

        if event.chat_id in set(channel_policy.get("blocked_chat_ids", [])):
            state["route"] = "blocked"
            state["should_reply"] = False
            return state

        allowed_chat_ids = set(channel_policy.get("allowed_chat_ids", []))
        if channel_policy.get("allowlist_managed") and event.chat_id not in allowed_chat_ids:
            state["route"] = "blocked"
            state["should_reply"] = False
            return state
        if not channel_policy.get("allowlist_managed") and allowed_chat_ids and event.chat_id not in allowed_chat_ids:
            state["route"] = "blocked"
            state["should_reply"] = False
            return state

        parsed = parse_command(event.text) if settings.enable_commands else None
        if parsed:
            allowed_commands = set(behavior_policy.get("allowed_commands", []))
            command_name, argument = parsed
            if allowed_commands and command_name not in allowed_commands:
                state["route"] = "command"
                state["command_name"] = command_name
                state["response_text"] = "That command is not allowed."
                state["should_reply"] = True
                return state

            state["route"] = "command"
            state["command_name"] = command_name
            state["command_argument"] = argument
            return state

        state["route"] = "llm"
        return state

    def handle_blocked(state: AgentState) -> AgentState:
        return state

    def handle_command(state: AgentState) -> AgentState:
        return handle_builtin_command(state)

    async def summarize(state: AgentState) -> AgentState:
        event = state["event"]
        history = cast(list[dict], state.get("history", []))
        history_text = "\n".join(
            f"{item.get('role', item.get('direction', 'unknown'))}: {item.get('text', '')}" for item in history[-10:]
        ) or "No recent history."
        state["selected_model"] = settings.groq_complex_model
        try:
            response = await complex_llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "Summarize the conversation clearly. Include key topics, decisions, and next actions."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"Channel: {event.channel}\n"
                            f"Chat ID: {event.chat_id}\n"
                            f"Conversation:\n{history_text}"
                        )
                    ),
                ]
            )
            state["response_text"] = response.content if isinstance(response.content, str) else str(response.content)
        except Exception as error:
            state["selected_model"] = "fallback"
            state["error_message"] = str(error)
            state["response_text"] = fallback_summary_text(history)
        state["should_reply"] = True
        return state

    async def reason(state: AgentState) -> AgentState:
        event = state["event"]
        history = cast(list[dict], state.get("history", []))
        short_memory = cast(list[dict], state.get("short_term_memory", []))
        history_text = "\n".join(
            f"{item.get('role', item.get('direction', 'unknown'))}: {item.get('text', '')}" for item in history[-8:]
        ) or "No recent history."
        short_term_text = format_short_term_memory(short_memory)
        selected_llm, selected_model = select_reasoning_model(event.text, history)
        state["selected_model"] = selected_model

        def graph_memory_search(query: str, limit: int = settings.long_term_memory_top_k) -> str:
            nodes = long_term_memory.retrieve_top_nodes(event.channel, event.chat_id, query, limit)
            state["long_term_nodes"] = nodes
            if not nodes:
                return "No relevant graph memory nodes found."
            return "\n".join(
                f"[id={node['id']}] [score={node.get('score', 0):.2f}] {node['role']}: {str(node['text'])[:240]}"
                for node in nodes[: settings.long_term_memory_top_k]
            )

        builtin_tools = [
            StructuredTool.from_function(
                func=graph_memory_search,
                name="graph_memory_search",
                description=(
                    "Search the long-term graph memory for relevant past chat nodes in this same chat. "
                    "Use this only if the current question needs older durable memory."
                ),
                infer_schema=True,
            )
        ]
        available_tools = builtin_tools + dynamic_tool_registry.get_tools()
        llm_with_tools = selected_llm.bind_tools(available_tools)
        used_tools: list[dict] = []

        try:
            base_messages = [
                SystemMessage(
                    content=(
                        build_system_prompt()
                        + "\nYou have access to tools."
                        + "\nUse graph_memory_search only when long-term memory is genuinely needed."
                        + "\nDo not call tools when you can answer directly from the message and short-term memory."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Channel: {event.channel}\n"
                        f"Chat ID: {event.chat_id}\n"
                        f"Sender ID: {event.sender_id}\n"
                        f"Group Name: {event.group_name or 'N/A'}\n"
                        f"User Name: {event.push_name or 'N/A'}\n"
                        f"Short-Term Memory:\n{short_term_text}\n"
                        f"Recent History:\n{history_text}\n"
                        f"Message: {event.text}"
                    )
                ),
            ]
            response = await llm_with_tools.ainvoke(base_messages)
            if getattr(response, "tool_calls", None):
                tool_messages = []
                tool_map = {tool.name: tool for tool in available_tools}

                for call in response.tool_calls:
                    tool_name = call.get("name", "")
                    tool_args = call.get("args", {})
                    used_tools.append({"name": tool_name, "args": tool_args})
                    tool = tool_map.get(tool_name)
                    if not tool:
                        tool_result = f"Tool '{tool_name}' was not found."
                    else:
                        try:
                            tool_result = await tool.ainvoke(tool_args)
                        except Exception as error:
                            tool_result = f"Tool '{tool_name}' failed: {error}"
                    tool_call_id = call.get("id") or tool_name or "tool_call"
                    tool_messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call_id))

                final_response = await selected_llm.ainvoke(base_messages + [response, *tool_messages])
                response_text = final_response.content if isinstance(final_response.content, str) else str(final_response.content)
            else:
                response_text = response.content if isinstance(response.content, str) else str(response.content)

            state["used_tools"] = used_tools
            state["response_text"] = response_text
        except Exception as error:
            state["selected_model"] = "fallback"
            state["error_message"] = str(error)
            state["response_text"] = fallback_reasoning_text()
        state["should_reply"] = settings.default_reply_enabled and policy.load().get("behavior", {}).get(
            "allow_auto_reply", True
        )
        return state

    graph = StateGraph(AgentState)
    graph.add_node("load_context", load_context)
    graph.add_node("route_message", route_message)
    graph.add_node("handle_blocked", handle_blocked)
    graph.add_node("handle_command", handle_command)
    graph.add_node("summarize", summarize)
    graph.add_node("reason", reason)
    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "route_message")
    graph.add_conditional_edges(
        "route_message",
        lambda state: cast(str, state.get("route", "llm")),
        {
            "blocked": "handle_blocked",
            "command": "handle_command",
            "llm": "reason",
        },
    )
    graph.add_edge("handle_blocked", END)
    graph.add_conditional_edges(
        "handle_command",
        lambda state: "summarize" if state.get("summary_mode") else "done",
        {
            "summarize": "summarize",
            "done": END,
        },
    )
    graph.add_edge("summarize", END)
    graph.add_edge("reason", END)
    return graph.compile()
