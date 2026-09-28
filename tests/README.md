# AgentCreator unit tests

`test_creator.py` uses a fake lake/workspace and scripted model replies. It covers exact App and
build list/detail/event inputs, live topic validation, read-only grants, proposal-only mutations,
the exact `agent.toml` tool allow-list, ApplicationAgent delegation, turn-scoped solution reads,
exact autonomy and A1 gates, structured declines, old-engine contracts, proposal validation,
repair behavior and person-readable replies.
