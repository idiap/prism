# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Runtime values and internal control-flow signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from prism.language.core import (
    CoreType,
    Err,
    Ok,
)
from prism.language.effects import (
    FunctionDefinition,
    RecordDefinition,
)
from prism.language.evidence import Supported
from prism.language.workflows import (
    Agent,
    ReasoningDefinition,
    RelationDefinition,
    WorkflowDefinition,
)


@dataclass(frozen=True, slots=True)
class CapabilityValue:
    type_name: str


@dataclass(frozen=True, slots=True)
class ClaimValue:
    text: str = field(compare=False)
    identity: str | None = None
    arguments: tuple[Any, ...] = ()
    specialization: tuple[CoreType, ...] = ()

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class PolicyValue:
    name: str
    evaluator: Any
    operational_inputs: Mapping[str, Any]
    claim: ClaimValue
    identity: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class ValidatorValue:
    callable: Any
    contract: CoreType
    identity: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class SkillArtifactValue:
    skill_id: str
    version: str
    name: str
    description: str
    instructions: str
    resources: str


@dataclass(frozen=True, slots=True)
class HooksArtifactValue:
    provider: str
    configuration: str


@dataclass(frozen=True, slots=True)
class ToolValue:
    name: str
    callable: Any


@dataclass(frozen=True, slots=True)
class WorkflowValue:
    definition: WorkflowDefinition
    captured: dict[str, Any]
    invocation: ReasoningInvocationValue | None = None


@dataclass(frozen=True, slots=True)
class _Builtin:
    name: str


@dataclass(frozen=True, slots=True)
class _Callable:
    definition: FunctionDefinition


@dataclass(frozen=True, slots=True)
class _WorkflowFactory:
    definition: WorkflowDefinition


@dataclass(frozen=True, slots=True)
class _ReasoningFactory:
    definition: ReasoningDefinition


@dataclass(frozen=True, slots=True)
class ReasoningInvocationValue:
    definition: ReasoningDefinition
    captured: Mapping[str, Any]
    specialization: tuple[CoreType, ...] = ()


@dataclass(frozen=True, slots=True)
class _ConfiguredReasoning:
    definition: ReasoningDefinition
    bindings: Mapping[str, Any]
    invocation_type: CoreType | None = None


@dataclass(frozen=True, slots=True)
class _RelationFactory:
    definition: RelationDefinition


@dataclass(frozen=True, slots=True)
class RelationBuilderValue:
    definition: RelationDefinition
    builder: Any


@dataclass(frozen=True, slots=True)
class ReasoningStoppedValue:
    reasoning: str
    occurrence: str
    selector: str


@dataclass(frozen=True, slots=True)
class _RecordFactory:
    definition: RecordDefinition


@dataclass(frozen=True, slots=True)
class _AgentCallable:
    definition: Agent


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _ReasoningExitSignal(Exception):
    def __init__(
        self,
        action: str,
        value: Any,
        occurrence: str,
        selector: str,
        target: str | None,
    ) -> None:
        self.action = action
        self.value = value
        self.occurrence = occurrence
        self.selector = selector
        self.target = target


class _Propagate(Exception):
    def __init__(self, error: Any) -> None:
        self.error = error


def _value_status(value: Any) -> str:
    if isinstance(value, Err):
        return "rejected"
    if isinstance(value, Ok):
        return _value_status(value.value)
    if isinstance(value, Supported):
        return value.status
    return "accepted"
