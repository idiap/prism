# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from prism.language import check, compile, elaborate, parse_source
from prism.language.core import GeneratedValue, Ok, RecordValue
from prism.language.developer import PrismSyntaxError, PrismTypeError
from prism.language.effects import EffectResult
from prism.language.workflows import Agent, Tool
from prism.runtime import FakeEffectHandler, run

PROGRAM = """
type Task:
    text: String

type Draft:
    text: String

type Normalize = Task -> Draft

def normalize(task: Task) -> Draft:
    return Draft(text = task.text)

tool normalize_tool: Tool[Normalize] = normalize

review_skill: Skill[Task] = skill_artifact[Task](
    "review", "1.0.0", "Review", "Review a task", "Be precise.", "{}"
)
codex_hooks: Hooks[Codex] = hooks_artifact[Codex]("{\\"hooks\\":{}}")

agent reviewer(task: Task) -> Result[Generated[Draft], ModelFailure]
    ! {AI.Generate, Tool.Call, Context.Disclose}:
    tools: Tools[Normalize] = [normalize_tool]
    skills: Skills[Task] = [review_skill]
    hooks: Hooks[Codex] = codex_hooks

def invoke(task: Task, policy_tool: Tool[Normalize]) -> Result[Generated[Draft], ModelFailure] ! {AI.Generate, Tool.Call, Context.Disclose}:
    return reviewer(
        task,
        tools = [policy_tool],
        skills = [review_skill],
        hooks = codex_hooks,
    )
"""


def test_tools_artifacts_and_agents_are_fully_typed() -> None:
    checked = check(parse_source(PROGRAM))
    assert checked.globals["normalize_tool"].type.name == "Tool"
    assert checked.globals["review_skill"].type.render() == "Skill[Task]"
    assert checked.globals["codex_hooks"].type.render() == "Hooks[Codex]"
    assert checked.callable_contracts["reviewer"].kind == "agent"
    declarations = compile(elaborate(checked)).declarations
    assert any(isinstance(item, Tool) for item in declarations)
    assert any(isinstance(item, Agent) for item in declarations)


def test_agent_is_directly_callable_inside_an_unchanged_workflow() -> None:
    source = (
        PROGRAM
        + """

workflow review(task: Task) -> Generated[Draft]
    fails ModelFailure
    ! {AI.Generate, Tool.Call, Context.Disclose}:
    sequence:
        [draft: reviewer(task)]
    return draft
"""
    )
    checked = check(parse_source(source))
    assert checked.callable_contracts["review"].kind == "workflow"


def test_fake_handler_synthesizes_typed_agent_output_from_schema() -> None:
    source = (
        PROGRAM
        + """
def main() -> Result[Generated[Draft], ModelFailure] ! {AI.Generate, Tool.Call, Context.Disclose}:
    return reviewer(Task(text = "review this"))
"""
    )
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=FakeEffectHandler(),
    )

    assert output.status == "accepted"
    assert output.result.value.value == RecordValue("Draft", {"text": "synthetic"})


def test_invocation_local_capabilities_must_be_typed() -> None:
    with pytest.raises(PrismTypeError, match="invocation `skills`"):
        check(
            parse_source(
                PROGRAM
                + '\nbad = reviewer(Task(text = "x"), skills = [normalize_tool])\n'
            )
        )


def test_native_skill_declarations_are_removed() -> None:
    with pytest.raises(PrismSyntaxError, match="build the Open Agent Skill"):
        parse_source('skill Local[Task]:\n    instructions = "x"\n')


def test_invocation_capabilities_extend_without_mutating_the_agent() -> None:
    source = (
        PROGRAM
        + """
tool policy_tool: Tool[Normalize] = normalize
security_skill: Skill[Task] = skill_artifact[Task](
    "security", "1.0.0", "Security", "Review security", "Check security.", "{}"
)
strict_hooks: Hooks[Codex] = hooks_artifact[Codex]("{\\"hooks\\":{\\"Stop\\":[]}}")

def main() -> Result[Generated[Draft], ModelFailure] ! {AI.Generate, Tool.Call, Context.Disclose}:
    first = reviewer(
        Task(text = "first"),
        tools = [policy_tool],
        skills = [security_skill],
        hooks = strict_hooks,
    )
    return reviewer(Task(text = "second"))
"""
    )

    class RecordingHandler:
        def __init__(self) -> None:
            self.requests = []

        def handles(self, symbol, effects) -> bool:
            return symbol == "generate"

        def execute(self, request):
            self.requests.append(request)
            return EffectResult(
                Ok(GeneratedValue(RecordValue("Draft", {"text": "ok"}), "test")),
                request.result_type,
            )

    handler = RecordingHandler()
    run(compile(elaborate(check(parse_source(source)))), handler=handler)

    assert [request.named_arguments["tools"] for request in handler.requests] == [
        ("normalize_tool", "policy_tool"),
        ("normalize_tool",),
    ]
    assert [len(request.named_arguments["hooks"]) for request in handler.requests] == [
        2,
        1,
    ]
    assert ['"skill_id"' in request.arguments[0] for request in handler.requests] == [
        False,
        False,
    ]
    assert [
        request.arguments[0].count('"instructions"') for request in handler.requests
    ] == [2, 1]
