from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field


Channel = Literal["whatsapp", "telegram"]


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


class OutboundMessage(BaseModel):
    channel: Channel
    chat_id: str
    text: str


class AdminSendRequest(BaseModel):
    channel: Channel
    chat_id: str
    text: str


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
