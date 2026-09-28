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
S1 = {
    "id": "S-1",
    "name": "Churn & Retention",
    "promise": "Route the right retention work.",
    "use_case": "Prevent avoidable churn.",
    "status": "catalogue",
    "runnable": True,
    "issue": "https://github.com/oramasearch/zetta/issues/1102",
    "autonomy_defaults": [
        {"action_class": "score and create tasks", "autonomy": "A2"},
        {"action_class": "concessions", "autonomy": "A1"},
        {"action_class": "threshold tuning", "autonomy": "A3"},
    ],
    "promotion_condition": "",
}
S5 = {
    "id": "S-5",
    "name": "Demand Forecasting",
    "promise": "Surface the exceptions planners need.",
    "use_case": "Forecast demand.",
    "status": "catalogue",
    "runnable": False,
    "issue": "https://github.com/oramasearch/zetta/issues/1106",
    "autonomy_defaults": [
        {"action_class": "planning decisions", "autonomy": "A1"},
    ],
    "promotion_condition": "",
}
B1 = {
    "id": "B-1",
    "name": "Dynamic Pricing & Discount Governance",
    "promise": "Govern price changes.",
    "use_case": "Bound price changes.",
    "status": "sketch",
    "runnable": False,
    "issue": "https://github.com/oramasearch/zetta/issues/1102",
    "autonomy_defaults": [],
    "promotion_condition": "Promote after controlled price experiments are available.",
}
FACTS = {
    "solutions": [S1, S5, B1],
    "solution_source": "list_solutions/get_solution",
    "solution_error": "",
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

    def __init__(self, methodologies=None, methodology_error="", solutions=None,
                 solution_error="", solution_details=None, solution_detail_error=""):
        self.methodologies = methodologies if methodologies is not None else [M1, M4, M7]
        self.methodology_error = methodology_error
        self.solutions = solutions if solutions is not None else [S1, S5, B1]
        self.solution_error = solution_error
        self.solution_details = solution_details or {}
        self.solution_detail_error = solution_detail_error
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        ok = lambda value: SimpleNamespace(ok=True, value=value)  # noqa: E731
        if name == "list_solutions" and self.solution_error:
            return SimpleNamespace(ok=False, value=None, error=self.solution_error)
        if name == "list_solutions":
            return ok({"solutions": self.solutions})
        if name == "get_solution":
            if self.solution_detail_error:
                return SimpleNamespace(ok=False, value=None, error=self.solution_detail_error)
            identifier = arguments["solution"]
            found = self.solution_details.get(identifier)
            if found is None:
                found = next((item for item in self.solutions if item.get("id") == identifier),
                             None)
            if found is not None:
                return ok({"solution": found})
            return SimpleNamespace(ok=False, value=None, error="not_found")
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


def solution_binding(**changes):
    value = {
        "id": "S-1",
        "capabilities": main.SOLUTION_CAPABILITIES,
        "autonomy": S1["autonomy_defaults"],
        "approval_gates": ["concessions"],
    }
    value.update(changes)
    return value


def test_only_approved_pipelines_are_facts():
    workspace = Workspace()
    assert main.workspace_facts(workspace) == FACTS
    assert workspace.calls[:4] == [
        ("list_solutions", {}),
        ("get_solution", {"solution": "S-1"}),
        ("get_solution", {"solution": "S-5"}),
        ("get_solution", {"solution": "B-1"}),
    ]
    assert workspace.calls[4] == ("list_methodologies", {})


def test_get_solution_is_authoritative_over_the_list_entry():
    summary = {**S1, "runnable": False}

    facts = main.workspace_facts(Workspace(
        solutions=[summary],
        solution_details={"S-1": S1},
    ))

    assert facts["solutions"] == [S1]
    assert facts["solution_source"] == "list_solutions/get_solution"


def test_an_unknown_get_solution_capability_is_not_deployed_yet():
    facts = main.workspace_facts(Workspace(
        solutions=[S1],
        solution_detail_error="unknown_capability: get_solution",
    ))

    assert facts["solutions"] == []
    assert "get_solution is not deployed yet" in facts["solution_error"]


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


def test_a_good_solution_proposal_has_no_defects():
    assert main.defects(proposal(solution=solution_binding()), FACTS) == []


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
        "not in this turn's solution registry": proposal(
            solution=solution_binding(id="S-99"),
        ),
        "solution S-5 is not runnable": proposal(
            solution=solution_binding(
                id="S-5",
                autonomy=S5["autonomy_defaults"],
                approval_gates=["planning decisions"],
            ),
        ),
        "solution B-1 is a sketch": proposal(
            solution=solution_binding(
                id="B-1",
                autonomy=[],
                approval_gates=[],
            ),
        ),
        "must be decide": proposal(
            solution=solution_binding(capabilities=["decide", "approve_decision"]),
        ),
        "exactly match": proposal(
            solution=solution_binding(autonomy=[
                {"action_class": "concessions", "autonomy": "A2"},
            ]),
        ),
        "must stay approval-gated": proposal(
            solution=solution_binding(approval_gates=[]),
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
    assert workspace.calls[0] == ("list_solutions", {})
    assert ("list_methodologies", {}) in workspace.calls


def test_a_runnable_solution_is_bound_with_live_autonomy_and_capabilities():
    bound = proposal(solution=solution_binding())
    workspace = Workspace(solutions=[S1])

    answered = main.run(context(
        json.dumps(bound),
        workspace=workspace,
        message="Each Monday, work the retention queue and report what changed.",
    ))

    binding = answered["result"]["proposal"]["solution"]
    assert binding["id"] == "S-1"
    assert binding["capabilities"] == main.SOLUTION_CAPABILITIES
    assert binding["autonomy"] == S1["autonomy_defaults"]
    assert binding["approval_gates"] == ["concessions"]
    assert "approve_decision" not in binding["capabilities"]
    assert answered["result"]["defects"] == []
    assert workspace.calls[:2] == [
        ("list_solutions", {}),
        ("get_solution", {"solution": "S-1"}),
    ]


def test_an_unrunnable_solution_is_declined_with_its_issue():
    declined = {
        "kind": "decline",
        "solution": "S-5",
        "issue": S5["issue"],
        "reason": "S-5 is not runnable in this workspace",
    }

    answered = main.run(context(
        json.dumps(declined),
        workspace=Workspace(solutions=[S5]),
        message="Build an agent that operates demand forecasting.",
    ))

    assert answered["result"]["kind"] == "decline"
    assert answered["result"]["defects"] == []
    assert "S-5" in answered["reply"]
    assert S5["issue"] in answered["reply"]


def test_a_solution_sketch_decline_repeats_its_promotion_condition():
    declined = {
        "kind": "decline",
        "solution": "B-1",
        "issue": B1["issue"],
        "reason": "B-1 is a sketch. " + B1["promotion_condition"],
    }

    answered = main.run(context(
        json.dumps(declined),
        workspace=Workspace(solutions=[B1]),
        message="Build an agent that sets prices.",
    ))

    assert answered["result"]["defects"] == []
    assert B1["promotion_condition"] in answered["reply"]


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


def test_an_engine_without_the_solution_registry_has_no_solutions():
    workspace = Workspace(solution_error="unknown_capability: list_solutions")
    declined = {
        "kind": "decline",
        "solution": "solution registry",
        "issue": "",
        "reason": "list_solutions is not deployed yet in this workspace",
    }

    answered = main.run(context(
        json.dumps(declined),
        workspace=workspace,
        message="Each Monday, work the retention queue.",
    ))

    facts = answered["result"]["facts"]
    assert facts["solutions"] == []
    assert facts["solution_source"] == "not_deployed"
    assert answered["result"]["defects"] == []
    assert "not deployed yet" in answered["reply"]
    assert not any(name == "get_solution" for name, _ in workspace.calls)

    invented = {**declined, "solution": "S-1", "issue": S1["issue"]}
    assert main.defects(invented, facts)


def test_live_eval_reads_through_lakes_workspace_query(monkeypatch):
    sent = []

    def answer(request):
        sent.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "value": {"methodologies": [M1]}})

    monkeypatch.setenv("LAKE_URL", "https://lake.example")
    monkeypatch.setenv("LAKE_TOKEN", "test-token")
    monkeypatch.setenv("CUSTOMER_ID", "customer-1")
    workspace = eval_run.LiveWorkspace(httpx.MockTransport(answer))

    listed = workspace.call_tool("list_solutions", {})
    got = workspace.call_tool("get_solution", {"solution": "S-1"})

    assert listed.ok
    assert got.ok
    assert sent == [
        (
            "POST",
            "/v1/workspace_query",
            {"customer_id": "customer-1", "capability": "list_solutions", "input": {}},
        ),
        (
            "POST",
            "/v1/workspace_query",
            {
                "customer_id": "customer-1",
                "capability": "get_solution",
                "input": {"solution": "S-1"},
            },
        ),
    ]
    workspace.client.close()


def test_generated_evals_cover_runnable_unavailable_and_missing_solutions():
    current = list(eval_run.generated([M1, M7], [S1, S5]))
    older = list(eval_run.generated([M1], [], "not_deployed"))

    current_ids = {case["id"] for case in current}
    assert "solution-S-1-runnable" in current_ids
    assert "solution-S-5-unsupported" in current_ids
    assert any(case["id"] == "solution-registry-not-deployed" for case in older)


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
