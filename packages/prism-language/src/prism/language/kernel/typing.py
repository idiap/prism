# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""The native kernel judgment ``Gamma |- term : type``."""

from __future__ import annotations

from .context import EMPTY_CONTEXT, Context, substitute
from .diagnostics import KernelError
from .environment import CheckedTerm, Environment
from .equality import is_def_eq
from .levels import LevelSucc, level_leq, level_max
from .reduction import whnf
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
    instantiate_universes,
)


def infer(environment: Environment, context: Context, term: Term) -> Term:
    if isinstance(term, Sort):
        return Sort(LevelSucc(term.level)) if term.level is not None else Sort(_zero())
    if isinstance(term, Local):
        return context.lookup(term.index).type
    if isinstance(term, Const):
        declaration = environment.get(term.name)
        if len(term.universe_arguments) != len(declaration.universe_parameters):
            raise KernelError(
                f"constant `{term.name}` expects {len(declaration.universe_parameters)} "
                f"universe arguments, got {len(term.universe_arguments)}",
                code="kernel-universe-arity",
            )
        return instantiate_universes(
            declaration.type,
            declaration.universe_parameters,
            term.universe_arguments,
        )
    if isinstance(term, InductiveRef | ConstructorRef | RecursorRef):
        declaration = environment.get(term.name)
        expected_kind = {
            InductiveRef: "inductive",
            ConstructorRef: "constructor",
            RecursorRef: "recursor",
        }[type(term)]
        if declaration.kind != expected_kind:
            raise KernelError(
                f"`{term.name}` is a {declaration.kind}, not a {expected_kind}",
                code="kernel-reference-kind",
            )
        if declaration.universe_parameters:
            raise KernelError(
                f"{expected_kind} `{term.name}` cannot be referenced without universe arguments",
                code="kernel-universe-arity",
            )
        result = declaration.type
        for argument in term.arguments:
            result = _infer_application(environment, context, result, argument)
        return result
    if isinstance(term, Pi):
        domain_sort = _require_sort(environment, context, term.domain)
        codomain_sort = _require_sort(
            environment, context.push(term.name, term.domain), term.codomain
        )
        if codomain_sort.level is None:
            return codomain_sort  # impredicative Prop
        domain_level = domain_sort.level
        if domain_level is None:
            return codomain_sort
        return Sort(level_max(domain_level, codomain_sort.level))
    if isinstance(term, Lam):
        _require_sort(environment, context, term.domain)
        body_type = infer(environment, context.push(term.name, term.domain), term.body)
        return Pi(term.name, term.domain, body_type)
    if isinstance(term, App):
        return _infer_application(
            environment,
            context,
            infer(environment, context, term.function),
            term.argument,
        )
    if isinstance(term, Let):
        _require_sort(environment, context, term.type)
        check(environment, context, term.value, term.type)
        body_type = infer(
            environment,
            context.push(term.name, term.type, term.value),
            term.body,
        )
        return substitute(body_type, term.value)
    raise KernelError(
        f"unsupported or unresolved kernel term `{type(term).__name__}`",
        code="kernel-unsupported-term",
    )


def check(
    environment: Environment,
    context: Context,
    term: Term,
    expected_type: Term,
) -> CheckedTerm:
    _require_sort(environment, context, expected_type)
    actual = infer(environment, context, term)
    if not _type_compatible(environment, context, actual, expected_type):
        from .terms import pretty

        raise KernelError(
            f"term has type `{pretty(actual)}`, expected `{pretty(expected_type)}`",
            code="kernel-type-mismatch",
        )
    from .serialization import term_hash

    axioms = _axiom_dependencies(environment, term)
    return CheckedTerm(
        term,
        expected_type,
        environment.hash,
        term_hash(term),
        term_hash(expected_type),
        axioms,
    )


def check_closed(
    environment: Environment, term: Term, expected_type: Term
) -> CheckedTerm:
    return check(environment, EMPTY_CONTEXT, term, expected_type)


def _infer_application(
    environment: Environment, context: Context, function_type: Term, argument: Term
) -> Term:
    function_type = whnf(environment, context, function_type)
    if not isinstance(function_type, Pi):
        from .terms import pretty

        raise KernelError(
            f"application target has non-function type `{pretty(function_type)}`",
            code="kernel-invalid-application",
        )
    check(environment, context, argument, function_type.domain)
    return substitute(function_type.codomain, argument)


def _require_sort(environment: Environment, context: Context, term: Term) -> Sort:
    inferred = whnf(environment, context, infer(environment, context, term))
    if not isinstance(inferred, Sort):
        from .terms import pretty

        raise KernelError(
            f"expected a type, got term of type `{pretty(inferred)}`",
            code="kernel-expected-sort",
        )
    return inferred


def _type_compatible(
    environment: Environment, context: Context, actual: Term, expected: Term
) -> bool:
    if is_def_eq(environment, context, actual, expected):
        return True
    actual_whnf = whnf(environment, context, actual)
    expected_whnf = whnf(environment, context, expected)
    return (
        isinstance(actual_whnf, Sort)
        and isinstance(expected_whnf, Sort)
        and actual_whnf.level is not None
        and expected_whnf.level is not None
        and level_leq(actual_whnf.level, expected_whnf.level)
    )


def _axiom_dependencies(environment: Environment, term: Term) -> frozenset[str]:
    from .terms import constants

    dependencies: set[str] = set()
    pending = list(constants(term))
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        declaration = environment.get(name)
        if declaration.kind == "axiom":
            dependencies.add(name)
        dependencies.update(declaration.axiom_dependencies)
    return frozenset(dependencies)


def _zero():
    from .levels import ZERO

    return ZERO
