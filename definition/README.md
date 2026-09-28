# Agent definition

`instructions.md` is prompt v3. It requires solution jobs and methodology-dependent jobs to use
the turn's live registry facts, binds runnable solutions with their exact autonomy defaults,
records runnable dependencies on proposals, and returns structured declines for unsupported work.
`agent/` contains the deterministic checks that enforce those instructions.

`record.json` and `agent.toml` keep AgentCreator as a definition on `agent-runtime`; it proposes
agents and creates nothing.
