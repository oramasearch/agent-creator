"""AgentCreator's turn: read the workspace, then ask, decline or propose and check the answer.

It proposes and never creates: lake's Agent Factory shows the proposal and creates the agent only
on the person's approval (lake#233). Everything it may put in a proposal is checked here, by rules,
before the person sees it: App and build authority from lake's live grant, solution authority from
the live registry, skills from the runtime's set, Pipelines that exist and are approved, code that
compiles and imports only what the runtime ships, no secrets, and storage that fits the code.
"""

from __future__ import annotations

import json
import re
import tomllib
from typing import Any

# The skills a person may grant (agent-runtime#7): Studio's five and Lake's own areas. agent-runtime
# decides what each lets an agent do (its skills.py and skills.json); the workspace engine's agent
# record and lake's pages accept exactly these names.
SKILLS = {"search", "generate-data", "train", "summarize", "call-api", "drives", "transcripts",
          "repositories", "datasets", "streams", "pipelines", "usage"}
WORK_AREAS = {"workspace", "project", "dataset"}
RUNTIME_PACKAGES = {"openai", "httpx", "pydantic", "pandas", "numpy"}
SOLUTION_CAPABILITIES = ["decide", "list_ledger", "get_monitor", "get_roi_readout"]
APP_READ_CAPABILITIES = [
    "list_apps",
    "get_app",
    "receive_app_events",
    "list_builds",
    "get_build",
    "receive_build_events",
]
APP_ACTION_CAPABILITIES = {
    "create_app",
    "deploy_app",
    "rollback_app",
    "delete_app",
    "set_app_env",
    "unset_app_env",
    "set_app_auth",
    "restart_app",
    "stop_app",
    "start_app",
    "scale_app",
    "set_app_zetta_binding",
    "bind_service_to_app",
    "unbind_service_from_app",
    "create_service_and_bind_to_app",
    "build_image",
    "build_app",
    "cancel_build",
}
APP_DELEGATION = {
    "agent": "agent-application",
    "kind": "app",
}
APP_FACT_SOURCE = (
    "list_apps/get_app/receive_app_events; "
    "list_builds/get_build/receive_build_events"
)
INLINE_LIMIT = 900 * 1024
SECRET = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{20,}|(password|secret|token)\s*=\s*"
                    r"['\"][^'\"]{6,}['\"])", re.I)
LEGACY_METHODOLOGY = {
    "id": "M-1",
    "name": "Churn / GBDT classification",
    "family": "classification",
    "model_kinds": ["gbdt"],
    "solutions": [],
    "inputs": [],
    "outputs": [],
    "metrics": [],
    "runnable": True,
    "partial": False,
}


def _tool_error(reply: Any) -> str:
    """A failed runtime tool's error, including the capability code when it returned one."""
    error = getattr(reply, "error", "")
    if isinstance(error, dict):
        return f"{error.get('code', '')}: {error.get('message', '')}".strip(": ")
    if error:
        return str(error)
    value = getattr(reply, "value", None)
    if isinstance(value, dict):
        nested = value.get("error")
        if isinstance(nested, dict):
            return f"{nested.get('code', '')}: {nested.get('message', '')}".strip(": ")
        if value.get("code"):
            return str(value["code"])
    return "workspace capability failed"


def methodology_facts(context) -> dict[str, Any]:
    """The live registry for this turn, or the documented old-engine M-1 fallback."""
    listed = context.call_tool("list_methodologies", {})
    if listed.ok and isinstance(listed.value, dict):
        methods = listed.value.get("methodologies")
        if isinstance(methods, list):
            return {
                "methodologies": [item for item in methods if isinstance(item, dict)],
                "methodology_source": "list_methodologies",
                "methodology_error": "",
            }
        return {
            "methodologies": [],
            "methodology_source": "unavailable",
            "methodology_error": "list_methodologies returned no methodologies list",
        }

    error = _tool_error(listed)
    if "unknown_capability" in error:
        return {
            "methodologies": [dict(LEGACY_METHODOLOGY)],
            "methodology_source": "old-engine fallback",
            "methodology_error": "list_methodologies is unknown; only M-1 runs",
        }
    return {
        "methodologies": [],
        "methodology_source": "unavailable",
        "methodology_error": error,
    }


