"""LangGraph entrypoint for the Battery Lab Assistant deep agent."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Sequence

from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain.chat_models import init_chat_model

from battery_agent.kb import REPO_ROOT, SAMPLES_DIR
from battery_agent.prompts import (
    ANALYSIS_SUBAGENT_PROMPT,
    MAIN_SYSTEM_PROMPT,
    PROTOCOL_SUBAGENT_PROMPT,
    REPORT_SUBAGENT_PROMPT,
)
from battery_agent.tools import TOOLS

load_dotenv(REPO_ROOT / ".env")

MODEL_NAME = os.getenv("BATTERY_AGENT_MODEL", "openai:gpt-4o-mini")
TEMPERATURE = float(os.getenv("BATTERY_AGENT_TEMPERATURE", "0.1"))
OPENAI_API_KEY_PLACEHOLDERS = {
    "",
    "replace_with_real_key",
    "replace-with-real-openai-key",
}


class MissingOpenAIKeyChatModel(BaseChatModel):
    """Small local fallback so the app can explain missing configuration."""

    model_name: str = "missing_openai_api_key"

    @property
    def _llm_type(self) -> str:
        return "missing_openai_api_key"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "MissingOpenAIKeyChatModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=(
                            "The Battery Lab backend is running, but OpenAI is not configured yet. "
                            "Set a real OPENAI_API_KEY in the repository .env file, then restart "
                            "the backend server and send the message again."
                        )
                    )
                )
            ]
        )


def _uses_openai_model(model_name: str) -> bool:
    normalized_model_name = model_name.strip().lower()
    return normalized_model_name.startswith("openai:") or ":" not in normalized_model_name


def _has_real_openai_api_key() -> bool:
    return os.getenv("OPENAI_API_KEY", "").strip() not in OPENAI_API_KEY_PLACEHOLDERS


model = (
    MissingOpenAIKeyChatModel()
    if _uses_openai_model(MODEL_NAME) and not _has_real_openai_api_key()
    else init_chat_model(model=MODEL_NAME, temperature=TEMPERATURE)
)

today = datetime.now().strftime("%Y-%m-%d")

protocol_subagent = {
    "name": "protocol-specialist",
    "description": "Delegate protocol drafting, constraint checking, and checklist assembly here.",
    "system_prompt": PROTOCOL_SUBAGENT_PROMPT.format(date=today),
    "tools": TOOLS,
}

analysis_subagent = {
    "name": "analysis-specialist",
    "description": "Delegate cycle CSV analysis, preprocessing questions, and KPI summaries here.",
    "system_prompt": ANALYSIS_SUBAGENT_PROMPT.format(date=today),
    "tools": TOOLS,
}

report_subagent = {
    "name": "report-specialist",
    "description": "Delegate report drafting and review-ready markdown summaries here.",
    "system_prompt": REPORT_SUBAGENT_PROMPT.format(date=today),
    "tools": TOOLS,
}

agent = create_deep_agent(
    model=model,
    tools=TOOLS,
    system_prompt=MAIN_SYSTEM_PROMPT.format(
        date=today,
        repo_root=str(REPO_ROOT),
        sample_dir=str(SAMPLES_DIR),
    ),
    subagents=[protocol_subagent, analysis_subagent, report_subagent],
)
