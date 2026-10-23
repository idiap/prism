# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Capture-avoiding shifts and substitutions of bound variables."""

from __future__ import annotations

from .diagnostics import KernelError
from .terms import (
    App,
    Const,
    Lam,
    Let,
    Local,
    Pi,
    Sort,
    Term,
)


def shift(term: Term | None, amount: int, cutoff: int = 0) -> Term | None:
    if term is None or amount == 0:
        return term
    if isinstance(term, Local):
        return _shift_local(term, amount, cutoff)
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
    return type(term)(term.name, arguments)  # type: ignore[arg-type]


def substitute(term: Term, replacement: Term, index: int = 0) -> Term:
    """Replace local ``index`` and close that binder."""

    def walk(value: Term, depth: int) -> Term:
        if isinstance(value, Local):
            return _substitute_local(value, replacement, index, depth)
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
        return type(value)(value.name, arguments)  # type: ignore[arg-type]

    return walk(term, 0)


def _shift_local(term: Local, amount: int, cutoff: int) -> Local:
    shifted = term.index + amount if term.index >= cutoff else term.index
    if shifted < 0:
        raise KernelError(
            "substitution produced an escaping local", code="kernel-local-underflow"
        )
    return Local(shifted)


def _substitute_local(value: Local, replacement: Term, index: int, depth: int) -> Term:
    target = index + depth
    if value.index == target:
        return shift(replacement, depth)  # type: ignore[return-value]
    if value.index > target:
        return Local(value.index - 1)
    return value
