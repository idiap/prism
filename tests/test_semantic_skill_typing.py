# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from prism.language import check, parse_source
from prism.language.developer import PrismTypeError


def test_skill_task_contract_is_invariant() -> None:
    source = """
type ReviewTask:
    request: String

type SecurityTask:
    request: String

review: Skill[ReviewTask] = skill_artifact[ReviewTask]("id", "1", "n", "d", "i", "{}")

agent analyst(task: ReviewTask) -> String ! {AI.Generate}:
    skills: Skills[SecurityTask] = [review]
"""
    with pytest.raises(PrismTypeError, match="rejects skill contract"):
        check(parse_source(source))


def test_hook_provider_is_checked() -> None:
    source = 'bad: Hooks[Codex] = hooks_artifact[Claude]("{}")\n'
    with pytest.raises(PrismTypeError, match="binding `bad`"):
        check(parse_source(source))


def test_tool_must_preserve_the_wrapped_callable_contract() -> None:
    source = """
type Task:
    request: String
type Other:
    request: String
type Contract = Task -> Other
def wrong(task: Task) -> Task:
    return task
tool wrong_tool: Tool[Contract] = wrong
"""
    with pytest.raises(PrismTypeError, match="tool `wrong_tool` output"):
        check(parse_source(source))


def test_tool_cannot_wrap_an_agent() -> None:
    source = """
type Task:
    request: String

type AgentContract = Task -> String ! {AI.Generate}

agent reviewer(task: Task) -> String ! {AI.Generate}:

tool invalid: Tool[AgentContract] = reviewer
"""
    with pytest.raises(PrismTypeError, match="only a def or workflow"):
        check(parse_source(source))


def test_tool_wraps_the_existing_workflow_callable_contract() -> None:
    source = """
type Task:
    request: String

type Prepared:
    request: String

type PrepareWorkflow = Task -> Workflow[Prepared, Never]

def prepare(task: Task) -> Prepared:
    return Prepared(request = task.request)

workflow preflight(task: Task) -> Prepared:
    sequence:
        [prepared: prepare(task)]
    return prepared

tool preflight_tool: Tool[PrepareWorkflow] = preflight
"""
    checked = check(parse_source(source))
    assert checked.globals["preflight_tool"].type.render() == (
        "Tool[(Task) -> Workflow[Prepared, Never]]"
    )
