from collections.abc import Sequence
from typing import Any

from agno.agent import Agent
from agno.models.groq import Groq
from agno.models.ollama import Ollama
from agno.models.openai.like import OpenAILike

from agent_core.config import settings


def create_agent(model_id: str, tools: Sequence[Any], system_message: str) -> Agent:
    if settings.model_provider == "ollama":
        model = Ollama(
            id=settings.ollama_model,
            host=settings.ollama_host,
            options={"num_ctx": settings.ollama_num_ctx, "temperature": 0.2},
        )
    elif settings.model_provider == "nvidia":
        model = OpenAILike(id=model_id, api_key=settings.nvidia_api_key,
                           base_url=settings.nvidia_base_url, temperature=0.2)
    else:
        model = Groq(id=model_id, api_key=settings.groq_api_key, temperature=0.2)
    return Agent(
        name=settings.agent_name,
        model=model,
        tools=list(tools),
        system_message=system_message,
    )
