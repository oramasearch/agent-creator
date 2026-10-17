# Releases

One page per tagged release, newest first. A page states what the release includes, what it does
not include, known issues, verification output, and where the image runs. The first release lists
everything the agent does: its definition, every Lake capability it reads, the HTTP API and the
agent bus it is reached through, and its environment.

A release has one `vX.Y.Z` name shared by the Git tag, the GitHub release and the private Docker Hub
image tag `oramasearch/agent-creator:vX.Y.Z`. The image tag names the digest already deployed and
verified; it is never produced by a second build.

| Release | Date | Summary |
|---|---|---|
| [v0.1.0](v0.1.0.md) | 2026-10-17 | The first release: the Agent Creator Agent as a definition on agent-runtime, prompt v5, its rule-checked proposals (skills, methodologies, solutions, Apps and builds, Pipelines, code) and the private image |

`pyproject.toml`'s `[project].version` is the one place the version is set; `tests/test_release.py`
fails when that version has no page here or is not listed in this table.
