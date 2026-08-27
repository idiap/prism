# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Immutable terms for the single native Prism proof language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TypeAlias

from .levels import ZERO, Level, level_variables, substitute_level


@dataclass(frozen=True, slots=True)
class Sort:
    """``Sort(None)`` is Prop; ``Sort(level)`` is Type level."""

    level: Level | None


@dataclass(frozen=True, slots=True)
class Local:
    index: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("de Bruijn indices cannot be negative")


@dataclass(frozen=True, slots=True)
class Const:
    name: str
    universe_arguments: tuple[Level, ...] = ()


@dataclass(frozen=True, slots=True)
class Pi:
    name: str
    domain: "Term"
    codomain: "Term"


@dataclass(frozen=True, slots=True)
class Lam:
    name: str
    domain: "Term"
    body: "Term"


@dataclass(frozen=True, slots=True)
class App:
    function: "Term"
    argument: "Term"


@dataclass(frozen=True, slots=True)
class Let:
    name: str
    type: "Term"
    value: "Term"
    body: "Term"


@dataclass(frozen=True, slots=True)
class InductiveRef:
    name: str
    arguments: tuple["Term", ...] = ()


@dataclass(frozen=True, slots=True)
class ConstructorRef:
    name: str
    arguments: tuple["Term", ...] = ()


@dataclass(frozen=True, slots=True)
class RecursorRef:
    name: str
    arguments: tuple["Term", ...] = ()


Term: TypeAlias = (
    Sort
    | Local
    | Const
    | Pi
    | Lam
    | App
    | Let
    | InductiveRef
    | ConstructorRef
    | RecursorRef
)

PROP = Sort(None)
TYPE = Sort(ZERO)


def apps(function: Term, *arguments: Term) -> Term:
    result = function
    for argument in arguments:
        result = App(result, argument)
    return result


def unfold_apps(term: Term) -> tuple[Term, tuple[Term, ...]]:
    arguments: list[Term] = []
    while isinstance(term, App):
        arguments.append(term.argument)
        term = term.function
    return term, tuple(reversed(arguments))


def term_children(term: Term) -> tuple[Term, ...]:
    if isinstance(term, Sort | Local | Const):
        return ()
    if isinstance(term, Pi | Lam):
        return (term.domain, term.codomain if isinstance(term, Pi) else term.body)
    if isinstance(term, App):
        return (term.function, term.argument)
    if isinstance(term, Let):
        return (term.type, term.value, term.body)
    return term.arguments


def contains_local(term: Term, index: int, *, depth: int = 0) -> bool:
    if isinstance(term, Local):
        return term.index == index + depth
    if isinstance(term, Pi | Lam):
        second = term.codomain if isinstance(term, Pi) else term.body
        return contains_local(term.domain, index, depth=depth) or contains_local(
            second, index, depth=depth + 1
        )
    if isinstance(term, Let):
        return (
            contains_local(term.type, index, depth=depth)
            or contains_local(term.value, index, depth=depth)
            or contains_local(term.body, index, depth=depth + 1)
        )
    return any(
        contains_local(child, index, depth=depth) for child in term_children(term)
    )


def constants(term: Term) -> frozenset[str]:
    found: set[str] = set()

    def visit(value: Term) -> None:
        if isinstance(value, Const | InductiveRef | ConstructorRef | RecursorRef):
            found.add(value.name)
        for child in term_children(value):
            visit(child)

    visit(term)
    return frozenset(found)


def universe_variables(term: Term) -> frozenset[str]:
    found: set[str] = set()

    def visit(value: Term) -> None:
        if isinstance(value, Sort) and value.level is not None:
            found.update(level_variables(value.level))
        elif isinstance(value, Const):
            for argument in value.universe_arguments:
                found.update(level_variables(argument))
        for child in term_children(value):
            visit(child)

    visit(term)
    return frozenset(found)


def instantiate_universes(
    term: Term, parameters: tuple[str, ...], arguments: tuple[Level, ...]
) -> Term:
    if len(parameters) != len(arguments):
        raise ValueError("universe parameter and argument counts differ")
    substitutions = dict(zip(parameters, arguments, strict=True))

    def visit(value: Term) -> Term:
        if isinstance(value, Sort):
            return Sort(
                None
                if value.level is None
                else substitute_level(value.level, substitutions)
            )
        if isinstance(value, Local):
            return value
        if isinstance(value, Const):
            return Const(
                value.name,
                tuple(
                    substitute_level(argument, substitutions)
                    for argument in value.universe_arguments
                ),
            )
        if isinstance(value, Pi):
            return Pi(value.name, visit(value.domain), visit(value.codomain))
        if isinstance(value, Lam):
            return Lam(value.name, visit(value.domain), visit(value.body))
        if isinstance(value, App):
            return App(visit(value.function), visit(value.argument))
        if isinstance(value, Let):
            return Let(
                value.name,
                visit(value.type),
                visit(value.value),
                visit(value.body),
            )
        arguments_ = tuple(visit(argument) for argument in value.arguments)
        if isinstance(value, InductiveRef):
            return InductiveRef(value.name, arguments_)
        if isinstance(value, ConstructorRef):
            return ConstructorRef(value.name, arguments_)
        return RecursorRef(value.name, arguments_)

    return visit(term)


def pretty(term: Term, names: Iterable[str] = ()) -> str:
    context = tuple(names)
    if isinstance(term, Sort):
        return "Prop" if term.level is None else f"Type {term.level!r}"
    if isinstance(term, Local):
        return (
            context[-1 - term.index] if term.index < len(context) else f"#{term.index}"
        )
    if isinstance(term, Const):
        return term.name
    if isinstance(term, Pi):
        return f"(forall {term.name}: {pretty(term.domain, context)}, {pretty(term.codomain, (*context, term.name))})"
    if isinstance(term, Lam):
        return f"(fun {term.name}: {pretty(term.domain, context)} => {pretty(term.body, (*context, term.name))})"
    if isinstance(term, App):
        head, arguments = unfold_apps(term)
        return f"{pretty(head, context)}({', '.join(pretty(item, context) for item in arguments)})"
    if isinstance(term, Let):
        return (
            f"(let {term.name}: {pretty(term.type, context)} := "
            f"{pretty(term.value, context)}; {pretty(term.body, (*context, term.name))})"
        )
    rendered = term.name
    if term.arguments:
        rendered += f"({', '.join(pretty(item, context) for item in term.arguments)})"
    return rendered
