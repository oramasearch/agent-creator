# AgentCreator entrypoint

`main.py` reads live Apps, builds, retained event batches, solution and methodology availability
before proposing. It validates App read grants, live topics, proposal-only actions and
ApplicationAgent delegation; details every listed solution through `get_solution`; applies the
documented M-1 methodology fallback; filters approved Pipelines by runtime support; and validates
proposal dependencies or structured declines before returning the answer.
