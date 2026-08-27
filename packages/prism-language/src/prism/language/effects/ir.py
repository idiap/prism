# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Primitive typed execution IR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from prism.language.core import CoreType
from prism.language.kernel import CheckedModule, Term


@dataclass(frozen=True, slots=True)
class ValueBinding:
    name: str
    expression: Any
    type: CoreType


@dataclass(frozen=True, slots=True)
class Literal:
    value: Any


@dataclass(frozen=True, slots=True)
class Reference:
    name: str


@dataclass(frozen=True, slots=True)
class ListValue:
    items: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class TupleValue:
    items: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class MapValue:
    items: tuple[tuple[Any, Any], ...]


@dataclass(frozen=True, slots=True)
class Field:
    value: Any
    name: str


@dataclass(frozen=True, slots=True)
class CallArgument:
    value: Any
    name: str | None = None


@dataclass(frozen=True, slots=True)
class CallExpression:
    callee: Any
    arguments: tuple[CallArgument, ...]
    result_type: CoreType | None = None
    expected_term: Term | None = None


@dataclass(frozen=True, slots=True)
class Try:
    value: Any


@dataclass(frozen=True, slots=True)
class ReasoningInvocation:
    callee: Any
    arguments: tuple[CallArgument, ...]


@dataclass(frozen=True, slots=True)
class Solve:
    reasoning: Any | None
    workflow: Any


@dataclass(frozen=True, slots=True)
class Execute:
    reasoning: Any | None
    workflow: Any


@dataclass(frozen=True, slots=True)
class Unary:
    operator: str
    operand: Any


@dataclass(frozen=True, slots=True)
class Binary:
    left: Any
    operator: str
    right: Any


@dataclass(frozen=True, slots=True)
class Conditional:
    condition: Any
    when_true: Any
    when_false: Any


@dataclass(frozen=True, slots=True)
class Index:
    value: Any
    index: Any


@dataclass(frozen=True, slots=True)
class Call:
    target: str
    callable_name: str
    arguments: tuple[Any, ...]
    named_arguments: Mapping[str, Any]
    result_type: CoreType
    effects: tuple[str, ...] = ()
    call_id: str = ""


@dataclass(frozen=True, slots=True)
class Return:
    expression: Any


@dataclass(frozen=True, slots=True)
class RecordDefinition:
    name: str
    fields: tuple[tuple[str, CoreType], ...]


@dataclass(frozen=True, slots=True)
class FunctionDefinition:
    name: str
    parameters: tuple[tuple[str, CoreType], ...]
    result_type: CoreType
    effects: tuple[str, ...]
    body: tuple[Any, ...]
    kind: str = "def"


@dataclass(frozen=True, slots=True)
class ExecutableProgram:
    path: str | None
    source_hash: str
    declarations: tuple[Any, ...]
    entry_callable: str | None
    module_hashes: Mapping[str, str] = field(default_factory=dict)
    ir_version: str = "10"
    checked_module: CheckedModule | None = None
