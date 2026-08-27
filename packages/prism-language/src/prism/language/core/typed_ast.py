# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Resolved and typed representation emitted by elaboration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from prism.language.kernel import CheckedModule, Term

from .bindings import Binding
from .declarations import CallableContract, RecordContract
from .types import CoreType


@dataclass(frozen=True, slots=True)
class TypedExpression:
    source: Any
    type: CoreType
    effects: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TypedModule:
    path: str | None
    source: str
    declarations: tuple[Any, ...]
    globals: Mapping[str, Binding]
    callable_contracts: Mapping[str, CallableContract]
    record_contracts: Mapping[str, RecordContract]
    expression_types: Mapping[int, CoreType] = field(default_factory=dict)
    proof_goals: tuple[Any, ...] = ()
    module_hashes: Mapping[str, str] = field(default_factory=dict)
    aliases: Mapping[str, CoreType] = field(default_factory=dict)
    type_parameters: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    variants: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    reasoning_outputs: Mapping[str, Mapping[str, CoreType]] = field(
        default_factory=dict
    )
    reasoning_methods: Mapping[str, Mapping[str, CoreType]] = field(
        default_factory=dict
    )
    callable_origins: Mapping[str, str | None] = field(default_factory=dict)
    checked_module: CheckedModule | None = None
    expression_terms: Mapping[int, Term] = field(default_factory=dict)
