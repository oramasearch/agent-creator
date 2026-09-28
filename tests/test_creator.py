"""AgentCreator's turn with a scripted model and a workspace answered from tables."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from agent import main
from evals import run as eval_run

M1 = {
    "id": "M-1",
    "name": "Churn / GBDT classification",
    "runnable": True,
    "partial": False,
}
M4 = {
    "id": "M-4",
    "name": "Demand forecasting",
    "runnable": True,
    "partial": False,
}
M7 = {
    "id": "M-7",
    "name": "Optimization",
    "runnable": False,
    "partial": False,
    "issue": "zetta#1047",
}
FACTS = {
    "datasets": ["accounts"],
    "pipelines": [
        {
            "project": "churn",
            "graph": "weekly",
            "methodology": "M-1",
            "runnable": True,
        }
    ],
    "unrunnable_pipelines": [],
    "methodologies": [M1, M4, M7],
    "methodology_source": "list_methodologies",
    "methodology_error": "",
}


class Workspace:
    """The reads AgentCreator's skills grant, answered the way the workspace does."""

    def __init__(self, methodologies=None, methodology_error=""):
        self.methodologies = methodologies if methodologies is not None else [M1, M4, M7]
        self.methodology_error = methodology_error
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        ok = lambda value: SimpleNamespace(ok=True, value=value)  # noqa: E731
        if name == "list_methodologies" and self.methodology_error:
            return SimpleNamespace(ok=False, value=None, error=self.methodology_error)
        if name == "list_methodologies":
            return ok({"methodologies": self.methodologies})
        if name == "list_datasets":
            return ok({"datasets": [{"name": "accounts"}]})
        if name == "list_projects":
            return ok({"projects": ["churn", "draft"]})
        if name == "get_project" and arguments["name"] == "churn":
            return ok({"graphs": [{"name": "weekly", "approval": "approved",
                                    "methodology": "M-1", "runnable": True}]})
        if name == "get_project":
            return ok({"graphs": [{"name": "idea", "approval": "proposed"}]})
        return SimpleNamespace(ok=False, value=None)


def proposal(**changes):
    value = {"type": "python", "why_type": "needs code", "storage": "zetta", "why_storage": "small",
             "methodologies": ["M-1"],
             "agent": {"name": "Renewal watcher", "purpose": "Flag renewals",
                       "work_area": {"kind": "project", "detail": "churn"},
                       "manifesto": "Company data only.", "goal": "A month ahead.",
                       "skills": ["search", "summarize"], "trigger": "every Monday at 09:00"},
             "pipelines": [{"project": "churn", "graph": "weekly"}],
             "files": [{"path": "agent/tools.py",
                        "contents": "import json\n\ndef note(x):\n    return json.dumps(x)\n\n"
                                    "TOOLS = [note]\n"}],
             "secret_mount": ""}
    value.update(changes)
    return {"kind": "proposal", "proposal": value}


def test_only_approved_pipelines_are_facts():
    workspace = Workspace()
    assert main.workspace_facts(workspace) == FACTS
    assert workspace.calls[0] == ("list_methodologies", {})


def test_a_pipeline_is_not_grantable_when_its_methodology_is_not_runnable():
    blocked_m1 = {**M1, "runnable": False, "issue": "zetta#1041"}

    facts = main.workspace_facts(Workspace(methodologies=[blocked_m1, M4, M7]))

    assert facts["pipelines"] == []
    assert facts["unrunnable_pipelines"] == [{
        "project": "churn",
        "graph": "weekly",
        "methodology": "M-1",
        "runnable": True,
        "issue": "zetta#1041",
    }]


def test_a_good_proposal_has_no_defects():
    assert main.defects(proposal(), FACTS) == []


def test_every_rule_catches_its_defect():
    cases = {
        "skills that do not exist": proposal(agent={**proposal()["proposal"]["agent"],
                                                    "skills": ["launch-missiles"]}),
        "not an approved runnable Pipeline": proposal(
            pipelines=[{"project": "draft", "graph": "idea"}]),
        "does not compile": proposal(files=[{"path": "agent/x.py", "contents": "def (:"}]),
        "does not ship": proposal(files=[{"path": "agent/x.py", "contents": "import torch\n"}]),
        "looks like a secret": proposal(files=[{"path": "agent/x.py",
                                                "contents": "KEY = 'sk-abcdefghijklmnopqrstu'\n"}]),
        "outside the definition": proposal(files=[{"path": "../x.py", "contents": ""}]),
        "carries no code": proposal(type="native", storage=""),
        "stored in zetta or lake": proposal(storage="s3"),
        "too large": proposal(files=[{"path": "data.txt", "contents": "x" * (901 * 1024)}]),
        "only a python agent": proposal(type="native", storage="", files=[]),
        "not runnable": proposal(methodologies=["M-7"]),
        "depends on M-1": proposal(methodologies=[]),
        "must record its methodology": proposal(
            methodologies=[],
            pipelines=[],
            agent={**proposal()["proposal"]["agent"], "skills": ["train"]},
        ),
    }
    for expected, answer in cases.items():
        assert any(expected in problem for problem in main.defects(answer, FACTS)), expected


