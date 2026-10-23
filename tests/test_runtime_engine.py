# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Regression checks for the engine package and its host-value boundary."""

import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from prism.language.core import CoreType
from prism.language.effects import (
    ExecutableProgram,
    FunctionDefinition,
    Reference,
    Return,
)
from prism.runtime import FakeEffectHandler, engine, run


def test_occurrence_ancestry_is_upstream_and_survives_selection():
    from types import SimpleNamespace

    from prism.language.core.occurrences import OriginConstraint, ValueRequirement
    from prism.runtime.engine.occurrences import check_requirements
    from prism.runtime.engine.provenance import ProvenanceTracker
    from prism.runtime.replay import EffectRecorder

    tracker = ProvenanceTracker(EffectRecorder().store)
    prompt = tracker.record(3, "literal", "prompt")
    generated = tracker.record(3, "generated", "generation", (prompt,))
    condition = tracker.record(True, "literal", "condition")
    selected = tracker.select(generated, (condition,))
    runtime = SimpleNamespace(
        provenance=tracker,
        global_env={},
        program=SimpleNamespace(variants={}, record_contracts={}),
    )
    requirement = ValueRequirement(
        (), CoreType("Int"), OriginConstraint(("generated",), ("literal",))
    )
    check_requirements(runtime, (requirement,), 3, selected)
    transformed = tracker.record(4, "computed", "arithmetic", (selected,))
    requirement = ValueRequirement(
        (), CoreType("Int"), OriginConstraint(("computed",), ("literal",))
    )
    with pytest.raises(ValueError, match="ancestors.*generated"):
        check_requirements(runtime, (requirement,), 4, transformed)


@pytest.mark.parametrize("container", ["List", "Set", "Tuple", "Map", "Option"])
def test_occurrence_container_requirements_check_actual_members(container):
    from types import SimpleNamespace

    from prism.language.core import GeneratedValue
    from prism.language.core.occurrences import value_requirements
    from prism.runtime.engine.occurrences import check_requirements
    from prism.runtime.engine.provenance import ProvenanceTracker
    from prism.runtime.replay import EffectRecorder

    tracker = ProvenanceTracker(EffectRecorder().store)
    item = GeneratedValue(3, "test generator")
    item_ref = tracker.record(item, "generated", "generation")
    wrappers = {
        "List": [item],
        "Set": {item},
        "Tuple": (item,),
        "Map": {item: item},
        "Option": item,
    }
    value = wrappers[container]
    fields = {str(item) if container == "Map" else "0": item_ref}
    reference = (
        item_ref
        if container == "Option"
        else tracker.record(
            value,
            "computed",
            "collection assembly",
            (item_ref,),
            children=fields,
            entries=((item_ref, item_ref),) if container == "Map" else (),
        )
    )
    runtime = SimpleNamespace(
        provenance=tracker,
        global_env={},
        program=SimpleNamespace(variants={}, record_contracts={}),
    )
    generated = CoreType("Generated", (CoreType("Int"),))
    type_ = CoreType(container, (generated,) * (2 if container == "Map" else 1))
    requirements = value_requirements(type_, {})
    check_requirements(runtime, requirements, value, reference)
    if container == "Option":
        empty_ref = tracker.record(None, "literal", "empty option")
        check_requirements(runtime, requirements, None, empty_ref)
    forged_ref = tracker.record(7, "literal", "forged collection")
    with pytest.raises(ValueError, match="occurrence"):
        check_requirements(runtime, requirements, 7, forged_ref)


def test_occurrence_map_keys_retain_their_actual_producer():
    from prism.language import check, compile, elaborate, parse_source

    source = """
def main(model: Model, access: ModelGenerate) -> Result[Map[Int, Int], ModelFailure] ! {AI.Generate}:
    generated = try generate[Int](3, model, access)
    return Ok({generated.value: 4})
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )
    graph = output.provenance
    assert graph is not None
    assert graph.result is not None
    values = {value.identity: value for value in graph.values}
    activities = {activity.identity: activity for activity in graph.activities}
    mapping = values[dict(values[graph.result].children)["value"]]
    key, value = mapping.entries[0]
    assert activities[values[key].activity].kind == "generated"
    assert activities[values[value].activity].kind == "literal"


def test_nested_invocations_and_runs_have_distinct_trace_identities():
    from prism.language import check, compile, elaborate, parse_source

    source = """
def identity(value: Int) -> Int:
    return value
workflow inner(value: Int) -> Int:
    [result: identity]
def nested(value: Int) -> Int:
    return solve inner(value)
workflow outer(value: Int) -> Int:
    [result: nested]
def main() -> Int:
    return solve outer(7)
