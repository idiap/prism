# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Definitional equality for Prism core terms."""

from __future__ import annotations

from .context import Context
from .diagnostics import KernelError
from .environment import Environment
from .levels import normalize_level
from .reduction import ReductionBudget, whnf
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


def is_def_eq(
    environment: Environment,
    context: Context,
    left: Term,
    right: Term,
    *,
    max_steps: int = 20_000,
) -> bool:
    budget = ReductionBudget(max_steps)
    seen: set[tuple[Term, Term]] = set()

    def equal(a: Term, b: Term, local_context: Context = context) -> bool:
        if a == b:
            return True
        pair = (a, b)
        if pair in seen:
            return True
        seen.add(pair)
        a = whnf(environment, local_context, a, budget=budget)
        b = whnf(environment, local_context, b, budget=budget)
        if a == b:
            return True
        if _proof_irrelevant(environment, local_context, a, b, equal, budget):
            return True
        if type(a) is not type(b):
            return False
        if isinstance(a, Sort) and isinstance(b, Sort):
            if a.level is None or b.level is None:
                return a.level is b.level
            return normalize_level(a.level) == normalize_level(b.level)
        if isinstance(a, Local) and isinstance(b, Local):
            return a.index == b.index
        if isinstance(a, Const) and isinstance(b, Const):
            return a.name == b.name and tuple(
                normalize_level(item) for item in a.universe_arguments
            ) == tuple(normalize_level(item) for item in b.universe_arguments)
        if isinstance(a, Pi) and isinstance(b, Pi):
            return equal(a.domain, b.domain, local_context) and equal(
                a.codomain,
                b.codomain,
                local_context.push(a.name, a.domain),
            )
        if isinstance(a, Lam) and isinstance(b, Lam):
            return equal(a.domain, b.domain, local_context) and equal(
                a.body,
                b.body,
                local_context.push(a.name, a.domain),
            )
        if isinstance(a, App) and isinstance(b, App):
            return equal(a.function, b.function, local_context) and equal(
                a.argument, b.argument, local_context
            )
        if isinstance(a, Let) and isinstance(b, Let):
            return (
                equal(a.type, b.type, local_context)
                and equal(a.value, b.value, local_context)
                and equal(
                    a.body,
                    b.body,
                    local_context.push(a.name, a.type, a.value),
                )
            )
        if isinstance(a, InductiveRef | ConstructorRef | RecursorRef) and isinstance(
            b, InductiveRef | ConstructorRef | RecursorRef
        ):
            return (
                a.name == b.name
                and len(a.arguments) == len(b.arguments)
                and all(
                    equal(x, y, local_context)
                    for x, y in zip(a.arguments, b.arguments, strict=True)
                )
            )
        return False

    return equal(left, right)


def _proof_irrelevant(environment, context, left, right, equal, budget) -> bool:
    """All inhabitants of the same proposition are definitionally equal."""

    from .typing import infer

    try:
        left_type = infer(environment, context, left)
        right_type = infer(environment, context, right)
        left_type_sort = whnf(
            environment, context, infer(environment, context, left_type), budget=budget
        )
        right_type_sort = whnf(
            environment, context, infer(environment, context, right_type), budget=budget
        )
    except KernelError:
        return False
    return (
        isinstance(left_type_sort, Sort)
        and left_type_sort.level is None
        and isinstance(right_type_sort, Sort)
        and right_type_sort.level is None
        and equal(left_type, right_type, context)
    )
