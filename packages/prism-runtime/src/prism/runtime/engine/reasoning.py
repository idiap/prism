# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Reasoning configuration and concrete workflow construction."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Mapping

from prism.language.core import (
    CoreType,
    substitute_type,
)
from prism.language.effects import (
    Reference,
)
from prism.language.workflows import (
    Choice,
    NodeOccurrence,
    Parallel,
    ReasoningDefinition,
    Repeat,
    Sequence,
    WorkflowDefinition,
)
from prism.runtime.results import TraceEvent

from .composition import _composition_nodes
from .provenance import ValueEnvironment
from .values import (
    ReasoningInvocationValue,
    RelationBuilderValue,
    WorkflowValue,
    _RelationFactory,
)

if TYPE_CHECKING:
    from .execution import _Engine


def _reasoning_configuration_bindings(
    self: _Engine,
    definition: ReasoningDefinition,
    supplied: Mapping[str, Any],
) -> Mapping[str, Any]:
    bindings: dict[str, Any] = {}
    switch_names = {
        exit_.target.rsplit(".", 1)[-1]
        for exit_ in definition.exits
        if exit_.action == "switch" and exit_.target
    }
    for name, value in supplied.items():
        if name in switch_names:
            continue
        if name.endswith("_by") and not isinstance(value, RelationBuilderValue):
            occurrence = name[: -len("_by")]
            node = next(
                item
                for item in _composition_nodes(definition.composition)
                if item.alias == occurrence and item.relation
            )
            relation = self.global_env.get(node.relation or "")
            if not isinstance(relation, _RelationFactory):
                matches = [
                    candidate
                    for candidate_name, candidate in self.global_env.items()
                    if isinstance(candidate, _RelationFactory)
                    and candidate_name.rsplit(".", 1)[-1]
                    == (node.relation or "").rsplit(".", 1)[-1]
                ]
                relation = matches[0] if len(matches) == 1 else None
            if not isinstance(relation, _RelationFactory):
                raise ValueError(
                    f"reasoning edge `{name}` has no loaded relation declaration"
                )
            value = RelationBuilderValue(relation.definition, value)
        bindings[name] = value
    if switch_names:
        bindings["switches"] = {name: supplied[name] for name in switch_names}
    return bindings


def _materialize_reasoning(
    self: _Engine,
    definition: ReasoningDefinition,
    implementation_bindings: Mapping[str, Any],
    values: Mapping[str, Any],
    result_type: CoreType | None,
) -> WorkflowValue:
    occurrence_names = {
        node.alias
        for node in _composition_nodes(definition.composition)
        if node.alias is not None and node.contract.execution_kind == "method"
    }
    captured = ValueEnvironment(values)
    captured.update(
        {
            (
                _reasoning_implementation_name(name)
                if name in occurrence_names
                else name
            ): value
            for name, value in implementation_bindings.items()
        }
    )
    workflow_type = result_type or CoreType(
        "Workflow",
        (definition.result_type, CoreType("Never")),
    )
    contract = workflow_type.invocation
    if contract is None or contract.identity != definition.identity:
        raise ValueError("materialization is missing its checked reasoning invocation")
    substitutions = dict(
        zip(definition.type_parameters, contract.specialization, strict=True)
    )
    if workflow_type.name != "Workflow" or len(workflow_type.arguments) < 2:
        raise ValueError("materialization requires a checked workflow result type")
    success, failure = workflow_type.arguments[:2]
    effects = tuple(item.name for item in workflow_type.arguments[2:])
    materialized = WorkflowDefinition(
        definition.name,
        (),
        success,
        failure,
        effects,
        _materialize_reasoning_composition(
            definition.composition,
            substitutions,
            self.program.record_contracts,
            self.program.variants,
        ),
        definition.result_alias,
        definition.exits,
        definition.name,
    )
    self.trace.append(
        TraceEvent(
            "reasoning-materialized",
            definition.name,
            metadata={
                "occurrences": tuple(
                    name
                    for name in implementation_bindings
                    if not name.endswith("_by")
                    and not name.endswith("_input")
                    and name != "switches"
                ),
                "input_adapters": tuple(
                    name for name in implementation_bindings if name.endswith("_input")
                ),
                "relations": tuple(
                    name for name in implementation_bindings if name.endswith("_by")
                ),
                "switches": tuple(implementation_bindings.get("switches", {})),
                "effects": effects,
                "failure": failure.render(),
            },
        )
    )
    logical = {name: values[name] for name, _ in definition.parameters}
    return WorkflowValue(
        materialized,
        captured,
        ReasoningInvocationValue(definition, logical, contract.specialization),
    )


