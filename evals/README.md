# AgentCreator eval runner

`run.py` keeps the generated Studio skill/work-area/code matrix and adds live methodology cases.
It selects one runnable and one unsupported entry from `list_methodologies`, then verifies that the
runnable proposal records its dependency and the unsupported answer declines with the registry's
issue. Workspace reads use lake's `workspace_query` envelope.
