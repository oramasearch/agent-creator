"""AgentCreator's turn with a scripted model and a workspace answered from tables."""

from __future__ import annotations

import json
from types import SimpleNamespace

from agent import main

FACTS = {"datasets": ["accounts"], "pipelines": [{"project": "churn", "graph": "weekly"}]}


class Workspace:
    """The reads AgentCreator's skills grant, answered the way the workspace does."""

    def call_tool(self, name, arguments):
        ok = lambda value: SimpleNamespace(ok=True, value=value)  # noqa: E731
        if name == "list_datasets":
            return ok({"datasets": [{"name": "accounts"}]})
        if name == "list_projects":
            return ok({"projects": ["churn", "draft"]})
        if name == "get_project" and arguments["name"] == "churn":
            return ok({"graphs": [{"name": "weekly", "approval": "approved"}]})
        if name == "get_project":
            return ok({"graphs": [{"name": "idea", "approval": "proposed"}]})
        return SimpleNamespace(ok=False, value=None)


def proposal(**changes):
    value = {"type": "python", "why_type": "needs code", "storage": "zetta", "why_storage": "small",
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
    assert main.workspace_facts(Workspace()) == FACTS


def test_a_good_proposal_has_no_defects():
    assert main.defects(proposal(), FACTS) == []


def test_every_rule_catches_its_defect():
    cases = {
        "skills that do not exist": proposal(agent={**proposal()["proposal"]["agent"],
                                                    "skills": ["launch-missiles"]}),
        "not an approved Pipeline": proposal(pipelines=[{"project": "draft", "graph": "idea"}]),
        "does not compile": proposal(files=[{"path": "agent/x.py", "contents": "def (:"}]),
        "does not ship": proposal(files=[{"path": "agent/x.py", "contents": "import torch\n"}]),
        "looks like a secret": proposal(files=[{"path": "agent/x.py",
                                                "contents": "KEY = 'sk-abcdefghijklmnopqrstu'\n"}]),
        "outside the definition": proposal(files=[{"path": "../x.py", "contents": ""}]),
        "carries no code": proposal(type="native", storage=""),
        "stored in zetta or lake": proposal(storage="s3"),
        "too large": proposal(files=[{"path": "data.txt", "contents": "x" * (901 * 1024)}]),
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


def context(*replies, history=None):
    workspace = Workspace()
    return SimpleNamespace(agent=SimpleNamespace(instructions="You are AgentCreator."),
                           input={"message": "an agent that flags renewals", "history": history
                                  or []},
                           client=Scripted(*replies), model="gpt-5.5",
                           call_tool=workspace.call_tool)


def test_a_defective_proposal_gets_one_repair_round():
    bad = proposal(pipelines=[{"project": "draft", "graph": "idea"}])
    answer = json.loads(main.run(context(json.dumps(bad), json.dumps(proposal()))))
    assert answer["kind"] == "proposal" and answer["defects"] == []


def test_a_proposal_that_fails_twice_is_returned_with_its_defects():
    bad = json.dumps(proposal(storage="s3"))
    answer = json.loads(main.run(context(bad, bad)))
    assert answer["defects"], "the person is never shown a proposal as clean when it is not"


def test_a_question_is_an_answer():
    answer = json.loads(main.run(context(json.dumps({"kind": "question",
                                                     "question": "Which accounts count?"}))))
    assert answer["kind"] == "question" and not answer["defects"]
