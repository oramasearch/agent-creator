# Agent definition

`instructions.md` is prompt v4. It requires App, solution and methodology jobs to use the turn's
live facts. App agents grant only lake reads and keep every mutation proposal-only for confirmed
delegation to ApplicationAgent; solution jobs bind exact autonomy defaults; methodology jobs
record runnable dependencies. `agent/` contains the deterministic checks that enforce those
instructions.

`record.json` and `agent.toml` keep AgentCreator as a definition on `agent-runtime`; it proposes
agents and creates nothing.
