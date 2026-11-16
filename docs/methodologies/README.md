# Methodology-aware agent proposals

AgentCreator proposes an agent only when the workspace engine can run the methodology its job
needs. Availability is runtime evidence, not repository data.

## Turn flow

1. `list_methodologies` is the first workspace read of every turn.
2. The complete response is placed in the model context beside the workspace's datasets and
   Pipelines.
3. A job that needs a runnable methodology may be proposed. Its proposal records the dependency as
   `"methodologies": ["M-n"]`.
4. A job that needs an unavailable methodology is declined. The structured decline and the words
   shown to the person name the methodology and the registry's `issue`.
5. Approved Pipelines are grantable only when their graph and methodology are runnable. A granted
   Pipeline's methodology must also appear in `proposal.methodologies`.

The validator repeats these checks after the model answers. A proposal cannot pass by naming an
unknown or unavailable methodology, omitting the dependency of a granted Pipeline, or granting an
approved Pipeline whose engine reports `runnable: false`.

## Older engines

A workspace whose engine predates the registry answers `unknown_capability`. That exact response
activates the compatibility contract: M-1 (churn / GBDT classification) is the only runnable
methodology. AgentCreator says that limitation when it declines any other methodology. Other
registry errors do not activate the fallback and cannot be treated as evidence that work runs.

## Lake boundary

Production turns use the person's delegated lake credential and customer id. The runtime's
workspace tools pass reads through lake's workspace authorization and audit path. The live eval
runner calls lake's `workspace_query` with
`{"customer_id": "...", "capability": "list_methodologies", "input": {}}`, the same envelope used
for its other workspace reads.

## The grant

On a deployed turn the runtime makes a tool only of what the agent's record grants
(agent-runtime's `lake_grant`), so the read must be granted, not just called. `search` and
`summarize` do not grant `list_methodologies`; `pipelines` does, so `definition/record.json` carries
`["search", "summarize", "pipelines"]`.
`definition/agent.toml`'s `tools` allow-list then keeps AgentCreator to exactly the twelve reads a
turn makes, so none of `pipelines`' proposals is ever one of its tools.

## Verification

`uv run pytest` uses a fake workspace client to cover a runnable proposal, an unsupported decline
with its issue, the old-engine fallback, first-call ordering, and the proposal validator. The live
eval runner derives one runnable and one unsupported case from the registry response instead of
hard-coding portfolio status.

`tests/test_grants.py` runs the turn against a workspace that answers only the tools agent-runtime
would give this record: the reads of its skills from agent-runtime's `skills.json` (vendored at
`tests/fixtures/agent-runtime-skills.json`), plus every agent's App and build reads, filtered by the
allow-list. It fails when a turn makes a read the record does not grant, and when the allow-list
differs from the reads a turn makes. Refresh the fixture when agent-runtime's skills change:
`git -C <agent-runtime checkout> show origin/dev:skills.json > tests/fixtures/agent-runtime-skills.json`.
