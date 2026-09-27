# CLAUDE.md — agent-creator

AgentCreator, the agent behind lake's Agent Factory. Read the zetta-bridge `CLAUDE.md` (*Agents in
lake*) and `docs/agents/scaffold.md` first; the org rules in `oramasearch/orama-bridge` apply.

- **It is a definition** (`definition/`: `record.json`, `agent.toml`, `instructions.md`, `agent/`)
  that runs on `agent-runtime`. The image is the runtime plus this directory, nothing else.
- **It proposes and never creates.** lake creates the agent when the person approves (lake#233).
- **Every rule a proposal must meet is code** in `agent/main.py` (`defects`), not prompt text alone:
  skills from Studio's set, approved Pipelines only, code that compiles and imports only what the
  runtime ships, no secrets, storage that fits the code.
- **Evals are generated and rule-graded** (`evals/run.py`), run against a real workspace. A prompt
  change is a new version of `instructions.md` noted in the report.
