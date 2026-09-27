"""AgentCreator's turn (zetta#1017): read the workspace, ask or propose, check the proposal.

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


def workspace_facts(context) -> dict[str, Any]:
    """What exists: the datasets, and every approved Pipeline, read through the person's key."""
    facts: dict[str, Any] = {"datasets": [], "pipelines": []}
    datasets = context.call_tool("list_datasets", {})
    if datasets.ok and isinstance(datasets.value, dict):
        for item in datasets.value.get("datasets", []):
            facts["datasets"].append(item.get("name") if isinstance(item, dict) else str(item))
    projects = context.call_tool("list_projects", {})
    names = projects.value.get("projects", []) if projects.ok and isinstance(projects.value,
                                                                              dict) else []
    for name in names:
        name = name if isinstance(name, str) else (name or {}).get("name", "")
        got = context.call_tool("get_project", {"name": name})
        if not got.ok or not isinstance(got.value, dict):
            continue
        for graph in got.value.get("graphs", []):
            if graph.get("approval") == "approved":
                facts["pipelines"].append({"project": name, "graph": graph.get("name", "")})
    return facts


def defects(answer: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    """Everything wrong with an answer. Empty means it may be shown to the person."""
    if answer.get("kind") == "question":
        return [] if (answer.get("question") or "").strip() else ["an empty question"]
    if answer.get("kind") != "proposal":
        return ["the answer is neither a question nor a proposal"]
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
    approved = {(p["project"], p["graph"]) for p in facts.get("pipelines", [])}
    for grant in proposal.get("pipelines") or []:
        if (grant.get("project"), grant.get("graph")) not in approved:
            problems.append(f"Pipeline {grant.get('graph')} in {grant.get('project')} is not an "
                            "approved Pipeline of this workspace")
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
              + "\n\nApproved Pipelines you may grant: " + json.dumps(facts["pipelines"]))
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
