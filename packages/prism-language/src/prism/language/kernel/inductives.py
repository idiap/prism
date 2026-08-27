# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Narrow, strictly-positive inductive admission for core calculus v1."""

from __future__ import annotations

from dataclasses import dataclass

from .context import EMPTY_CONTEXT
from .diagnostics import KernelError
from .environment import Declaration, Environment
from .terms import (
    Const,
    InductiveRef,
    Lam,
    Let,
    Pi,
    Term,
    term_children,
    unfold_apps,
)
from .typing import infer


@dataclass(frozen=True, slots=True)
class Constructor:
    name: str
    type: Term


@dataclass(frozen=True, slots=True)
class InductiveDefinition:
    name: str
    type: Term
    constructors: tuple[Constructor, ...]


def admit_inductive(
    environment: Environment, definition: InductiveDefinition
) -> Environment:
    from .declarations import check_declaration

    inferred = infer(environment, EMPTY_CONTEXT, definition.type)
    from .reduction import whnf
    from .terms import Sort

    if not isinstance(whnf(environment, EMPTY_CONTEXT, inferred), Sort):
        raise KernelError(
            f"inductive `{definition.name}` family is not a type",
            code="kernel-expected-sort",
        )
    environment = check_declaration(
        environment,
        Declaration(
            definition.name,
            definition.type,
            kind="inductive",
            transparent=False,
        ),
    )
    family_arity = _pi_arity(definition.type)
    for constructor in definition.constructors:
        _require_strictly_positive(constructor.type, definition.name)
        result = constructor.type
        while isinstance(result, Pi):
            result = result.codomain
        head, arguments = unfold_apps(result)
        if isinstance(head, InductiveRef):
            arguments = (*head.arguments, *arguments)
        if not (
            isinstance(head, InductiveRef | Const) and head.name == definition.name
        ):
            raise KernelError(
                f"constructor `{constructor.name}` does not return `{definition.name}`",
                code="kernel-constructor-result",
            )
        if len(arguments) != family_arity:
            raise KernelError(
                f"constructor `{constructor.name}` returns its family with "
                f"{len(arguments)} arguments, expected {family_arity}",
                code="kernel-constructor-result-arity",
            )
        environment = check_declaration(
            environment,
            Declaration(
                constructor.name,
                constructor.type,
                kind="constructor",
                transparent=False,
                inductive_name=definition.name,
            ),
        )
    return environment


def _pi_arity(term: Term) -> int:
    arity = 0
    while isinstance(term, Pi):
        arity += 1
        term = term.codomain
    return arity


def _require_strictly_positive(term: Term, inductive: str) -> None:
    def occurs(value: Term) -> bool:
        return (
            isinstance(value, InductiveRef | Const) and value.name == inductive
        ) or any(occurs(child) for child in term_children(value))

    def visit(value: Term, positive: bool) -> None:
        if isinstance(value, Pi):
            domain_head, _ = unfold_apps(value.domain)
            direct_recursive_argument = (
                isinstance(domain_head, InductiveRef | Const)
                and domain_head.name == inductive
            )
            if occurs(value.domain) and not direct_recursive_argument:
                raise KernelError(
                    f"negative occurrence of `{inductive}` in constructor domain",
                    code="kernel-negative-inductive",
                )
            visit(value.codomain, positive)
            return
        if isinstance(value, Lam):
            visit(value.domain, positive)
            visit(value.body, positive)
            return
        if isinstance(value, Let):
            visit(value.type, positive)
            visit(value.value, positive)
            visit(value.body, positive)
            return
        for child in term_children(value):
            visit(child, positive)

    visit(term, True)
