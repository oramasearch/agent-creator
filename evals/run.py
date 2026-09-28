"""AgentCreator's evals: generated asks, graded by rules, run live against a real workspace.

The asks are generated from Studio's skills and work areas plus live Apps, builds, methodologies
and solutions. Each is graded by `agent.main.defects` and case-specific facts. No judge.

    LAKE_URL=... LAKE_TOKEN=<a person's token> CUSTOMER_ID=... uv run python evals/run.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "definition"))
from agent import main  # noqa: E402

SKILL_ASKS = {
    "search": "finds the accounts in our data that match what I describe",
    "summarize": "summarizes what our latest runs found, in plain words, every Monday",
    "train": "retrains our approved churn Pipeline when a new dataset lands and tells me the score",
    "call-api": "scores a single account through our published model when I ask about it",
    "generate-data": "generates a realistic test dataset of accounts for demos",
}
AREAS = {"workspace": "anywhere in this workspace", "project": "only in the churn project"}
CODE_ASKS = {False: "", True: " It needs a small helper that formats results as a table."}


def generated(methodologies=None, solutions=None, solution_source="", apps=None, app_source=""):
    for (skill, ask), (area, where), (code, extra) in itertools.product(
            SKILL_ASKS.items(), AREAS.items(), CODE_ASKS.items()):
        if code and skill in {"call-api", "generate-data"}:
            continue
        yield {"id": f"{skill}-{area}-{'code' if code else 'plain'}", "skill": skill,
               "needs_code": code,
               "message": f"I want an agent that {ask}, working {where}.{extra} Propose it now; "
                          "do not ask me anything."}
    methods = [item for item in methodologies or [] if isinstance(item, dict)]
    runnable = next((item for item in methods if item.get("runnable") is True), None)
    unsupported = next((item for item in methods if item.get("runnable") is not True), None)
    if runnable:
        identifier = runnable.get("id")
        yield {
            "id": f"methodology-{identifier}-runnable",
            "expected_kind": "proposal",
            "expected_methodology": identifier,
            "message": f"Propose an agent whose job uses {runnable.get('name')} "
                       f"({identifier}). Do not ask me anything.",
        }
    if unsupported:
        identifier = unsupported.get("id")
        yield {
            "id": f"methodology-{identifier}-unsupported",
            "expected_kind": "decline",
            "expected_methodology": identifier,
            "expected_issue": unsupported.get("issue"),
            "message": f"Propose an agent whose job uses {unsupported.get('name')} "
                       f"({identifier}). Do not substitute another methodology and do not ask me "
                       "anything.",
        }
    entries = [item for item in solutions or [] if isinstance(item, dict)]
    runnable_solution = next((item for item in entries
                              if item.get("runnable") is True
                              and item.get("status") != "sketch"), None)
    unsupported_solution = next((item for item in entries
                                 if item.get("runnable") is not True
                                 or item.get("status") == "sketch"), None)
    if runnable_solution:
        identifier = runnable_solution.get("id")
        yield {
            "id": f"solution-{identifier}-runnable",
            "expected_kind": "proposal",
            "expected_solution": identifier,
            "message": f"Each Monday, operate the {runnable_solution.get('name')} solution "
                       f"({identifier}) and report what changed. Propose it now; do not ask me "
                       "anything.",
        }
    if unsupported_solution:
        identifier = unsupported_solution.get("id")
        yield {
            "id": f"solution-{identifier}-unsupported",
            "expected_kind": "decline",
            "expected_solution": identifier,
            "expected_issue": unsupported_solution.get("issue"),
            "message": f"Each Monday, operate the {unsupported_solution.get('name')} solution "
                       f"({identifier}) and report what changed. Do not substitute another "
                       "solution and do not ask me anything.",
        }
    if solution_source == "not_deployed":
        yield {
            "id": "solution-registry-not-deployed",
            "expected_kind": "decline",
            "expected_registry_missing": True,
            "message": "Each Monday, operate the matching customer-retention solution and report "
                       "what changed. Do not ask me anything.",
        }
    live_apps = [item for item in apps or [] if isinstance(item, dict)]
    if app_source == main.APP_FACT_SOURCE and live_apps:
        app = live_apps[0]
        app_id = app.get("id") or app.get("app_id")
        yield {
            "id": f"app-{app_id}-watch-and-propose",
            "expected_kind": "proposal",
            "expected_app_id": app_id,
            "expected_app_actions": ["build_app", "restart_app"],
            "message": f"Alert me when App {app.get('name') or app_id} ({app_id}) crash-loops "
                       "or one of its builds fails. Propose a rebuild or restart for me to "
                       "confirm; never execute it yourself. Propose the agent now and do not ask "
                       "me anything.",
        }


class LiveWorkspace:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.customer_id = os.environ["CUSTOMER_ID"]
        self.client = httpx.Client(
            base_url=os.environ["LAKE_URL"].rstrip("/"),
            timeout=60,
            headers={"Authorization": f"Bearer {os.environ['LAKE_TOKEN']}"},
            transport=transport,
        )

    def app_capabilities(self):
        response = self.client.get("/v1/openapi.json")
        document = response.json() if response.content else {}
        names = {
            path.removeprefix("/v1/")
            for path in (document.get("paths") or {})
            if isinstance(path, str)
        }
        return {
            "reads": sorted(names & set(main.APP_READ_CAPABILITIES)),
            "proposals": sorted(names & main.APP_ACTION_CAPABILITIES),
        }

    def call_tool(self, name, arguments):
        if name in main.APP_READ_CAPABILITIES:
            parameters = {"customer_id": self.customer_id, **arguments}
            response = self.client.get(f"/v1/{name}", params=parameters)
            body = response.json() if response.content else {}
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict):
                error = f"{error.get('code', response.status_code)}: {error.get('message', '')}"
            return SimpleNamespace(ok=bool(body.get("ok")), value=body.get("value"),
                                   error=error or "")
        response = self.client.post("/v1/workspace_query", json={
            "customer_id": self.customer_id,
            "capability": name,
            "input": arguments,
        })
        body = response.json() if response.content else {}
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            error = f"{error.get('code', response.status_code)}: {error.get('message', '')}"
        return SimpleNamespace(ok=bool(body.get("ok")), value=body.get("value"),
                               error=error or "")


def main_eval() -> int:
    workspace = LiveWorkspace()
    instructions = (Path(__file__).resolve().parent.parent / "definition" /
                    "instructions.md").read_text()
    client, model = OpenAI(), os.environ.get("AGENT_MODEL", "gpt-5.5")
    app_capabilities = workspace.app_capabilities()
    fact_context = SimpleNamespace(
        input={"customer_id": workspace.customer_id},
        app_capabilities=app_capabilities,
        call_tool=workspace.call_tool,
    )
    solution_snapshot = main.solution_facts(fact_context)
    app_snapshot = main.app_facts(fact_context)
    methodology_snapshot = main.methodology_facts(fact_context)
    rows = []
    for case in generated(
        methodology_snapshot["methodologies"],
        solution_snapshot["solutions"],
        solution_snapshot["solution_source"],
        app_snapshot["apps"],
        app_snapshot["app_source"],
    ):
        context = SimpleNamespace(agent=SimpleNamespace(instructions=instructions),
                                  input={"message": case["message"], "history": [],
                                         "customer_id": workspace.customer_id},
                                  app_capabilities=app_capabilities,
                                  client=client, model=model, call_tool=workspace.call_tool)
        turn = main.run(context)
        answer = turn["result"]
        reasons = list(answer.get("defects") or [])
        proposal = answer.get("proposal") or {}
        expected_kind = case.get("expected_kind", "proposal")
        if answer.get("kind") != expected_kind:
            reasons.append(f"answered {answer.get('kind')} instead of {expected_kind}")
        if case.get("skill") and answer.get("kind") == "proposal":
            skills = (proposal.get("agent") or {}).get("skills") or []
            if case["skill"] not in skills:
                reasons.append(f"did not grant {case['skill']}")
        if case.get("needs_code") and proposal.get("type") == "native":
            reasons.append("code was asked for; a native agent carries none")
        methodology = case.get("expected_methodology")
        if methodology and answer.get("kind") == "proposal":
            if methodology not in (proposal.get("methodologies") or []):
                reasons.append(f"did not record {methodology}")
        if methodology and answer.get("kind") == "decline":
            if answer.get("methodology") != methodology:
                reasons.append(f"declined {answer.get('methodology')} instead of {methodology}")
            issue = case.get("expected_issue")
            if issue and issue not in json.dumps(answer):
                reasons.append(f"did not name {issue}")
        solution = case.get("expected_solution")
        if solution and answer.get("kind") == "proposal":
            binding = proposal.get("solution") or {}
            if binding.get("id") != solution:
                reasons.append(f"did not bind {solution}")
        if solution and answer.get("kind") == "decline":
            if answer.get("solution") != solution:
                reasons.append(f"declined {answer.get('solution')} instead of {solution}")
            issue = case.get("expected_issue")
            if issue and issue not in json.dumps(answer):
                reasons.append(f"did not name {issue}")
        if case.get("expected_registry_missing"):
            if "not deployed yet" not in str(answer.get("reason") or ""):
                reasons.append("did not say the solution registry is not deployed yet")
        app_id = case.get("expected_app_id")
        if app_id and answer.get("kind") == "proposal":
            access = proposal.get("app_capabilities") or {}
            expected_topic = f"app-events.{app_id}"
            if expected_topic not in (access.get("subscriptions") or []):
                reasons.append(f"did not subscribe to {expected_topic}")
            if "build-events.*" not in (access.get("subscriptions") or []):
                reasons.append("did not subscribe to build-events.*")
            if set(access.get("reads") or []) != set(main.APP_READ_CAPABILITIES):
                reasons.append("did not grant the six App and build reads")
            for action in case.get("expected_app_actions") or []:
                if action not in (access.get("proposals") or []):
                    reasons.append(f"did not propose {action}")
            if access.get("application_agent") != main.APP_DELEGATION:
                reasons.append("did not delegate the confirmed change to ApplicationAgent")
        rows.append({"case": case, "passed": not reasons, "reasons": reasons, "answer": answer,
                     "reply": turn["reply"]})
    passed = sum(row["passed"] for row in rows)
    out = Path(__file__).resolve().parent.parent / "reports"
    out.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    (out / f"{stamp}-evals.json").write_text(json.dumps(rows, indent=1, default=str))
    lines = [f"# AgentCreator evals, {stamp}", "",
             f"**{passed} / {len(rows)} passed** with `{model}` against `{os.environ['LAKE_URL']}`.",
             "Asks generated from Studio's skills, work areas, Apps, builds and live registries; "
             "graded by rules, no judge.", "",
             "| Case | Result |", "|---|---|"]
    lines += [f"| `{row['case']['id']}` | " + ("pass" if row["passed"] else
                                                 "FAIL: " + "; ".join(row["reasons"])) + " |"
              for row in rows]
    (out / f"{stamp}-evals.md").write_text("\n".join(lines) + "\n")
    print(f"{passed}/{len(rows)} passed")
    return 0 if passed == len(rows) else 2


if __name__ == "__main__":
    sys.exit(main_eval())
