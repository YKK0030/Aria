from __future__ import annotations

from agent_core.models import AgentState
from agent_core.storage import store


def parse_command(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    parts = stripped.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""
    return command, argument


def capabilities_text() -> str:
    return (
        "I can help with:\n"
        "- normal chat replies on WhatsApp and Telegram\n"
        "- recent memory lookup with /memory\n"
        "- channel and session context with /status and /channels\n"
        "- note keeping with /note add|list|clear\n"
        "- todo tracking with /todo add|list|done|clear\n"
        "- chat summarization with /summary\n"
        "- simple echo/testing with /echo\n"
        "- admin-side manual sending and history inspection through the API"
    )


def handle_builtin_command(state: AgentState) -> AgentState:
    command_name = state.get("command_name", "")
    command_argument = state.get("command_argument", "").strip()
    event = state["event"]
    history = state.get("history", [])

    if command_name == "/help":
        state["response_text"] = (
            "Available commands:\n"
            "/help\n"
            "/status\n"
            "/channels\n"
            "/memory\n"
            "/capabilities\n"
            "/echo <text>\n"
            "/note add <text>\n"
            "/note list\n"
            "/note clear\n"
            "/todo add <text>\n"
            "/todo list\n"
            "/todo done <id>\n"
            "/todo clear\n"
            "/summary"
        )
    elif command_name == "/status":
        state["response_text"] = (
            f"Agent is active.\nChannel: {event.channel}\n"
            f"Chat: {event.chat_id}\nSender: {event.sender_id}"
        )
    elif command_name == "/channels":
        state["response_text"] = (
            f"Channel: {event.channel}\n"
            f"Chat ID: {event.chat_id}\n"
            f"Group: {'yes' if event.is_group else 'no'}\n"
            f"Group Name: {event.group_name or 'N/A'}"
        )
    elif command_name == "/memory":
        if not history:
            state["response_text"] = "No recent history saved for this chat yet."
        else:
            preview = "\n".join(
                f"- {item.get('role', item.get('direction', 'unknown'))}: {item.get('text', '')[:120]}"
                for item in history[-5:]
            )
            state["response_text"] = f"Recent history:\n{preview}"
    elif command_name == "/capabilities":
        state["response_text"] = capabilities_text()
    elif command_name == "/echo":
        state["response_text"] = command_argument or "Nothing to echo."
    elif command_name == "/note":
        state["response_text"] = _handle_note_command(event.channel, event.chat_id, event.sender_id, command_argument)
    elif command_name == "/todo":
        state["response_text"] = _handle_todo_command(event.channel, event.chat_id, event.sender_id, command_argument)
    elif command_name == "/summary":
        state["summary_mode"] = True
    else:
        state["response_text"] = "Unknown command. Use /help."

    if not state.get("summary_mode"):
        state["should_reply"] = True
    return state


def _handle_note_command(channel: str, chat_id: str, sender_id: str, argument: str) -> str:
    if not argument:
        return "Usage: /note add <text> | /note list | /note clear"

    if argument == "list":
        notes = store.list_notes(channel, chat_id)
        if not notes:
            return "No saved notes for this chat."
        return "Notes:\n" + "\n".join(f"- [{note['id']}] {note['text']}" for note in notes)

    if argument == "clear":
        store.clear_notes(channel, chat_id)
        return "All notes cleared for this chat."

    if argument.startswith("add "):
        note_text = argument[4:].strip()
        if not note_text:
            return "Usage: /note add <text>"
        note = store.add_note(channel, chat_id, note_text, sender_id)
        return f"Note saved: [{note['id']}] {note['text']}"

    return "Usage: /note add <text> | /note list | /note clear"


def _handle_todo_command(channel: str, chat_id: str, sender_id: str, argument: str) -> str:
    if not argument:
        return "Usage: /todo add <text> | /todo list | /todo done <id> | /todo clear"

    if argument == "list":
        todos = store.list_todos(channel, chat_id)
        if not todos:
            return "No todos for this chat."
        return "Todos:\n" + "\n".join(
            f"- [{todo['id']}] {'done' if todo['done'] else 'open'}: {todo['text']}" for todo in todos
        )

    if argument == "clear":
        store.clear_todos(channel, chat_id)
        return "All todos cleared for this chat."

    if argument.startswith("add "):
        todo_text = argument[4:].strip()
        if not todo_text:
            return "Usage: /todo add <text>"
        todo = store.add_todo(channel, chat_id, todo_text, sender_id)
        return f"Todo created: [{todo['id']}] {todo['text']}"

    if argument.startswith("done "):
        raw_id = argument[5:].strip()
        if not raw_id.isdigit():
            return "Usage: /todo done <id>"
        todo = store.complete_todo(channel, chat_id, int(raw_id))
        if not todo:
            return "Todo not found."
        return f"Todo completed: [{todo['id']}] {todo['text']}"

    return "Usage: /todo add <text> | /todo list | /todo done <id> | /todo clear"