"""
    executable = compile(elaborate(check(parse_source(source))))
    outputs = [run(executable, handler=FakeEffectHandler()) for _ in range(2)]
    assert outputs[0].metadata["run_id"] != outputs[1].metadata["run_id"]
    assert all(output.result == 7 for output in outputs)
    for output in outputs:
        calls = [event for event in output.trace if event.kind == "workflow-call"]
        assert len({event.metadata["invocation_id"] for event in calls}) == 2
        assert (
            calls[1].metadata["parent_invocation_id"]
            == calls[0].metadata["invocation_id"]
        )
        occurrences = [event for event in output.trace if event.kind == "workflow-node"]
        assert (
            len({event.metadata["occurrence_instance_id"] for event in occurrences})
            == 2
        )
        assert all(
            event.metadata["declared_contract"]["identity"]
            == event.metadata["source_occurrence_id"]
            for event in occurrences
        )
        for event in occurrences:
            assert event.outcome is not None
            assert event.outcome.execution == "completed"
            assert event.outcome.observed[0].assurance == "unchecked"
            assert event.outcome.observed[0].claim_disposition == "not_applicable"


def test_engine_functions_have_complexity_below_ten() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            str(Path(engine.__file__).parent),
            "--isolated",
            "--select",
            "C901",
            "--config",
            "lint.mccabe.max-complexity=9",
            "--ignore-noqa",
            "--no-cache",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def _identity_program(type_: CoreType) -> ExecutableProgram:
    definition = FunctionDefinition(
        "main", (("value", type_),), type_, (), (Return(Reference("value")),)
    )
    return ExecutableProgram(None, "host-values", (definition,), "main")


@pytest.mark.parametrize(
    "name, supplied, expected",
    [
        ("Unit", None, None),
        ("Bool", False, False),
        ("Int", -2, -2),
        ("Nat", 0, 0),
        ("Float", 2, 2.0),
        ("Decimal", "1.25", Decimal("1.25")),
        ("Char", "é", "é"),
        ("Bytes", "aGVsbG8=", b"hello"),
    ],
)
def test_host_scalar_conversion_preserves_python_types(
    name: str, supplied: Any, expected: Any
) -> None:
    output = run(
        _identity_program(CoreType(name)),
        handler=FakeEffectHandler(),
        entry_arguments={"value": supplied},
    )

    assert output.result == expected
    assert type(output.result) is type(expected)


@pytest.mark.parametrize(
    "name, supplied",
    [
        ("Unit", 0),
        ("Bool", 1),
        ("Int", True),
        ("Nat", -1),
        ("Nat", False),
        ("Float", True),
        ("Decimal", "invalid"),
        ("Decimal", True),
        ("Char", "ab"),
        ("Bytes", "%%%"),
        ("Bytes", b"hello"),
    ],
)
def test_host_scalars_reject_incompatible_values(name: str, supplied: Any) -> None:
    with pytest.raises(TypeError, match=f"host argument `value` expected {name}"):
        run(
            _identity_program(CoreType(name)),
            handler=FakeEffectHandler(),
            entry_arguments={"value": supplied},
        )


@pytest.mark.parametrize(
    "type_, supplied, expected",
    [
        (CoreType("Set", (CoreType("Int"),)), [1, 1, 2], {1, 2}),
        (CoreType("Option", (CoreType("Int"),)), None, None),
        (CoreType("Option", (CoreType("Int"),)), 3, 3),
        (
            CoreType("Tuple", (CoreType("Int"), CoreType("Bytes"))),
            [2, "aGk="],
            (2, b"hi"),
        ),
    ],
)
def test_host_collections_convert_nested_values(
    type_: CoreType, supplied: Any, expected: Any
) -> None:
    output = run(
        _identity_program(type_),
        handler=FakeEffectHandler(),
        entry_arguments={"value": supplied},
    )

    assert output.result == expected
    assert type(output.result) is type(expected)


def test_nested_host_conversion_reports_the_failing_path() -> None:
    type_ = CoreType("List", (CoreType("Option", (CoreType("Nat"),)),))

    with pytest.raises(TypeError, match=r"host argument `value\[2\]` expected Nat"):
        run(
            _identity_program(type_),
            handler=FakeEffectHandler(),
            entry_arguments={"value": [None, 0, -1]},
        )


def test_ordinary_occurrence_records_actual_inputs_and_output_artifacts():
    from prism.language import check, compile, elaborate, parse_source
    from prism.runtime.replay import EffectRecorder

    source = """
def fixed(value: Int) -> Int:
    return 7
workflow plan(value: Int) -> Int:
    [result: fixed(value)]
    return result
def main() -> Int:
    return solve plan(99)
"""
    recorder = EffectRecorder()
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=FakeEffectHandler(),
        effect_recorder=recorder,
    )
    assert output.result == 7
    graph = output.provenance
    assert graph is not None
    values = {value.identity: value for value in graph.values}
    node = next(event for event in output.trace if event.kind == "workflow-node")
    input_artifact = values[node.metadata["input_reference"]].artifact
    output_artifact = values[node.metadata["output_reference"]].artifact
    assert input_artifact is not None and output_artifact is not None
    assert recorder.store.get(input_artifact) == 99
    assert recorder.store.get(output_artifact) == 7
    assert all(
        reference in values
        for activity in graph.activities
        for reference in activity.inputs
    )
    assert all(
        reference in values for value in graph.values for _, reference in value.children
    )

    assert all(
        reference in values
        for value in graph.values
        for reference in value.dependencies
    )