class Scripted:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_):
        content = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def context(*replies, history=None, workspace=None, message="an agent that flags renewals"):
    workspace = workspace or Workspace()
    return SimpleNamespace(agent=SimpleNamespace(instructions="You are AgentCreator."),
                           input={"message": message, "history": history or [],
                                  "customer_id": "customer-1"},
                           client=Scripted(*replies), model="gpt-5.5",
                           call_tool=workspace.call_tool)


def test_a_runnable_methodology_is_recorded_on_the_proposal():
    forecasting = proposal(
        methodologies=["M-4"],
        pipelines=[],
        agent={
            **proposal()["proposal"]["agent"],
            "purpose": "Forecast demand each Monday",
            "skills": ["train", "summarize"],
        },
    )
    workspace = Workspace()

    answered = main.run(context(
        json.dumps(forecasting),
        workspace=workspace,
        message="Each Monday, forecast demand.",
    ))

    assert answered["result"]["proposal"]["methodologies"] == ["M-4"]
    assert answered["result"]["defects"] == []
    assert workspace.calls[0] == ("list_methodologies", {})


def test_an_unrunnable_methodology_is_declined_with_its_issue():
    declined = {
        "kind": "decline",
        "methodology": "M-7",
        "issue": "zetta#1047",
        "reason": "optimization is not runnable in this workspace",
    }

    answered = main.run(context(
        json.dumps(declined),
        message="Build an agent that optimizes delivery assignments.",
    ))

    assert answered["result"]["kind"] == "decline"
    assert answered["result"]["defects"] == []
    assert "M-7" in answered["reply"]
    assert "zetta#1047" in answered["reply"]


def test_an_old_engine_fallback_says_only_m1_runs():
    workspace = Workspace(methodology_error="unknown_capability: list_methodologies")
    declined = {
        "kind": "decline",
        "methodology": "M-4",
        "reason": "this older workspace engine can run only M-1",
    }

    answered = main.run(context(
        json.dumps(declined),
        workspace=workspace,
        message="Each Monday, forecast demand.",
    ))

    assert answered["result"]["facts"]["methodology_source"] == "old-engine fallback"
    assert answered["result"]["facts"]["methodologies"] == [main.LEGACY_METHODOLOGY]
    assert answered["result"]["defects"] == []
    assert "only M-1" in answered["reply"]


def test_an_old_engine_fallback_still_allows_m1():
    workspace = Workspace(methodology_error="unknown_capability: list_methodologies")

    answered = main.run(context(json.dumps(proposal()), workspace=workspace))

    assert answered["result"]["proposal"]["methodologies"] == ["M-1"]
    assert answered["result"]["defects"] == []


def test_live_eval_reads_through_lakes_workspace_query(monkeypatch):
    sent = []

    def answer(request):
        sent.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "value": {"methodologies": [M1]}})

    monkeypatch.setenv("LAKE_URL", "https://lake.example")
    monkeypatch.setenv("LAKE_TOKEN", "test-token")
    monkeypatch.setenv("CUSTOMER_ID", "customer-1")
    workspace = eval_run.LiveWorkspace(httpx.MockTransport(answer))

    reply = workspace.call_tool("list_methodologies", {})

    assert reply.ok
    assert reply.value == {"methodologies": [M1]}
    assert sent == [(
        "POST",
        "/v1/workspace_query",
        {"customer_id": "customer-1", "capability": "list_methodologies", "input": {}},
    )]
    workspace.client.close()


def test_a_defective_proposal_gets_one_repair_round():
    bad = proposal(pipelines=[{"project": "draft", "graph": "idea"}])
    answered = main.run(context(json.dumps(bad), json.dumps(proposal())))
    answer = answered["result"]
    assert answer["kind"] == "proposal" and answer["defects"] == []
    assert answered["reply"].startswith("I propose an agent named Renewal watcher: Flag renewals.")


def test_a_proposal_that_fails_twice_is_returned_with_its_defects():
    bad = json.dumps(proposal(storage="s3"))
    answered = main.run(context(bad, bad))
    answer = answered["result"]
    assert "still has problems" in answered["reply"]
    assert answer["defects"], "the person is never shown a proposal as clean when it is not"


def test_a_question_is_an_answer():
    answered = main.run(context(json.dumps({"kind": "question",
                                            "question": "Which accounts count?"})))
    answer = answered["result"]
    assert answer["kind"] == "question" and not answer["defects"]
    assert answered["reply"] == "Which accounts count?", "a person reads words, not JSON"