def _reasoning_configuration_names(
    definition: ReasoningDefinition,
) -> tuple[str, ...]:
    nodes = _composition_nodes(definition.composition)
    occurrences = tuple(
        node.alias
        for node in nodes
        if node.alias and node.contract.execution_kind == "method"
    )
    inputs = tuple(
        f"{node.alias}_input"
        for node in nodes
        if node.alias and node.input_adapter is not None
    )
    relations = tuple(
        f"{node.alias}_by" for node in nodes if node.alias and node.relation
    )
    switches = tuple(
        dict.fromkeys(
            exit_.target.rsplit(".", 1)[-1]
            for exit_ in definition.exits
            if exit_.action == "switch" and exit_.target
        )
    )
    return (*occurrences, *inputs, *relations, *switches)


def _materialize_reasoning_composition(
    composition: Any, substitutions, records, variants
) -> Any:
    if isinstance(composition, NodeOccurrence):
        if composition.contract.execution_kind == "structural":
            contract = composition.contract.specialize(substitutions, records, variants)
            return replace(
                composition,
                contract=contract,
                component=replace(
                    composition.component, result_type=contract.output_type
                ),
            )
        if composition.alias is None:
            raise ValueError("materialized reasoning occurrences require aliases")
        if composition.logical_input is None:
            raise ValueError(
                "materialized reasoning occurrences require a logical input"
            )
        return NodeOccurrence(
            Reference(_reasoning_implementation_name(composition.alias)),
            composition.alias,
            composition.contract.specialize(substitutions, records, variants),
            composition.relation,
            composition.dependencies,
            composition.logical_input,
            composition.input_adapter,
            substitute_type(composition.method_type, substitutions)
            if composition.method_type
            else None,
            substitute_type(composition.topology_input_type, substitutions)
            if composition.topology_input_type
            else None,
        )
    if isinstance(composition, Sequence):
        return Sequence(
            tuple(
                _materialize_reasoning_composition(
                    child, substitutions, records, variants
                )
                for child in composition.children
            ),
            composition.relation,
        )
    if isinstance(composition, Parallel):
        return Parallel(
            tuple(
                _materialize_reasoning_composition(
                    child, substitutions, records, variants
                )
                for child in composition.children
            ),
            composition.relation,
        )
    if isinstance(composition, Repeat):
        return Repeat(
            composition.policy,
            tuple(
                _materialize_reasoning_composition(
                    child, substitutions, records, variants
                )
                for child in composition.children
            ),
            composition.relation,
            composition.until,
        )
    if isinstance(composition, Choice):
        return Choice(
            _materialize_reasoning_composition(
                composition.router, substitutions, records, variants
            ),
            tuple(
                type(arm)(
                    arm.pattern,
                    tuple(
                        _materialize_reasoning_composition(
                            child, substitutions, records, variants
                        )
                        for child in arm.children
                    ),
                )
                for arm in composition.arms
            ),
            composition.relation,
        )
    raise TypeError(f"unsupported reasoning composition `{type(composition).__name__}`")


def _reasoning_implementation_name(alias: str) -> str:
    return f"__reasoning_implementation_{alias}"