def solution_facts(context) -> dict[str, Any]:
    """The live solution details for this turn, with no old-engine fallback."""
    listed = context.call_tool("list_solutions", {})
    if not listed.ok or not isinstance(listed.value, dict):
        error = _tool_error(listed)
        if "unknown_capability" in error:
            return {
                "solutions": [],
                "solution_source": "not_deployed",
                "solution_error": "list_solutions is not deployed yet in this workspace",
            }
        return {
            "solutions": [],
            "solution_source": "unavailable",
            "solution_error": error,
        }

    summaries = listed.value.get("solutions")
    if not isinstance(summaries, list):
        return {
            "solutions": [],
            "solution_source": "unavailable",
            "solution_error": "list_solutions returned no solutions list",
        }

    solutions: list[dict[str, Any]] = []
    detail_errors: list[str] = []
    for summary in summaries:
        if not isinstance(summary, dict) or not summary.get("id"):
            detail_errors.append("list_solutions returned an entry without an id")
            continue
        identifier = str(summary["id"])
        got = context.call_tool("get_solution", {"solution": identifier})
        if not got.ok or not isinstance(got.value, dict):
            error = _tool_error(got)
            if "unknown_capability" in error:
                error = "get_solution is not deployed yet in this workspace"
            detail_errors.append(f"get_solution {identifier}: {error}")
            continue
        solution = got.value.get("solution")
        if not isinstance(solution, dict):
            detail_errors.append(f"get_solution {identifier} returned no solution")
            continue
        solutions.append(solution)

    return {
        "solutions": solutions,
        "solution_source": "list_solutions/get_solution",
        "solution_error": "; ".join(detail_errors),
    }


def _lake_arguments(context, **arguments: Any) -> dict[str, Any]:
    turn_input = getattr(context, "input", {})
    customer_id = turn_input.get("customer_id") if isinstance(turn_input, dict) else ""
    if customer_id:
        return {"customer_id": customer_id, **arguments}
    return arguments


def _app_inventory(
    context,
    granted_reads: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], bool]:
    required = {"list_apps", "get_app", "receive_app_events"}
    missing = required - granted_reads
    if missing:
        return [], [], [f"App reads not granted: {sorted(missing)}"], False
    listed = context.call_tool("list_apps", _lake_arguments(context))
    if not listed.ok or not isinstance(listed.value, dict):
        return [], [], [f"list_apps: {_tool_error(listed)}"], False
    summaries = listed.value.get("apps")
    if not isinstance(summaries, list):
        return [], [], ["list_apps returned no apps list"], False

    apps: list[dict[str, Any]] = []
    event_batches: list[dict[str, Any]] = []
    errors: list[str] = []
    for summary in summaries:
        if not isinstance(summary, dict):
            errors.append("list_apps returned an app that is not an object")
            continue
        app_id = str(summary.get("id") or summary.get("app_id") or "")
        if not app_id:
            errors.append("list_apps returned an app without an id")
            continue
        got = context.call_tool("get_app", _lake_arguments(context, app_id=app_id))
        if got.ok and isinstance(got.value, dict):
            apps.append(got.value)
        else:
            errors.append(f"get_app {app_id}: {_tool_error(got)}")
        events = context.call_tool(
            "receive_app_events",
            _lake_arguments(context, app_id=app_id, from_sequence=1, wait_ms=0),
        )
        if events.ok and isinstance(events.value, dict):
            event_batches.append({"app_id": app_id, **events.value})
        else:
            errors.append(f"receive_app_events {app_id}: {_tool_error(events)}")
    return apps, event_batches, errors, True


