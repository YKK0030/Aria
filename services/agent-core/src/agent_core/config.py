from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "README.md").exists() and (parent / "docker-compose.yml").exists():
            return parent
    return current.parents[4]


REPO_ROOT = _find_repo_root()
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="AGENT_HOST")
    port: int = Field(default=8000, alias="AGENT_PORT")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_simple_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_SIMPLE_MODEL")
    groq_complex_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_COMPLEX_MODEL")
    groq_complex_message_length: int = Field(default=280, alias="GROQ_COMPLEX_MESSAGE_LENGTH")
    groq_complex_history_threshold: int = Field(default=6, alias="GROQ_COMPLEX_HISTORY_THRESHOLD")
    agent_name: str = Field(default="OpsBridge", alias="AGENT_NAME")
    system_prompt: str = Field(
        default="You are a multi-channel operations copilot. Be concise and helpful.",
        alias="SYSTEM_PROMPT",
    )
    whatsapp_gateway_url: str = Field(default="http://localhost:3001", alias="WHATSAPP_GATEWAY_URL")
    whatsapp_gateway_api_key: str = Field(default="", alias="WHATSAPP_GATEWAY_API_KEY")
    whatsapp_webhook_api_key: str = Field(default="", alias="WHATSAPP_WEBHOOK_API_KEY")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_chat_ids: str = Field(default="", alias="TELEGRAM_ALLOWED_CHAT_IDS")
    default_reply_enabled: bool = Field(default=True, alias="DEFAULT_REPLY_ENABLED")
    agent_data_dir: str = Field(default=".data/agent-core", alias="AGENT_DATA_DIR")
    access_policy_file: str = Field(default="config/access-policy.json", alias="ACCESS_POLICY_FILE")
    max_history_messages: int = Field(default=10, alias="MAX_HISTORY_MESSAGES")
    enable_audit_logging: bool = Field(default=True, alias="ENABLE_AUDIT_LOGGING")
    enable_commands: bool = Field(default=True, alias="ENABLE_COMMANDS")
    admin_api_key: str = Field(default="", alias="ADMIN_API_KEY")
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

    @property
    def allowed_telegram_chat_ids(self) -> set[int]:
        values = [item.strip() for item in self.telegram_allowed_chat_ids.split(",") if item.strip()]
        return {int(item) for item in values}

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
    def resolved_long_term_memory_db_path(self) -> Path:
        db_path = Path(self.long_term_memory_db_path)
        return db_path if db_path.is_absolute() else REPO_ROOT / db_path

    @property
    def resolved_tools_dir(self) -> Path:
        tools_dir = Path(self.tools_dir)
        return tools_dir if tools_dir.is_absolute() else REPO_ROOT / tools_dir

    @property
    def resolved_whatsapp_webhook_api_key(self) -> str:
        return self.whatsapp_webhook_api_key or self.whatsapp_gateway_api_key


settings = Settings()
