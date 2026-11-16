# CLAUDE.md — agent-creator

AgentCreator, the agent behind Lake's Agent Factory. Read `README.md` and `docs/README.md` first;
`AGENTS.md` carries the conventions that apply to every change.

- **It is a definition** (`definition/`: `record.json`, `agent.toml`, `instructions.md`, `agent/`)
  that runs on `agent-runtime`. The image is the runtime plus this directory, nothing else.
- **It asks, declines unsupported work or proposes, and never creates.** Lake creates the agent
  when the person approves.
- **Every rule a proposal must meet is code** in `agent/main.py` (`defects`), not prompt text alone:
  live App/build read grants with proposal-only writes, runnable solutions and methodologies,
  exact solution autonomy with A1 approval gates, skills from agent-runtime's set, approved runnable
  Pipelines only, code that compiles and imports only what the runtime ships, no secrets, storage
  that fits the code.
- **Evals are generated and rule-graded** (`evals/run.py`), run against a real workspace. A prompt
  change is a new version of `instructions.md` noted in the report.
- Build and test with uv, never pip: `uv sync`, then `uv run --group dev pytest`.
