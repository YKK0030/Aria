from pathlib import Path
import re
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    # Check container fallback first
    if Path("/app").exists():
        return Path("/app")
    # Then search for repo markers
    for parent in current.parents:
        if (parent / "README.md").exists() and (parent / "docker-compose.yml").exists():
            return parent
    return Path("/")


REPO_ROOT = _find_repo_root()
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(default="aria-agent-core", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(default="", alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    host: str = Field(default="0.0.0.0", alias="AGENT_HOST")
    port: int = Field(default=8000, alias="AGENT_PORT")
    aria_channels: str = Field(default="all", alias="ARIA_CHANNELS")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    model_provider: Literal["groq", "ollama", "nvidia"] = Field(default="ollama", alias="MODEL_PROVIDER")
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", alias="NVIDIA_BASE_URL")
    nvidia_super_model: str = Field(default="nvidia/nemotron-3.5-lightning-30b-a3b", alias="NVIDIA_SUPER_MODEL")
    nvidia_code_model: str = Field(default="nvidia/nemotron-3.5-lightning-30b-a3b", alias="NVIDIA_CODE_MODEL")
    nvidia_robotics_model: str = Field(default="nvidia/nemotron-3.5-lightning-30b-a3b", alias="NVIDIA_ROBOTICS_MODEL")
    ollama_model: str = Field(default="llama3.2:latest", alias="OLLAMA_MODEL")
    ollama_host: str = Field(default="http://host.docker.internal:11434", alias="OLLAMA_HOST")
    ollama_num_ctx: int = Field(default=4096, gt=0, le=131072, alias="OLLAMA_NUM_CTX")
    groq_simple_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_SIMPLE_MODEL")
    groq_complex_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_COMPLEX_MODEL")
    groq_complex_message_length: int = Field(default=280, alias="GROQ_COMPLEX_MESSAGE_LENGTH")
    groq_complex_history_threshold: int = Field(default=6, alias="GROQ_COMPLEX_HISTORY_THRESHOLD")
    agent_name: str = Field(default="Aria", alias="AGENT_NAME")
    system_prompt: str = Field(
        default="You are a multi-channel operations copilot. Be concise and helpful.",
        alias="SYSTEM_PROMPT",
    )
    whatsapp_gateway_url: str = Field(default="http://localhost:3001", alias="WHATSAPP_GATEWAY_URL")
    whatsapp_gateway_api_key: str = Field(default="", alias="WHATSAPP_GATEWAY_API_KEY")
    whatsapp_webhook_api_key: str = Field(default="", alias="WHATSAPP_WEBHOOK_API_KEY")
    whatsapp_owner_numbers: str = Field(default="", alias="WHATSAPP_OWNER_NUMBERS")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_chat_ids: str = Field(default="", alias="TELEGRAM_ALLOWED_CHAT_IDS")
    slack_bot_token: str = Field(default="", alias="SLACK_BOT_TOKEN")
    slack_app_token: str = Field(default="", alias="SLACK_APP_TOKEN")
    slack_allowed_channels: str = Field(default="", alias="SLACK_ALLOWED_CHANNELS")
    discord_bot_token: str = Field(default="", alias="DISCORD_BOT_TOKEN")
    discord_allowed_channels: str = Field(default="", alias="DISCORD_ALLOWED_CHANNELS")
    email_webhook_key: str = Field(default="", alias="EMAIL_WEBHOOK_KEY")
    default_reply_enabled: bool = Field(default=True, alias="DEFAULT_REPLY_ENABLED")
    agent_data_dir: str = Field(default=".data/agent-core", alias="AGENT_DATA_DIR")
    access_policy_file: str = Field(default="config/access-policy.json", alias="ACCESS_POLICY_FILE")
    access_policy_overrides_file: str = Field(
        default=".data/agent-core/allowlists/access-policy-overrides.json", alias="ACCESS_POLICY_OVERRIDES_FILE"
    )
    max_history_messages: int = Field(default=10, alias="MAX_HISTORY_MESSAGES")
    enable_audit_logging: bool = Field(default=True, alias="ENABLE_AUDIT_LOGGING")
    enable_commands: bool = Field(default=True, alias="ENABLE_COMMANDS")
    admin_api_key: str = Field(default="", alias="ADMIN_API_KEY")
    # MCP API key mirrors admin key for single-key access
    @property
    def mcp_api_key(self) -> str:
        return self.admin_api_key
    mcp_identity: str = Field(default="local", alias="MCP_IDENTITY")
    mcp_allowed_hosts: str = Field(
        default="localhost,localhost:8000,127.0.0.1,127.0.0.1:8000,agent-core,agent-core:8000",
        alias="MCP_ALLOWED_HOSTS",
    )
    redis_enabled: bool = Field(default=True, alias="REDIS_ENABLED")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    short_term_memory_turns: int = Field(default=4, alias="SHORT_TERM_MEMORY_TURNS")
    short_term_memory_ttl_seconds: int = Field(default=86400, alias="SHORT_TERM_MEMORY_TTL_SECONDS")
    long_term_memory_db_path: str = Field(
        default=".data/agent-core/long_term_memory.sqlite3",
        alias="LONG_TERM_MEMORY_DB_PATH",
    )
    long_term_memory_top_k: int = Field(default=5, alias="LONG_TERM_MEMORY_TOP_K")
    tools_dir: str = Field(default="tools", alias="TOOLS_DIR")
    attic_enabled: bool = Field(default=False, alias="ATTIC_ENABLED")
    attic_mcp_url: str = Field(default="http://host.docker.internal:4100/mcp", alias="ATTIC_MCP_URL")
    attic_mcp_api_key: str = Field(default="", alias="ATTIC_MCP_API_KEY")
    tool_proposals_dir: str = Field(default=".data/agent-core/tool-proposals", alias="TOOL_PROPOSALS_DIR")
    generated_tools_dir: str = Field(default=".data/agent-core/generated-tools", alias="GENERATED_TOOLS_DIR")

    @property
    def enabled_channels(self) -> set[str]:
        channels = {item.strip().lower() for item in self.aria_channels.split(",") if item.strip()}
        known = {"cli", "web", "telegram", "whatsapp", "slack", "discord", "email"}
        return known if "all" in channels else channels & known

    def channel_enabled(self, channel: str) -> bool:
        return channel in self.enabled_channels

    @property
    def allowed_telegram_chat_ids(self) -> set[int]:
        values = [item.strip() for item in self.telegram_allowed_chat_ids.split(",") if item.strip()]
        return {int(item) for item in values}

    @property
    def allowed_whatsapp_owner_chat_ids(self) -> set[str]:
        values = [item.strip() for item in self.whatsapp_owner_numbers.split(",") if item.strip()]
        owner_ids = set()
        for value in values:
            if value.endswith("@s.whatsapp.net"):
                owner_ids.add(value)
                continue
            digits = re.sub(r"\D", "", value)
            if digits:
                owner_ids.add(f"{digits}@s.whatsapp.net")
        return owner_ids

    @property
    def allowed_slack_channels(self) -> set[str]:
        return {item.strip() for item in self.slack_allowed_channels.split(",") if item.strip()}

    @property
    def allowed_discord_channels(self) -> set[str]:
        return {item.strip() for item in self.discord_allowed_channels.split(",") if item.strip()}

    @property
    def allowed_mcp_hosts(self) -> list[str]:
        return [item.strip() for item in self.mcp_allowed_hosts.split(",") if item.strip()]

    @property
    def has_admin_api_key(self) -> bool:
        return bool(self.admin_api_key.strip())

    @property
    def has_whatsapp_webhook_api_key(self) -> bool:
        return bool(self.resolved_whatsapp_webhook_api_key.strip())

    @property
    def resolved_agent_data_dir(self) -> Path:
        data_dir = Path(self.agent_data_dir)
        return data_dir if data_dir.is_absolute() else REPO_ROOT / data_dir

    @property
    def resolved_access_policy_file(self) -> Path:
        policy_file = Path(self.access_policy_file)
        return policy_file if policy_file.is_absolute() else REPO_ROOT / policy_file

    @property
    def resolved_access_policy_overrides_file(self) -> Path:
        policy_file = Path(self.access_policy_overrides_file)
        return policy_file if policy_file.is_absolute() else REPO_ROOT / policy_file

    @property
    def resolved_docs_dir(self) -> Path:
        return REPO_ROOT / "docs"

    @property
    def resolved_long_term_memory_db_path(self) -> Path:
        db_path = Path(self.long_term_memory_db_path)
        return db_path if db_path.is_absolute() else REPO_ROOT / db_path

    @property
    def resolved_tools_dir(self) -> Path:
        tools_dir = Path(self.tools_dir)
        return tools_dir if tools_dir.is_absolute() else REPO_ROOT / tools_dir

    @property
    def resolved_tool_proposals_dir(self) -> Path:
        path = Path(self.tool_proposals_dir)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def resolved_generated_tools_dir(self) -> Path:
        path = Path(self.generated_tools_dir)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def resolved_whatsapp_webhook_api_key(self) -> str:
        return self.whatsapp_webhook_api_key or self.whatsapp_gateway_api_key


settings = Settings()
