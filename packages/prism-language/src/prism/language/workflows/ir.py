# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workflow execution IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NodeOccurrence:
    component: Any
    alias: str | None
    relation: str | None = None
    dependencies: tuple[str, ...] = ()
    logical_input: Any | None = None
    input_adapter: Any | None = None
    method_type: Any | None = None
    topology_input_type: Any | None = None
    input_type: Any | None = None
    output_type: Any | None = None
    relation_type: Any | None = None
    certificate_type: Any | None = None


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


@dataclass(frozen=True, slots=True)
class RelationDefinition:
    name: str
    parameters: tuple[tuple[str, Any], ...]
    certificate_type: Any
    type_parameters: tuple[str, ...] = ()
    source_module: str | None = None


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
