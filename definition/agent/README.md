# AgentCreator entrypoint

`main.py` reads solution and methodology availability before the rest of the workspace facts on
every turn. It details every listed solution through `get_solution`, treats an unknown solution
registry as not deployed, applies the documented M-1 methodology fallback, filters approved
Pipelines by runtime support, and validates solution authority, proposal dependencies or
structured declines before returning the answer.
