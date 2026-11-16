# agent-creator

**AgentCreator**, the agent behind lake's **Agent Factory**,
and an entry of the Agent Library. A person tells it what they want an agent for; it asks what it
must (one question at a time), declines work the workspace engine cannot run, or proposes the agent
in Studio's shape: native or Python, and for Python whether its code is stored in Zetta or a lake
repository. **It creates nothing**: lake shows the proposal and creates the agent only when the
person approves it.

**Current release: [v0.3.1](docs/releases/v0.3.1.md)** (all releases: [`docs/releases/`](docs/releases/README.md)).

## How it runs

It is a **definition** on [`agent-runtime`](https://github.com/oramasearch/agent-runtime), not a
program of its own:

```
definition/
  record.json      its AgentRecord: kind orama, skills search + summarize + pipelines (the reads it needs)
  agent.toml       entrypoint agent.main:run, model gpt-5.5, dependencies openai, tools = its reads only
  instructions.md  the prompt (v5)
  agent/main.py    the turn: read the workspace, ask, decline or propose, then check the answer
```

The image `oramasearch/agent-creator` is `oramasearch/agent-runtime` plus `definition/`, served
lake-wide in service mode with **per-turn credentials**: every turn carries the person's delegated
lake key and space, so what it reads is what they may read.

## What a proposal must pass

`agent/main.py`'s `defects` is the review, run before the person sees anything; a proposal that
fails gets one repair round and is otherwise returned **with** its defects, never as clean:

- an App agent is Python, grants only the lake App/build reads it needs, subscribes to live
  `app-events.<app-id>` / `build-events.*`, and can only propose mutations for confirmation and an
  `app` turn to ApplicationAgent;
- a solution-bound agent uses one runnable entry from the turn's live `list_solutions` /
  `get_solution` reads, carries its exact autonomy defaults, approval-gates every A1 action, and
  gets `decide`, `list_ledger`, `get_monitor` and `get_roi_readout` but not `approve_decision`;
- skills only from agent-runtime's set (`search`, `generate-data`, `train`, `summarize`, `call-api`,
  and Lake's own areas: `drives`, `transcripts`, `repositories`, `datasets`, `streams`, `pipelines`,
  `usage`; agent-runtime#7);
- work area `workspace`, `project` or `dataset`;
- methodology dependencies only from the workspace's live `list_methodologies` response and only
  when `runnable: true`; unsupported work is declined with its methodology and tracking issue;
- Pipelines only from the workspace's **approved, runnable** ones (read live: `list_projects`,
  `get_project`), with the Pipeline's methodology recorded on the proposal;
- a native agent carries no code; a Python agent is stored in `zetta` or `lake`, and in `lake` when
  its code is larger than inline storage allows;
- code compiles, imports only the standard library and the runtime's packages, stays inside the
  definition, and carries no secret.

## Evals

`evals/run.py` generates asks from Studio's skills × work areas × with/without code, then adds live
App/build, methodology and solution cases. It runs them against a real workspace and grades by
rule: `defects` must be empty, ordinary asks must be proposals, App grants and live dependencies
must be recorded, unsupported work must be declined with the engine's issue, the named skill must
be granted, and an ask that needs code must not get a native agent. Reports land in
[`reports/`](reports/); no score is claimed that the runner did not produce.

```sh
LAKE_URL=https://lake.example.com LAKE_TOKEN=<a person's token> CUSTOMER_ID=<their space> \
  uv run python evals/run.py
```

## Image

Published on Docker Hub as `oramasearch/agent-creator`, built on a pushed agent-runtime tag:

```sh
docker buildx build --platform linux/amd64 --build-arg RUNTIME_TAG=<agent-runtime tag> \
  -t <registry>/agent-creator:<tag> --push .
```

## Tests

`uv run pytest`: the facts are live Apps, builds, retained events, solution details and approved
Pipelines; a good proposal is clean; every rule catches its defect; and the suite covers runnable
and unsupported solutions and methodologies, both old-engine paths, one repair round, a
twice-defective proposal and questions.

## Apps and builds

AgentCreator reads `list_apps`, `get_app`, `receive_app_events`, `list_builds`, `get_build` and
`receive_build_events` through the person's lake grant on every turn. An App proposal declares its
read capabilities and event topics separately from proposal tools and writes their exact combined
allow-list to `agent.toml`. agent-runtime records a proposal tool's input but never calls its
mutation route; after the person confirms, lake delegates an `app` turn to
`agent-application`, which builds and changes Apps through its own confirmation flow. The complete
fact, topic, input and proposal contract is in [`docs/apps/`](docs/apps/README.md).

## Methodology availability

AgentCreator reads `list_methodologies` on every turn. The response is turn-scoped: it never carries
a local copy of the 21-method portfolio, because methods become runnable as the engine gains
implementations. A proposal records its methodology ids in `proposal.methodologies`; a method with
`runnable: false` produces a structured decline that names the registry's issue.

An older engine answers `unknown_capability`. Only in that state AgentCreator uses the compatibility
contract that M-1 (churn / GBDT classification) runs and says that every other methodology is
unavailable. The full behavior and response shapes are in
[`docs/methodologies/`](docs/methodologies/README.md).

## Solution availability

AgentCreator reads `list_solutions` and details every returned entry with `get_solution` on every
turn. A business problem that matches a runnable catalogue entry gets one solution binding with
the operating capabilities, exact autonomy defaults and explicit A1 approval gates. A matching
entry that does not run is declined with its live issue; a sketch also names its promotion
condition. An older engine's `unknown_capability` means the solution registry is not deployed yet
and supplies no compatibility solution. The complete binding and refusal contract is in
[`docs/solutions/`](docs/solutions/README.md).

## Known failures and limits

- It proposes only what the fixed skills can do; an agent that needs a new kind of access needs a
  new skill in agent-runtime first.
- It checks that Python compiles, not that it does the right thing: lake's check job after
  creation is where a new agent first runs.


## Its answer

`run` answers `{"reply": <words>, "result": {kind, question | decline | proposal, defects,
facts}}`: the question, decline, or proposal in one sentence for a person; the structured answer
for lake's Factory page and API callers. It needs an agent-runtime that returns
`result`.

## License

MIT, see [LICENSE](LICENSE). Third-party components and their licenses are in
[THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES). Contributions are welcome under the
[Contributor License Agreement](CLA.md); see [CONTRIBUTING.md](CONTRIBUTING.md).
