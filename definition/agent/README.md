# AgentCreator entrypoint

`main.py` reads live Apps, builds, retained event batches, solution and methodology availability
before proposing. It validates App read grants, live topics, proposal-only actions and
ApplicationAgent delegation; details every listed solution through `get_solution`; applies the
documented M-1 methodology fallback; filters approved Pipelines by runtime support; and validates
proposal dependencies or structured declines before returning the answer.

Workspace facts are bounded and sent to the model as untrusted data in their own delimited message,
never in the system message; event log lines are never sent (agent-creator#22,
[`docs/apps/README.md`](../../docs/apps/README.md#bounds-and-untrusted-data)). The code check parses
proposed Python and refuses imports outside the runtime's set (which leaves out `os`, `sys`,
`subprocess`, `urllib`, `http`, `importlib` and the like) and the names that get round it
(`__import__`, `exec`, `eval`, `compile`, `__subclasses__`, `__globals__` and the like). It is a
compatibility check, not a review: the reply tells the person the code is unreviewed and lists
every grant and file.
