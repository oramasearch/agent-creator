# SPDX-License-Identifier: MIT

"""AgentCreator's own record grants every read its turn makes (agent-creator#11).

The fake workspace in test_creator.py answers every read, so it cannot see a read the record does
not grant. Here the turn runs against a workspace that answers only what agent-runtime would make a
tool for this record: the reads of the record's skills (agent-runtime's `lake_grant`, published as
its `skills.json` and vendored at tests/fixtures/agent-runtime-skills.json), plus the App and build
reads every agent has (agent-runtime `apps.py`), filtered by `agent.toml`'s `tools` allow-list.
Anything else is refused the way the runtime refuses it.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

from agent import main
from test_creator import FACTS, Workspace

ROOT = Path(__file__).resolve().parent.parent
DEFINITION = ROOT / "definition"
RUNTIME_SKILLS = Path(__file__).resolve().parent / "fixtures" / "agent-runtime-skills.json"
# agent-runtime apps.py APP_READ_CAPABILITIES: every agent's App and build reads.
RUNTIME_APP_READS = {"list_apps", "get_app", "app_logs", "receive_app_events", "list_builds",
                     "get_build", "build_logs", "receive_build_events"}


def record() -> dict:
    return json.loads((DEFINITION / "record.json").read_text())


def allow_list() -> list[str] | None:
    return tomllib.loads((DEFINITION / "agent.toml").read_text()).get("tools")


def granted_reads(skills: list[str]) -> set[str]:
    by_name = {skill["name"]: skill for skill in json.loads(RUNTIME_SKILLS.read_text())["skills"]}
    reads: set[str] = set(RUNTIME_APP_READS)
    for name in skills:
        assert name in by_name, f"{name} is not one of agent-runtime's skills"
        reads |= set(by_name[name]["reads"])
    return reads


def agent_tools() -> set[str]:
    tools = granted_reads(record()["skills"])
    allowed = allow_list()
    return tools if allowed is None else tools & set(allowed)


class GrantedWorkspace(Workspace):
    """The fake workspace, behind the tools agent-runtime would give this record."""

    def __init__(self, tools: set[str], **kwargs):
        super().__init__(**kwargs)
        self.tools = tools
        self.refused: list[str] = []

    def call_tool(self, name, arguments):
        if name not in self.tools:
            self.refused.append(name)
            self.calls.append((name, arguments))
            return SimpleNamespace(ok=False, value=None,
                                   error=f"'{name}' is not one of this agent's tools")
        return super().call_tool(name, arguments)


def test_the_record_grants_every_read_the_turn_makes():
    workspace = GrantedWorkspace(agent_tools())
    facts = main.workspace_facts(workspace)
    assert workspace.refused == []
    assert facts["methodology_source"] == "list_methodologies"
    assert facts == FACTS


def test_without_a_skill_that_grants_list_methodologies_the_registry_is_unavailable():
    # The v0.1.0 record: the turn's methodology read is refused and the registry is unavailable.
    workspace = GrantedWorkspace(granted_reads(["search", "summarize"]))
    facts = main.workspace_facts(workspace)
    assert workspace.refused == ["list_methodologies"]
    assert facts["methodology_source"] == "unavailable"


def test_the_allow_list_is_exactly_the_reads_the_turn_makes():
    allowed = allow_list()
    assert allowed is not None, "agent.toml must keep AgentCreator to its reads"
    workspace = Workspace()
    main.workspace_facts(workspace)
    assert set(allowed) == {name for name, _ in workspace.calls}
    # Every allowed tool is a read the record's skills grant, never a proposal.
    assert set(allowed) <= granted_reads(record()["skills"])