def _build_inventory(
    context,
    granted_reads: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], bool]:
    required = {"list_builds", "get_build", "receive_build_events"}
    missing = required - granted_reads
    if missing:
        return [], [], [f"build reads not granted: {sorted(missing)}"], False
    listed = context.call_tool("list_builds", _lake_arguments(context))
    if not listed.ok or not isinstance(listed.value, dict):
        return [], [], [f"list_builds: {_tool_error(listed)}"], False
    summaries = listed.value.get("builds")
    if not isinstance(summaries, list):
        return [], [], ["list_builds returned no builds list"], False

    builds: list[dict[str, Any]] = []
    event_batches: list[dict[str, Any]] = []
    errors: list[str] = []
    for summary in summaries:
        if not isinstance(summary, dict):
            errors.append("list_builds returned a build that is not an object")
            continue
        build_id = str(summary.get("id") or summary.get("build_id") or "")
        if not build_id:
            errors.append("list_builds returned a build without an id")
            continue
        got = context.call_tool("get_build", _lake_arguments(context, build_id=build_id))
        if got.ok and isinstance(got.value, dict):
            builds.append(got.value)
        else:
            errors.append(f"get_build {build_id}: {_tool_error(got)}")
        events = context.call_tool(
            "receive_build_events",
            _lake_arguments(context, build_id=build_id, from_sequence=1, wait_ms=0),
        )
        if events.ok and isinstance(events.value, dict):
            event_batches.append({"build_id": build_id, **events.value})
        else:
            errors.append(f"receive_build_events {build_id}: {_tool_error(events)}")
    return builds, event_batches, errors, True


def app_facts(context) -> dict[str, Any]:
    """The live Ship Apps, builds and retained event batches visible to this turn."""
    granted = getattr(context, "app_capabilities", {})
    granted = granted if isinstance(granted, dict) else {}
    granted_reads = {
        item
        for item in granted.get("reads", [])
        if isinstance(item, str) and item in APP_READ_CAPABILITIES
    }
    granted_proposals = {
        item
        for item in granted.get("proposals", [])
        if isinstance(item, str) and item in APP_ACTION_CAPABILITIES
    }
    apps, app_events, app_errors, apps_available = _app_inventory(context, granted_reads)
    builds, build_events, build_errors, builds_available = _build_inventory(
        context,
        granted_reads,
    )
    return {
        "apps": apps,
        "app_events": app_events,
        "builds": builds,
        "build_events": build_events,
        "app_read_capabilities": [
            name for name in APP_READ_CAPABILITIES if name in granted_reads
        ],
        "app_action_capabilities": sorted(granted_proposals),
        "app_source": APP_FACT_SOURCE if apps_available and builds_available else "unavailable",
        "app_error": "; ".join(app_errors + build_errors),
    }


def workspace_facts(context) -> dict[str, Any]:
    """What exists: the datasets, and every approved Pipeline, read through the person's key."""
    # These reads are deliberately turn-scoped. Engine registries change as implementations land.
    facts: dict[str, Any] = {
        **solution_facts(context),
        **app_facts(context),
        **methodology_facts(context),
        "datasets": [],
        "pipelines": [],
        "unrunnable_pipelines": [],
    }
    datasets = context.call_tool("list_datasets", {})
    if datasets.ok and isinstance(datasets.value, dict):
        for item in datasets.value.get("datasets", []):
            facts["datasets"].append(item.get("name") if isinstance(item, dict) else str(item))
    projects = context.call_tool("list_projects", {})
    names = projects.value.get("projects", []) if projects.ok and isinstance(projects.value,
                                                                              dict) else []
    methods = {item.get("id"): item for item in facts["methodologies"]}
    for name in names:
        name = name if isinstance(name, str) else (name or {}).get("name", "")
        got = context.call_tool("get_project", {"name": name})
        if not got.ok or not isinstance(got.value, dict):
            continue
        for graph in got.value.get("graphs", []):
            if graph.get("approval") != "approved":
                continue
            pipeline = {"project": name, "graph": graph.get("name", "")}
            methodology = graph.get("methodology")
            if methodology:
                pipeline["methodology"] = methodology
            if "runnable" in graph:
                pipeline["runnable"] = graph.get("runnable") is True
            method = methods.get(methodology)
            runnable = graph.get("runnable") is not False
            if methodology:
                runnable = runnable and method is not None and method.get("runnable") is True
                if method is not None and method.get("issue"):
                    pipeline["issue"] = method["issue"]
            elif facts["methodology_source"] == "list_methodologies":
                runnable = False
            if runnable:
                facts["pipelines"].append(pipeline)
            else:
                facts["unrunnable_pipelines"].append(pipeline)
    return facts


