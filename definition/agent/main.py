"""AgentCreator's turn: read the workspace, then ask, decline or propose and check the answer.

It proposes and never creates: lake's Agent Factory shows the proposal and creates the agent only
on the person's approval (lake#233). Everything it may put in a proposal is checked here, by rules,
before the person sees it: skills from Studio's set, Pipelines that exist and are approved, code
that compiles and imports only what the runtime ships, no secrets, and storage that fits the code.
"""

from __future__ import annotations

import json
import re
import tomllib
from typing import Any

SKILLS = {"search", "generate-data", "train", "summarize", "call-api"}
WORK_AREAS = {"workspace", "project", "dataset"}
RUNTIME_PACKAGES = {"openai", "httpx", "pydantic", "pandas", "numpy"}
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


def workspace_facts(context) -> dict[str, Any]:
    """What exists: the datasets, and every approved Pipeline, read through the person's key."""
    # This is deliberately first. Methodology availability changes as the engine gains runners.
    facts: dict[str, Any] = {
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


def _decline_defects(answer: dict[str, Any], facts: dict[str, Any]) -> list[str]:
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
