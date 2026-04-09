"""LangGraph entrypoint for the Battery Lab Assistant deep agent."""

from __future__ import annotations

import os
from datetime import datetime

from deepagents import create_deep_agent
from dotenv import load_dotenv
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

# Allow the local LangGraph server and UI to start even before a real key is added.
if MODEL_NAME.startswith("openai:") and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "replace-with-real-openai-key"

model = init_chat_model(model=MODEL_NAME, temperature=TEMPERATURE)

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
