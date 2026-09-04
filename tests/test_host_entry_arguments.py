# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from prism.language import check, compile, elaborate, parse_source
from prism.language.core import RecordValue
from prism.runtime import EffectRecorder, FakeEffectHandler, run

SOURCE = """
type Request:
    goal: String
    count: Nat

type Response:
    summary: String

agent reviewer(request: Request) -> Result[Generated[Response], ModelFailure] ! {AI.Generate}:

def main(
    request: Request,
    model_access: ModelGenerate,
) -> Result[Generated[Response], ModelFailure] ! {AI.Generate}:
    return reviewer(request)
"""


def _program():
    return compile(elaborate(check(parse_source(SOURCE))))


def test_embedded_run_accepts_a_typed_record_host_argument() -> None:
    output = run(
        _program(),
        handler=FakeEffectHandler(),
        entry_arguments={"request": {"goal": "review", "count": 2}},
    )

    assert output.status == "accepted"
    invocation = next(event for event in output.trace if event.kind == "agent-invoked")
    assert invocation.name == "reviewer"


@pytest.mark.parametrize(
    "arguments, error",
    [
        ({}, "missing: request"),
        (
            {"request": {"goal": "review", "count": 2}, "unexpected": True},
            "extra: unexpected",
        ),
        (
            {"request": {"goal": "review", "count": "two"}},
            "request.count.*expected Nat",
        ),
    ],
)
def test_invalid_host_arguments_fail_before_an_effect(
    arguments: dict[str, object], error: str
) -> None:
    recorder = EffectRecorder()

    with pytest.raises((TypeError, ValueError), match=error):
        run(
            _program(),
            handler=FakeEffectHandler(),
            effect_recorder=recorder,
            entry_arguments=arguments,
        )

    assert recorder.records == {}


def test_capabilities_are_injected_and_cannot_be_supplied_by_the_host() -> None:
    with pytest.raises(ValueError, match="extra: model_access"):
        run(
            _program(),
            handler=FakeEffectHandler(),
            entry_arguments={
                "request": {"goal": "review", "count": 2},
                "model_access": "not-a-capability",
            },
        )


def test_record_conversion_is_visible_to_the_checked_program() -> None:
    source = """
type Request:
    goal: String
    count: Nat
def main(request: Request) -> Request:
    return request
"""
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=FakeEffectHandler(),
        entry_arguments={"request": {"goal": "review", "count": 2}},
    )

    assert output.result == RecordValue("Request", {"goal": "review", "count": 2})


def test_nested_lists_mappings_and_variants_are_converted() -> None:
    source = """
type Choice:
    | Selected(value: String)
    | Skipped
type Request:
    labels: List[String]
    scores: Map[String, Int]
    choice: Choice
def main(request: Request) -> Request:
    return request
"""
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=FakeEffectHandler(),
        entry_arguments={
            "request": {
                "labels": ["a", "b"],
                "scores": {"a": 1},
                "choice": {"Selected": {"value": "a"}},
            }
        },
    )

    assert output.result == RecordValue(
        "Request",
        {
            "labels": ["a", "b"],
            "scores": {"a": 1},
            "choice": RecordValue("Selected", {"value": "a"}),
        },
    )
