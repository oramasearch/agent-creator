# Releases

One page per tagged release, newest first. A page states what the release includes, what it does
not include, known issues, verification output, and where the image runs. The first release lists
everything the agent does: its definition, every Lake capability it reads, the HTTP API and the
agent bus it is reached through, and its environment.

A release has one `vX.Y.Z` name shared by the Git tag, the GitHub release and the Docker Hub
image tag `oramasearch/agent-creator:vX.Y.Z`. The image tag names the digest already deployed and
verified; it is never produced by a second build.

| Release | Date | Summary |
|---|---|---|
| [v0.3.1](v0.3.1.md) | 2026-11-16 | A patch release: a clean Dockerfile header, on agent-runtime v0.3.1; the definition is unchanged |
| [v0.3.0](v0.3.0.md) | 2026-11-16 | The MIT licence, a security policy and the public-export preparation, on agent-runtime v0.3.0 (bounded bus consumer and conversation memory, base images pinned by digest) |
| [v0.2.0](v0.2.0.md) | 2026-10-25 | A minor release: the methodology registry is readable (the `pipelines` skill grants `list_methodologies`), a `tools` allow-list of exactly its reads, and agent-runtime v0.2.0's security fixes underneath (service token always required, a turn's key only to `LAKE_URL`) |
| [v0.1.0](v0.1.0.md) | 2026-10-17 | The first release: the Agent Creator Agent as a definition on agent-runtime, prompt v5, its rule-checked proposals (skills, methodologies, solutions, Apps and builds, Pipelines, code) and the image |

`pyproject.toml`'s `[project].version` is the one place the version is set; `tests/test_release.py`
fails when that version has no page here or is not listed in this table.
