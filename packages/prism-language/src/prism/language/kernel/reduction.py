# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Deterministic beta/delta/iota/zeta weak-head reduction."""

from __future__ import annotations

from dataclasses import dataclass

from .context import Context, substitute
from .diagnostics import KernelResourceError
from .environment import Environment
from .terms import (
    App,
    Const,
    ConstructorRef,
    InductiveRef,
    Lam,
    Let,
    Local,
    RecursorRef,
    Term,
    apps,
    instantiate_universes,
    unfold_apps,
)


@dataclass(slots=True)
class ReductionBudget:
    remaining: int = 20_000

    def spend(self) -> None:
        self.remaining -= 1
        if self.remaining < 0:
            raise KernelResourceError()


def whnf(
    environment: Environment,
    context: Context,
    term: Term,
    *,
    budget: ReductionBudget | None = None,
) -> Term:
    budget = budget or ReductionBudget()
    unfolding: set[str] = set()
    current = term
    while True:
        budget.spend()
        current, reduced = _reduce_head(
            environment, context, current, budget, unfolding
        )
        if not reduced:
            return current


def _reduce_recursor(
    environment: Environment,
    context: Context,
    head: Term,
    arguments: tuple[Term, ...],
    budget: ReductionBudget,
) -> Term | None:
    if not isinstance(head, RecursorRef):
        return None
    declaration = environment.get(head.name)
    spec = declaration.recursor
    if spec is None or len(arguments) <= spec.scrutinee_index:
        return None
    scrutinee = whnf(
        environment, context, arguments[spec.scrutinee_index], budget=budget
    )
    constructor_head, constructor_arguments = unfold_apps(scrutinee)
    if isinstance(constructor_head, ConstructorRef):
        constructor_arguments = (*constructor_head.arguments, *constructor_arguments)
    else:
        return None
    rule = next(
        (item for item in spec.rules if item.constructor == constructor_head.name),
        None,
    )
    if rule is None or len(constructor_arguments) < rule.constructor_arity:
        return None
    branch = arguments[rule.method_index]
    fields = (
        constructor_arguments[-rule.constructor_arity :]
        if rule.constructor_arity
        else ()
    )
    branch_arguments: list[Term] = [
        fields[position]
        for position in (
            rule.field_positions
            if rule.field_positions is not None
            else tuple(range(len(fields)))
        )
    ]
    prefix = arguments[: spec.scrutinee_index]
    for position in rule.recursive_positions:
        branch_arguments.append(apps(RecursorRef(head.name), *prefix, fields[position]))
    result = apps(branch, *branch_arguments)
    return apps(result, *arguments[spec.scrutinee_index + 1 :])


def _unfold_constant(
    environment: Environment, current: Const, unfolding: set[str]
) -> Term | None:
    declaration = environment.get(current.name)
    if (
        declaration.value is not None
        and declaration.transparent
        and declaration.name not in unfolding
    ):
        unfolding.add(declaration.name)
        return instantiate_universes(
            declaration.value,
            declaration.universe_parameters,
            current.universe_arguments,
        )
    return None


def _reduce_head(
    environment: Environment,
    context: Context,
    current: Term,
    budget: ReductionBudget,
    unfolding: set[str],
) -> tuple[Term, bool]:
    if isinstance(current, Local):
        local = context.lookup(current.index)
        if local.value is None:
            return current, False
        current = local.value
        return current, True
    if isinstance(current, Let):
        current = substitute(current.body, current.value)
        return current, True
    if isinstance(current, Const):
        unfolded = _unfold_constant(environment, current, unfolding)
        if unfolded is None:
            return current, False
        current = unfolded
        return current, True
    if (
        isinstance(current, InductiveRef | ConstructorRef | RecursorRef)
        and current.arguments
    ):
        current = apps(type(current)(current.name), *current.arguments)
        return current, True
    if not isinstance(current, App):
        return current, False
    return _reduce_application(environment, context, current, budget)


def _reduce_application(
    environment: Environment, context: Context, current: App, budget: ReductionBudget
) -> tuple[Term, bool]:
    head, arguments = unfold_apps(current)
    reduced_head = whnf(environment, context, head, budget=budget)
    if isinstance(reduced_head, Lam) and arguments:
        return apps(substitute(reduced_head.body, arguments[0]), *arguments[1:]), True
    recursor_reduction = _reduce_recursor(
        environment, context, reduced_head, arguments, budget
    )
    if recursor_reduction is not None:
        return recursor_reduction, True
    rebuilt = apps(reduced_head, *arguments)
    return rebuilt, False
