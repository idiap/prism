# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Local contexts and capture-avoiding de Bruijn operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from .diagnostics import KernelError
from .terms import (
    App,
    Const,
    ConstructorRef,
    InductiveRef,
    Lam,
    Let,
    Local,
    Pi,
    RecursorRef,
    Sort,
    Term,
)


@dataclass(frozen=True, slots=True)
class LocalDeclaration:
    name: str
    type: Term
    value: Term | None = None


@dataclass(frozen=True, slots=True)
class Context:
    """Declarations are stored oldest first; local index zero is the last item."""

    declarations: tuple[LocalDeclaration, ...] = ()

    def push(self, name: str, type: Term, value: Term | None = None) -> "Context":
        return Context((*self.declarations, LocalDeclaration(name, type, value)))

    def lookup(self, index: int) -> LocalDeclaration:
        if index < 0 or index >= len(self.declarations):
            raise KernelError(
                f"escaping local #{index} in context of size {len(self.declarations)}",
                code="kernel-unknown-local",
            )
        declaration = self.declarations[-1 - index]
        # Stored types were valid before later binders were introduced.
        return LocalDeclaration(
            declaration.name,
            cast(Term, shift(declaration.type, index + 1)),
            (
                shift(declaration.value, index + 1)
                if declaration.value is not None
                else None
            ),
        )

    def __len__(self) -> int:
        return len(self.declarations)


EMPTY_CONTEXT = Context()


def shift(term: Term | None, amount: int, cutoff: int = 0) -> Term | None:
    if term is None or amount == 0:
        return term
    if isinstance(term, Local):
        shifted = term.index + amount if term.index >= cutoff else term.index
        if shifted < 0:
            raise KernelError(
                "substitution produced an escaping local", code="kernel-local-underflow"
            )
        return Local(shifted)
    if isinstance(term, Sort | Const):
        return term
    if isinstance(term, Pi):
        return Pi(
            term.name,
            shift(term.domain, amount, cutoff),  # type: ignore[arg-type]
            shift(term.codomain, amount, cutoff + 1),  # type: ignore[arg-type]
        )
    if isinstance(term, Lam):
        return Lam(
            term.name,
            shift(term.domain, amount, cutoff),  # type: ignore[arg-type]
            shift(term.body, amount, cutoff + 1),  # type: ignore[arg-type]
        )
    if isinstance(term, App):
        return App(
            shift(term.function, amount, cutoff),  # type: ignore[arg-type]
            shift(term.argument, amount, cutoff),  # type: ignore[arg-type]
        )
    if isinstance(term, Let):
        return Let(
            term.name,
            shift(term.type, amount, cutoff),  # type: ignore[arg-type]
            shift(term.value, amount, cutoff),  # type: ignore[arg-type]
            shift(term.body, amount, cutoff + 1),  # type: ignore[arg-type]
        )
    arguments = tuple(shift(item, amount, cutoff) for item in term.arguments)
    if isinstance(term, InductiveRef):
        return InductiveRef(term.name, arguments)  # type: ignore[arg-type]
    if isinstance(term, ConstructorRef):
        return ConstructorRef(term.name, arguments)  # type: ignore[arg-type]
    return RecursorRef(term.name, arguments)  # type: ignore[arg-type]


def substitute(term: Term, replacement: Term, index: int = 0) -> Term:
    """Replace local ``index`` and close that binder."""

    def walk(value: Term, depth: int) -> Term:
        if isinstance(value, Local):
            target = index + depth
            if value.index == target:
                return shift(replacement, depth)  # type: ignore[return-value]
            if value.index > target:
                return Local(value.index - 1)
            return value
        if isinstance(value, Sort | Const):
            return value
        if isinstance(value, Pi):
            return Pi(
                value.name, walk(value.domain, depth), walk(value.codomain, depth + 1)
            )
        if isinstance(value, Lam):
            return Lam(
                value.name, walk(value.domain, depth), walk(value.body, depth + 1)
            )
        if isinstance(value, App):
            return App(walk(value.function, depth), walk(value.argument, depth))
        if isinstance(value, Let):
            return Let(
                value.name,
                walk(value.type, depth),
                walk(value.value, depth),
                walk(value.body, depth + 1),
            )
        arguments = tuple(walk(item, depth) for item in value.arguments)
        if isinstance(value, InductiveRef):
            return InductiveRef(value.name, arguments)
        if isinstance(value, ConstructorRef):
            return ConstructorRef(value.name, arguments)
        return RecursorRef(value.name, arguments)

    return walk(term, 0)
