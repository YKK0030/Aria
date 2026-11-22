from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field


Channel = Literal["whatsapp", "telegram", "mcp", "cli", "web", "slack", "discord", "email"]
OutboundChannel = Literal["whatsapp", "telegram", "slack", "discord", "email"]


class InboundEvent(BaseModel):
    channel: Channel
    chat_id: str = Field(alias="chatId")
    sender_id: str = Field(alias="senderId")
    from_me: bool = Field(default=False, alias="fromMe")
    push_name: str | None = Field(default=None, alias="pushName")
    group_name: str | None = Field(default=None, alias="groupName")
    is_group: bool = Field(default=False, alias="isGroup")
    message_id: str = Field(alias="messageId")
    text: str
    timestamp: int
    voice_mode: bool = False

    model_config = {
        "populate_by_name": True
    }


class TelegramInboundEvent(BaseModel):
    channel: Channel = "telegram"
    chat_id: str
    sender_id: str
    from_me: bool = False
    push_name: str | None = None
    group_name: str | None = None
    is_group: bool = False
    message_id: str
    text: str
    timestamp: int


class SlackInboundEvent(BaseModel):
    channel: Channel = "slack"
    channel_id: str
    sender_id: str
    from_me: bool = False
    push_name: str | None = None
    group_name: str | None = None
    is_group: bool = False
    message_id: str
    text: str
    timestamp: int


class DiscordInboundEvent(BaseModel):
    channel: Channel = "discord"
    channel_id: str
    sender_id: str
    from_me: bool = False
    push_name: str | None = None
    group_name: str | None = None
    is_group: bool = False
    message_id: str
    text: str
    timestamp: int


class EmailInboundEvent(BaseModel):
    channel: Channel = "email"
    chat_id: str
    sender_id: str
    from_me: bool = False
    push_name: str | None = None
    group_name: str | None = None
    is_group: bool = False
    message_id: str
    text: str
    timestamp: int


class OutboundMessage(BaseModel):
    channel: OutboundChannel
    chat_id: str
    text: str


class AdminSendRequest(BaseModel):
    channel: OutboundChannel
    chat_id: str
    text: str


class LocalChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    session_id: str = Field(default="default", min_length=1, max_length=128)
    voice_mode: bool = False


class ToolProposalRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    source: str = Field(min_length=1, max_length=24000)
    tests: list[dict] = Field(min_length=1, max_length=10)
    replaces_tool: str | None = Field(default=None, min_length=2, max_length=48)


class ToolTestResultRequest(BaseModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    test_count: int = Field(ge=1, le=10)


class ToolReviewRequest(BaseModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    test_count: int = Field(ge=1, le=10)


class ToolRevisionRequest(BaseModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class CodeChangeReviewRequest(BaseModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AgentState(TypedDict):
    event: InboundEvent | TelegramInboundEvent
    history: NotRequired[list[dict]]
    short_term_memory: NotRequired[list[dict]]
    long_term_nodes: NotRequired[list[dict]]
    route: NotRequired[str]
    command_name: NotRequired[str]
    command_argument: NotRequired[str]
    summary_mode: NotRequired[bool]
    selected_model: NotRequired[str]
    error_message: NotRequired[str]
    delivery_error: NotRequired[str]
    used_tools: NotRequired[list[dict]]
    response_text: NotRequired[str]
    should_reply: NotRequired[bool]
