# Architecture

## Core shape

This repo now follows the official split:

- `deepagents` provides the agent harness and LangGraph graph.
- `deep-agents-ui` provides the chat UI.

The battery-specific value sits on top of that in a small domain package.

## Runtime layers

### 1. Frontend

`ui/` is an upstream `deep-agents-ui` copy with light changes:

- Battery Lab Assistant branding
- default local deployment settings
- clearer connection copy for the local battery agent

### 2. LangGraph deployment

`langgraph.json` exposes one graph:

- `battery_lab -> ./agent.py:agent`

Run it locally with `uv run langgraph dev`.

### 3. Agent entrypoint

`agent.py` creates a `deepagents` agent with:

- an OpenAI-compatible chat model
- battery-specific starter tools
- a protocol specialist sub-agent
- an analysis specialist sub-agent

### 4. Battery domain package

`battery_agent/` contains:

- `prompts.py`: system instructions and sub-agent instructions
- `kb.py`: structured knowledge loading and path helpers
- `tools.py`: starter tool implementations

### 5. Controlled knowledge

`data/kb/` remains the hard-constraint source for:

- chemistry profiles
- equipment rules
- objective templates
- safety checklists

This is where your real SOP, standard, and equipment content should be added.

## Design intent

- The LLM handles planning, delegation, explanation, and synthesis.
- Structured knowledge and tools handle constraints and calculations.
- The UI remains the official `deep-agents-ui` interaction model.
- Approval gates are the next LangGraph feature to add, not something hidden in prompt text.
