# AgentCreator unit tests

`test_creator.py` uses a fake lake/workspace and scripted model replies. It covers exact App and
build list/detail/event inputs, live topic validation, read-only grants, proposal-only mutations,
the exact `agent.toml` tool allow-list, ApplicationAgent delegation, turn-scoped solution reads,
exact autonomy and A1 gates, structured declines, old-engine contracts, proposal validation,
repair behavior and person-readable replies. Its agent-creator#22 tests check that a build log's
instruction never reaches the model and does not change the proposal, that workspace facts are a
delimited message outside the system message that no value can close, that 500 builds of 1000
events each stay within the bounds, that `__import__`, `os`, `urllib`, `subprocess`, `exec`, `eval`
and `__subclasses__` are defects, and that the reply lists every grant and file.

`test_grants.py` runs the turn's reads against only the tools agent-runtime would give
AgentCreator's own record (its skills' reads from the vendored `fixtures/agent-runtime-skills.json`,
the App and build reads, and `agent.toml`'s allow-list), so a read the record does not grant fails
here instead of on a deployed turn (agent-creator#11).

`test_release.py` reads the version from `pyproject.toml` and fails when
`docs/releases/v<version>.md` is missing, does not name that version in its first heading, or is not
listed in `docs/releases/README.md`.