def _methodology_map(facts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item.get("id"): item
        for item in facts.get("methodologies", [])
        if isinstance(item, dict) and item.get("id")
    }


def _solution_map(facts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item.get("id"): item
        for item in facts.get("solutions", [])
        if isinstance(item, dict) and item.get("id")
    }


def _solution_decline_defects(answer: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    identifier = str(answer.get("solution") or "")
    reason = str(answer.get("reason") or "")
    issue = str(answer.get("issue") or "")
    problems: list[str] = []

    if facts.get("solution_source") == "not_deployed":
        if identifier != "solution registry":
            problems.append(
                "an old engine decline must name the solution registry, not a solution id"
            )
        if issue:
            problems.append("an old engine decline cannot invent a solution issue")
        if "not deployed yet" not in reason:
            problems.append("an old engine decline must say list_solutions is not deployed yet")
        return problems
    if not identifier:
        problems.append("a solution decline must name the solution the job needs")
        return problems
    solution = _solution_map(facts).get(identifier)
    if solution is None:
        problems.append(f"solution {identifier} is not in this turn's solution registry")
        return problems
    if solution.get("runnable") is True and solution.get("status") != "sketch":
        problems.append(f"solution {identifier} is runnable and must not be declined")
    expected_issue = str(solution.get("issue") or "")
    if expected_issue and expected_issue not in issue and expected_issue not in reason:
        problems.append(f"the decline must name {expected_issue}")
    if solution.get("status") == "sketch":
        condition = str(solution.get("promotion_condition") or "")
        if condition and condition not in reason:
            problems.append("a sketch decline must repeat its promotion condition")
    return problems


def _object_set(value: Any) -> set[str] | None:
    """An order-independent, duplicate-free set of JSON objects."""
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        return None
    encoded = [json.dumps(item, sort_keys=True) for item in value]
    if len(set(encoded)) != len(encoded):
        return None
    return set(encoded)


def _decline_defects(answer: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    if "solution" in answer:
        return _solution_decline_defects(answer, facts)
    methodology = answer.get("methodology")
    reason = str(answer.get("reason") or "")
    issue = str(answer.get("issue") or "")
    methods = _methodology_map(facts)
    method = methods.get(methodology)
    problems: list[str] = []

    if not methodology:
        problems.append("a decline must name the methodology the job needs")
    if facts.get("methodology_source") == "old-engine fallback":
        if methodology == "M-1":
            problems.append("M-1 is runnable on this older workspace engine")
        if "only M-1" not in reason:
            problems.append("an old-engine decline must say that only M-1 runs")
        return problems
    if method is None:
        problems.append(f"methodology {methodology} is not in list_methodologies")
        return problems
    if method.get("runnable") is True:
        problems.append(f"methodology {methodology} is runnable and must not be declined")
    expected_issue = str(method.get("issue") or "")
    if expected_issue and expected_issue not in issue and expected_issue not in reason:
        problems.append(f"the decline must name {expected_issue}")
    return problems


def _solution_proposal_defects(proposal: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    """Check a solution binding against the details read during this turn."""
    binding = proposal.get("solution")
    if binding is None:
        return []
    if not isinstance(binding, dict):
        return ["solution must be an object with an id, capabilities, autonomy and approval_gates"]

    identifier = binding.get("id")
    solution = _solution_map(facts).get(identifier)
    if solution is None:
        return [f"solution {identifier} is not in this turn's solution registry"]

    problems: list[str] = []
    if solution.get("status") == "sketch":
        problems.append(f"solution {identifier} is a sketch and cannot operate")
    if solution.get("runnable") is not True:
        suffix = f" ({solution.get('issue')})" if solution.get("issue") else ""
        problems.append(f"solution {identifier} is not runnable{suffix}")

    capabilities = binding.get("capabilities")
    if (not isinstance(capabilities, list)
            or any(not isinstance(item, str) for item in capabilities)
            or len(capabilities) != len(SOLUTION_CAPABILITIES)
            or set(capabilities) != set(SOLUTION_CAPABILITIES)):
        problems.append(
            "a solution agent's capabilities must be decide, list_ledger, get_monitor and "
            "get_roi_readout"
        )

    expected_autonomy = solution.get("autonomy_defaults") or []
    proposed_autonomy = binding.get("autonomy")
    expected_autonomy_set = _object_set(expected_autonomy)
    proposed_autonomy_set = _object_set(proposed_autonomy)
    if (expected_autonomy_set is None
            or proposed_autonomy_set is None
            or proposed_autonomy_set != expected_autonomy_set):
        problems.append("solution autonomy must exactly match this turn's autonomy defaults")

    expected_gates = [
        item.get("action_class")
        for item in expected_autonomy
        if isinstance(item, dict) and item.get("autonomy") == "A1"
    ]
    approval_gates = binding.get("approval_gates")
    if (not isinstance(approval_gates, list)
            or any(not isinstance(item, str) for item in approval_gates)
            or len(approval_gates) != len(expected_gates)
            or set(approval_gates) != set(expected_gates)):
        problems.append("every A1 action class must stay approval-gated")
    return problems


def _app_proposal_defects(proposal: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    """Keep app reads grantable and every app or build mutation proposal-only."""
    access = proposal.get("app_capabilities")
    if access is None:
        return []
    if not isinstance(access, dict):
        return ["app_capabilities must be an object"]

    problems: list[str] = []
    if facts.get("app_source") != APP_FACT_SOURCE:
        problems.append("app and build capabilities are unavailable for this turn")
    if proposal.get("type") != "python":
        problems.append("an app event subscription requires a python agent")

    reads = access.get("reads")
    if not isinstance(reads, list) or any(not isinstance(item, str) for item in reads):
        problems.append("app reads must be a list of capability names")
        reads = []
    elif not reads or len(reads) != len(set(reads)):
        problems.append("app reads must be non-empty and duplicate-free")
    unknown_reads = set(reads) - set(facts.get("app_read_capabilities", []))
    if unknown_reads:
        problems.append(f"app reads outside this turn's grant: {sorted(unknown_reads)}")

    subscriptions = access.get("subscriptions")
    if (not isinstance(subscriptions, list)
            or any(not isinstance(item, str) for item in subscriptions)):
        problems.append("app subscriptions must be a list of topic names")
        subscriptions = []
    elif not subscriptions or len(subscriptions) != len(set(subscriptions)):
        problems.append("app subscriptions must be non-empty and duplicate-free")

    app_ids = {str(item.get("id") or item.get("app_id"))
               for item in facts.get("apps", []) if isinstance(item, dict)}
    build_ids = {str(item.get("id") or item.get("build_id"))
                 for item in facts.get("builds", []) if isinstance(item, dict)}
    for topic in subscriptions:
        if topic.startswith("app-events."):
            app_id = topic.removeprefix("app-events.")
            if not app_id or app_id == "*" or app_id not in app_ids:
                problems.append(f"subscription {topic} does not name a live app from this turn")
            if "receive_app_events" not in reads:
                problems.append("app-events subscriptions require receive_app_events")
        elif topic == "build-events.*":
            if "receive_build_events" not in reads or "list_builds" not in reads:
                problems.append(
                    "build-events.* requires list_builds and receive_build_events"
                )
        elif topic.startswith("build-events."):
            build_id = topic.removeprefix("build-events.")
            if not build_id or build_id not in build_ids:
                problems.append(f"subscription {topic} does not name a live build from this turn")
            if "receive_build_events" not in reads:
                problems.append("build-events subscriptions require receive_build_events")
        else:
            problems.append(f"unsupported app subscription topic {topic}")

    proposed = access.get("proposals")
    if not isinstance(proposed, list) or any(not isinstance(item, str) for item in proposed):
        problems.append("app proposals must be a list of app or build capability names")
        proposed = []
    elif len(proposed) != len(set(proposed)):
        problems.append("app proposals must not contain duplicates")
    unknown_actions = set(proposed) - set(facts.get("app_action_capabilities", []))
    if unknown_actions:
        problems.append(f"app proposals outside this turn's grant: {sorted(unknown_actions)}")
    if access.get("application_agent") != APP_DELEGATION:
        problems.append("app changes must delegate an app turn to agent-application")

    config_files = [
        item
        for item in proposal.get("files", [])
        if isinstance(item, dict) and item.get("path") == "agent.toml"
    ]
    if len(config_files) != 1:
        problems.append("an app agent needs one agent.toml tool allow-list")
        return problems
    try:
        settings = tomllib.loads(str(config_files[0].get("contents") or ""))
    except tomllib.TOMLDecodeError:
        return problems
    allowed = settings.get("tools")
    expected = set(reads) | set(proposed)
    if (not isinstance(allowed, list)
            or any(not isinstance(item, str) for item in allowed)
            or len(allowed) != len(set(allowed))
            or set(allowed) != expected):
        problems.append("agent.toml tools must exactly match the App reads and proposals")
    return problems


def _proposal_methodology_defects(proposal: dict[str, Any], agent: dict[str, Any],
                                  facts: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return the declared dependencies and every availability problem they carry."""
    dependencies = proposal.get("methodologies")
    problems: list[str] = []
    if not isinstance(dependencies, list):
        problems.append("methodologies must be a list (empty when the agent needs none)")
        dependencies = []
    elif any(not isinstance(item, str) for item in dependencies):
        problems.append("methodologies must contain methodology ids")
        dependencies = [item for item in dependencies if isinstance(item, str)]

    methods = _methodology_map(facts)
    for methodology in dependencies:
        method = methods.get(methodology)
        if method is None:
            problems.append(f"methodology {methodology} is not in list_methodologies")
        elif method.get("runnable") is not True:
            suffix = f" ({method.get('issue')})" if method.get("issue") else ""
            problems.append(f"methodology {methodology} is not runnable{suffix}")
    if "train" in (agent.get("skills") or []) and not dependencies:
        problems.append("an agent that trains or runs models must record its methodology")
    return dependencies, problems


def _pipeline_defects(proposal: dict[str, Any], facts: dict[str, Any],
                      dependencies: list[str]) -> list[str]:
    """Check every Pipeline grant and its methodology dependency."""
    problems: list[str] = []
    approved = {(item["project"], item["graph"]): item
                for item in facts.get("pipelines", [])}
    for grant in proposal.get("pipelines") or []:
        key = (grant.get("project"), grant.get("graph"))
        pipeline = approved.get(key)
        if pipeline is None:
            problems.append(f"Pipeline {grant.get('graph')} in {grant.get('project')} is not an "
                            "approved runnable Pipeline of this workspace")
            continue
        methodology = pipeline.get("methodology")
        if methodology and methodology not in dependencies:
            problems.append(f"Pipeline {grant.get('graph')} depends on {methodology}; record it "
                            "in methodologies")
    return problems


def defects(answer: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    """Everything wrong with an answer. Empty means it may be shown to the person."""
    if answer.get("kind") == "question":
        return [] if (answer.get("question") or "").strip() else ["an empty question"]
    if answer.get("kind") == "decline":
        return _decline_defects(answer, facts)
    if answer.get("kind") != "proposal":
        return ["the answer is not a question, decline or proposal"]
    proposal = answer.get("proposal") or {}
    agent = proposal.get("agent") or {}
    problems: list[str] = []
    if proposal.get("type") not in {"native", "python"}:
        problems.append("type must be native or python")
    if not (agent.get("name") or "").strip():
        problems.append("the agent needs a name")
    unknown = set(agent.get("skills") or []) - SKILLS
    if unknown:
        problems.append(f"skills that do not exist: {sorted(unknown)}")
    if (agent.get("work_area") or {}).get("kind", "workspace") not in WORK_AREAS:
        problems.append("work_area.kind must be workspace, project or dataset")
    dependencies, methodology_problems = _proposal_methodology_defects(proposal, agent, facts)
    problems.extend(methodology_problems)
    problems.extend(_app_proposal_defects(proposal, facts))
    problems.extend(_solution_proposal_defects(proposal, facts))
    problems.extend(_pipeline_defects(proposal, facts, dependencies))
    files = proposal.get("files") or []
    if proposal.get("type") == "native" and files:
        problems.append("a native agent carries no code")
    if proposal.get("type") == "native" and (agent.get("trigger") or "").strip():
        problems.append("a trigger runs the agent unattended, which only a python agent does; make "
                        "it python, or leave the trigger empty for a conversation-only native agent")
    total = 0
    for item in files:
        path, contents = item.get("path", ""), item.get("contents", "")
        total += len(contents)
        if path.startswith("/") or ".." in path:
            problems.append(f"'{path}' is outside the definition")
        if SECRET.search(contents):
            problems.append(f"'{path}' carries something that looks like a secret")
        if path.endswith(".py"):
            try:
                compile(contents, path, "exec")
            except SyntaxError as error:
                problems.append(f"'{path}' does not compile: {error.msg} (line {error.lineno})")
            for module in re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", contents, re.M):
                if module not in RUNTIME_PACKAGES and module not in STDLIB and module != "agent":
                    problems.append(f"'{path}' imports {module}, which the runtime does not ship")
        if path == "agent.toml":
            try:
                wanted = set(tomllib.loads(contents).get("dependencies") or [])
            except tomllib.TOMLDecodeError as error:
                problems.append(f"agent.toml does not parse: {error}")
                wanted = set()
            if wanted - RUNTIME_PACKAGES:
                problems.append(f"dependencies the runtime does not ship: "
                                f"{sorted(wanted - RUNTIME_PACKAGES)}")
    if proposal.get("type") == "python":
        if proposal.get("storage") not in {"zetta", "lake"}:
            problems.append("a python agent is stored in zetta or lake")
        if proposal.get("storage") == "zetta" and total > INLINE_LIMIT:
            problems.append("the code is too large to store on the agent; store it in lake")
    if SECRET.search(json.dumps(agent)) or SECRET.search(proposal.get("secret_mount") or ""):
        problems.append("the proposal carries something that looks like a secret")
    return problems


def parse(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        try:
            value = json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


def words(answer: dict[str, Any], problems: list[str]) -> str:
    """What a person reads: the question, or the proposal in one sentence (agent-creator#1)."""
    if answer.get("kind") == "question":
        return (answer.get("question") or "").strip()
    if answer.get("kind") == "decline":
        if "solution" in answer:
            solution = answer.get("solution") or "the solution registry"
            reason = str(answer.get("reason") or "is not runnable in this workspace").rstrip(".")
            issue = answer.get("issue")
            text = f"I cannot propose this agent because {solution} {reason}."
            if issue and str(issue) not in reason:
                text += f" The engine tracks this as {issue}."
            if problems:
                text += " It still has problems: " + "; ".join(problems) + "."
            return text
        methodology = answer.get("methodology") or "the needed methodology"
        reason = str(answer.get("reason") or "is not runnable in this workspace").rstrip(".")
        issue = answer.get("issue")
        text = f"I cannot propose this agent because it needs {methodology}: {reason}."
        if issue and str(issue) not in reason:
            text += f" The engine tracks this as {issue}."
        if problems:
            text += " It still has problems: " + "; ".join(problems) + "."
        return text
    agent = (answer.get("proposal") or {}).get("agent") or {}
    if answer.get("kind") == "proposal":
        purpose = (agent.get("purpose") or "").strip()
        text = f"I propose an agent named {agent.get('name') or 'without a name'}"
        text += f": {purpose.rstrip('.')}." if purpose else "."
        text += " Review it, and it is created only when you approve it."
        return text + (" It still has problems: " + "; ".join(problems) + "." if problems else "")
    return "I could not design an agent from that. Say what it should do and on which data."


def run(context) -> dict[str, Any]:
    facts = workspace_facts(context)
    system = (context.agent.instructions
              + "\n\n## This workspace\n\nDatasets: " + json.dumps(facts["datasets"])
              + "\n\nSolution source: " + facts["solution_source"]
              + "\n\nSolutions: " + json.dumps(facts["solutions"])
              + "\n\nSolution read error: " + json.dumps(facts["solution_error"])
              + "\n\nApp and build source: " + facts["app_source"]
              + "\n\nApp read capabilities: " + json.dumps(facts["app_read_capabilities"])
              + "\n\nApp actions that may only be proposed: "
              + json.dumps(facts["app_action_capabilities"])
              + "\n\nApps: " + json.dumps(facts["apps"])
              + "\n\nApp events: " + json.dumps(facts["app_events"])
              + "\n\nBuilds: " + json.dumps(facts["builds"])
              + "\n\nBuild events: " + json.dumps(facts["build_events"])
              + "\n\nApp and build read error: " + json.dumps(facts["app_error"])
              + "\n\nMethodology source: " + facts["methodology_source"]
              + "\n\nMethodologies: " + json.dumps(facts["methodologies"])
              + "\n\nMethodology read error: " + json.dumps(facts["methodology_error"])
              + "\n\nApproved runnable Pipelines you may grant: "
              + json.dumps(facts["pipelines"])
              + "\n\nApproved Pipelines that are not runnable: "
              + json.dumps(facts["unrunnable_pipelines"]))
    messages = [{"role": "system", "content": system}]
    for earlier in context.input.get("history") or []:
        if earlier.get("role") in {"user", "assistant"}:
            messages.append({"role": earlier["role"], "content": earlier.get("content", "")})
    messages.append({"role": "user", "content": context.input.get("message", "")})
    answer: dict[str, Any] = {}
    problems: list[str] = []
    for attempt in range(2):
        reply = context.client.chat.completions.create(
            model=context.model, messages=messages,
            response_format={"type": "json_object"}).choices[0].message.content
        answer = parse(reply)
        problems = defects(answer, facts)
        if not problems:
            break
        if attempt == 0:
            messages += [{"role": "assistant", "content": reply or ""},
                         {"role": "user", "content": "Fix these and answer again with the whole "
                                                     "JSON object:\n" + "\n".join(
                                                         f"- {p}" for p in problems)}]
    # Words for the person, the structured answer for lake and API callers (agent-creator#1).
    return {"reply": words(answer, problems),
            "result": {**answer, "defects": problems, "facts": facts}}


STDLIB = {"json", "re", "os", "sys", "time", "datetime", "math", "statistics", "collections",
          "itertools", "functools", "typing", "dataclasses", "pathlib", "csv", "io", "uuid",
          "decimal", "random", "string", "textwrap", "logging", "enum", "abc", "hashlib", "base64",
          "urllib", "http", "__future__", "zoneinfo", "calendar", "heapq", "bisect", "copy",
          "pprint", "tomllib", "operator", "contextlib", "fractions"}
