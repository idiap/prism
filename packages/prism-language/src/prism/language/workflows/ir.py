# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workflow execution IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prism.language.core import CoreType
from prism.language.core.occurrences import OccurrenceContract


@dataclass(frozen=True, slots=True)
class NodeOccurrence:
    component: Any
    alias: str | None
    contract: OccurrenceContract
    relation: str | None = None
    dependencies: tuple[str, ...] = ()
    logical_input: Any | None = None
    input_adapter: Any | None = None
    method_type: Any | None = None
    topology_input_type: Any | None = None

    @property
    def input_type(self) -> CoreType:
        return self.contract.input_type

    @property
    def output_type(self) -> CoreType:
        return self.contract.output_type

    @property
    def certificate_type(self) -> CoreType | None:
        return (
            self.contract.relation.certificate_type if self.contract.relation else None
        )

    @property
    def relation_type(self) -> CoreType | None:
        relation = self.contract.relation
        if relation is None:
            return None
        assert self.relation is not None
        return CoreType(
            "Relation",
            (
                CoreType(self.relation),
                relation.source_type,
                relation.target_type,
                relation.certificate_type,
            ),
        )


@dataclass(frozen=True, slots=True)
class Sequence:
    children: tuple[Any, ...]
    relation: str | None = None


@dataclass(frozen=True, slots=True)
class Parallel:
    children: tuple[Any, ...]
    relation: str | None = None


@dataclass(frozen=True, slots=True)
class ChoiceArm:
    pattern: str
    children: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class Choice:
    router: NodeOccurrence
    arms: tuple[ChoiceArm, ...]
    relation: str | None = None


@dataclass(frozen=True, slots=True)
class Repeat:
    policy: Any
    children: tuple[Any, ...]
    relation: str | None = None
    until: Any | None = None


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    name: str
    parameters: tuple[tuple[str, Any], ...]
    result_type: Any
    failure_type: Any
    effects: tuple[str, ...]
    composition: Any
    result_alias: str | None
    guarded_exits: tuple["GuardedExit", ...] = ()
    abstract_name: str | None = None


@dataclass(frozen=True, slots=True)
class GuardedExit:
    occurrence: str
    selector: str
    action: str
    target: str | None = None


@dataclass(frozen=True, slots=True)
class ReasoningDefinition:
    name: str
    parameters: tuple[tuple[str, Any], ...]
    result_type: Any
    composition: Any
    exits: tuple[GuardedExit, ...]
    result_alias: str | None
    identity: str | None = None
    type_parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationDefinition:
    name: str
    parameters: tuple[tuple[str, Any], ...]
    certificate_type: Any
    type_parameters: tuple[str, ...] = ()
    source_module: str | None = None
    parameter_bindings: tuple[str | None, ...] = ()
    identity: str | None = None


@dataclass(frozen=True, slots=True)
class Agent:
    name: str
    parameters: tuple[tuple[str, Any], ...]
    result_type: Any
    effects: tuple[str, ...]
    tools: Any | None = None
    skills: Any | None = None
    hooks: Any | None = None


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    callable_type: Any
    callable: Any
