# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Exact declaration and module environments for checked core terms."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal, Mapping

from .diagnostics import KernelError
from .terms import Term

DeclarationKind = Literal[
    "axiom", "definition", "theorem", "inductive", "constructor", "recursor"
]


@dataclass(frozen=True, slots=True)
class RecursorRule:
    constructor: str
    constructor_arity: int
    method_index: int
    recursive_positions: tuple[int, ...] = ()
    field_positions: tuple[int, ...] | None = None


@dataclass(frozen=True, slots=True)
class RecursorSpec:
    scrutinee_index: int
    rules: tuple[RecursorRule, ...]


@dataclass(frozen=True, slots=True)
class Declaration:
    name: str
    type: Term
    value: Term | None = None
    kind: DeclarationKind = "definition"
    universe_parameters: tuple[str, ...] = ()
    transparent: bool = True
    pure: bool = True
    total: bool = True
    inductive_name: str | None = None
    recursor: RecursorSpec | None = None
    axiom_dependencies: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.name:
            raise KernelError(
                "declarations require a name", code="kernel-declaration-name"
            )
        if self.kind == "axiom" and self.value is not None:
            raise KernelError("axioms cannot have values", code="kernel-axiom-value")
        if self.kind in {"definition", "theorem"} and self.value is None:
            raise KernelError(
                f"{self.kind} `{self.name}` requires a value",
                code="kernel-declaration-value",
            )
        if (
            self.kind in {"inductive", "constructor", "recursor"}
            and self.value is not None
        ):
            raise KernelError(
                f"{self.kind} `{self.name}` cannot carry a definition value",
                code="kernel-declaration-value",
            )
        if self.kind in {"constructor", "recursor"} and self.inductive_name is None:
            raise KernelError(
                f"{self.kind} `{self.name}` requires its inductive family",
                code="kernel-inductive-owner",
            )
        if self.kind == "recursor" and self.recursor is None:
            raise KernelError(
                f"recursor `{self.name}` requires reduction metadata",
                code="kernel-recursor-metadata",
            )
        if self.recursor is not None and self.kind != "recursor":
            raise KernelError(
                "only recursor declarations can carry reduction rules",
                code="kernel-recursor-kind",
            )


@dataclass(frozen=True, slots=True)
class ModuleImport:
    name: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class Environment:
    declarations: tuple[Declaration, ...] = ()
    module_hashes: tuple[tuple[str, str], ...] = ()
    calculus_version: str = "prism-core-v1"

    def get(self, name: str) -> Declaration:
        for declaration in reversed(self.declarations):
            if declaration.name == name:
                return declaration
        raise KernelError(f"unknown constant `{name}`", code="kernel-unknown-constant")

    def contains(self, name: str) -> bool:
        return any(item.name == name for item in self.declarations)

    def extend(self, declaration: Declaration) -> "Environment":
        if self.contains(declaration.name):
            raise KernelError(
                f"duplicate declaration `{declaration.name}`",
                code="kernel-duplicate-declaration",
            )
        return Environment(
            (*self.declarations, declaration),
            self.module_hashes,
            self.calculus_version,
        )

    @property
    def hash(self) -> str:
        from .serialization import canonical_bytes, declaration_to_data

        payload = {
            "calculus": self.calculus_version,
            "modules": self.module_hashes,
            "declarations": [declaration_to_data(item) for item in self.declarations],
        }
        return hashlib.sha256(canonical_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class CheckedTerm:
    term: Term
    type: Term
    environment_hash: str
    term_hash: str
    type_hash: str
    axioms: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class CheckedModule:
    name: str
    imports: tuple[ModuleImport, ...]
    declarations: tuple[Declaration, ...]
    environment: Environment
    content_hash: str
    core_format_version: str = "1"
    calculus_version: str = "prism-core-v1"
    axiom_dependencies: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def axioms_for(self, declaration: str) -> frozenset[str]:
        return self.axiom_dependencies.get(declaration, frozenset())
