# Agent definition

`instructions.md` is prompt v2. It requires methodology-dependent jobs to use the turn's live
registry facts, records runnable dependencies on proposals, and returns structured declines for
unsupported methods. `agent/` contains the deterministic checks that enforce those instructions.

`record.json` and `agent.toml` keep AgentCreator as a definition on `agent-runtime`; it proposes
agents and creates nothing.
