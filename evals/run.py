"""AgentCreator's evals: generated asks, graded by rules, run live against a real workspace.

The asks are generated from Studio's skills and work areas (never hand-written); each is graded by
`agent.main.defects` plus: the answer must be a proposal (the asks are complete enough to propose
from), the type must match what the ask needs, and granted skills must include the one the ask
names. No judge.

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


def generated():
    for (skill, ask), (area, where), (code, extra) in itertools.product(
            SKILL_ASKS.items(), AREAS.items(), CODE_ASKS.items()):
        if code and skill in {"call-api", "generate-data"}:
            continue
        yield {"id": f"{skill}-{area}-{'code' if code else 'plain'}", "skill": skill,
               "needs_code": code,
               "message": f"I want an agent that {ask}, working {where}.{extra} Propose it now; "
                          "do not ask me anything."}


class LiveWorkspace:
    def __init__(self) -> None:
        base = os.environ["LAKE_URL"].rstrip("/") + f"/workspaces/{os.environ['CUSTOMER_ID']}/zetta"
        self.client = httpx.Client(base_url=base, timeout=60, headers={
            "Authorization": f"Bearer {os.environ['LAKE_TOKEN']}"})

    def call_tool(self, name, arguments):
        response = self.client.get(f"/v1/{name}", params=arguments)
        body = response.json() if response.content else {}
        return SimpleNamespace(ok=bool(body.get("ok")), value=body.get("value"))


def main_eval() -> int:
    workspace = LiveWorkspace()
    instructions = (Path(__file__).resolve().parent.parent / "definition" /
                    "instructions.md").read_text()
    client, model = OpenAI(), os.environ.get("AGENT_MODEL", "gpt-5.5")
    rows = []
    for case in generated():
        context = SimpleNamespace(agent=SimpleNamespace(instructions=instructions),
                                  input={"message": case["message"], "history": []},
                                  client=client, model=model, call_tool=workspace.call_tool)
        answer = main.run(context)["result"]
        reasons = list(answer.get("defects") or [])
        proposal = answer.get("proposal") or {}
        if answer.get("kind") != "proposal":
            reasons.append("asked instead of proposing")
        elif case["skill"] not in ((proposal.get("agent") or {}).get("skills") or []):
            reasons.append(f"did not grant {case['skill']}")
        if case["needs_code"] and proposal.get("type") == "native":
            reasons.append("code was asked for; a native agent carries none")
        rows.append({"case": case, "passed": not reasons, "reasons": reasons, "answer": answer})
    passed = sum(row["passed"] for row in rows)
    out = Path(__file__).resolve().parent.parent / "reports"
    out.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    (out / f"{stamp}-evals.json").write_text(json.dumps(rows, indent=1, default=str))
    lines = [f"# AgentCreator evals, {stamp}", "",
             f"**{passed} / {len(rows)} passed** with `{model}` against `{os.environ['LAKE_URL']}`.",
             "Asks generated from Studio's skills and work areas; graded by rules, no judge.", "",
             "| Case | Result |", "|---|---|"]
    lines += [f"| `{row['case']['id']}` | " + ("pass" if row["passed"] else
                                                 "FAIL: " + "; ".join(row["reasons"])) + " |"
              for row in rows]
    (out / f"{stamp}-evals.md").write_text("\n".join(lines) + "\n")
    print(f"{passed}/{len(rows)} passed")
    return 0 if passed == len(rows) else 2


if __name__ == "__main__":
    sys.exit(main_eval())
