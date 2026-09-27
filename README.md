# agent-creator

**AgentCreator**, the agent behind lake's **Agent Factory** ([lake#228](https://github.com/oramasearch/lake/issues/228),
[zetta#1017](https://github.com/oramasearch/zetta/issues/1017), [lake#233](https://github.com/oramasearch/lake/issues/233)),
and an entry of the Agent Library. A person tells it what they want an agent for; it asks what it
must (one question at a time) and then proposes the agent in Studio's shape: native or Python, and
for Python whether its code is stored in Zetta or a lake repository. **It creates nothing**: lake
shows the proposal and creates the agent only when the person approves it.

## How it runs

It is a **definition** on [`agent-runtime`](https://github.com/oramasearch/agent-runtime), not a
program of its own:

```
definition/
  record.json      its AgentRecord: kind orama, skills search + summarize (the reads it needs)
  agent.toml       entrypoint agent.main:run, model gpt-5.5, dependencies openai
  instructions.md  the prompt (v1)
  agent/main.py    the turn: read the workspace, ask or propose, check the proposal
```

The image `oramasearch/agent-creator` is `oramasearch/agent-runtime` plus `definition/`, served
lake-wide in service mode with **per-turn credentials**: every turn carries the person's delegated
lake key and space, so what it reads is what they may read.

## What a proposal must pass

`agent/main.py`'s `defects` is the review, run before the person sees anything; a proposal that
fails gets one repair round and is otherwise returned **with** its defects, never as clean:

- skills only from Studio's set (`search`, `generate-data`, `train`, `summarize`, `call-api`);
- work area `workspace`, `project` or `dataset`;
- Pipelines only from the workspace's **approved** ones (read live: `list_projects`, `get_project`);
- a native agent carries no code; a Python agent is stored in `zetta` or `lake`, and in `lake` when
  its code is larger than inline storage allows;
- code compiles, imports only the standard library and the runtime's packages, stays inside the
  definition, and carries no secret.

## Evals

`evals/run.py` generates asks from Studio's skills × work areas × with/without code (16 cases),
runs them live against a real workspace, and grades by rule: `defects` must be empty, the answer
must be a proposal, the named skill must be granted, and an ask that needs code must not get a
native agent. Reports land in [`reports/`](reports/); no score is claimed that the runner did not
produce.

```sh
LAKE_URL=https://lake.oramadev.net LAKE_TOKEN=<a person's token> CUSTOMER_ID=<their space> \
  uv run python evals/run.py
```

## Image

Private on Docker Hub as `oramasearch/agent-creator`, built on the cluster BuildKit from a pushed
runtime tag:

```sh
buildctl ... build --frontend dockerfile.v0 --local context=. --local dockerfile=. \
  --opt build-arg:RUNTIME_TAG=<agent-runtime tag> --opt platform=linux/amd64 \
  --output type=image,name=docker.io/oramasearch/agent-creator:<tag>,push=true
```

## Tests

`uv run pytest`: the facts are only approved Pipelines, a good proposal is clean, every rule
catches its defect, one repair round, a twice-defective proposal keeps its defects, and a question
is an answer.

## Known failures and limits

- It proposes only what the fixed skills can do; an agent that needs a new kind of access needs a
  new skill in agent-runtime first.
- It checks that Python compiles, not that it does the right thing: lake's check job after
  creation (lake#233) is where a new agent first runs.
