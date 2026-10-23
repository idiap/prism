# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workflow composition inspection and pattern matching."""

from __future__ import annotations

from typing import Any, Mapping

from prism.language.core import (
    RecordValue,
)
from prism.language.effects import (
    Field,
    Reference,
)
from prism.language.workflows import (
    Choice,
    NodeOccurrence,
    Parallel,
    Repeat,
    Sequence,
)


def _ir_name(expression: Any) -> str:
    if isinstance(expression, Reference):
        return expression.name
    if isinstance(expression, Field):
        return f"{_ir_name(expression.value)}.{expression.name}"
    return "<component>"


def _composition_terminals(composition: Any) -> tuple[str, ...]:
    if isinstance(composition, NodeOccurrence):
        return (
            composition.alias or _ir_name(composition.component).rsplit(".", 1)[-1],
        )
    if isinstance(composition, Sequence | Repeat):
        return _composition_terminals(composition.children[-1])
    if isinstance(composition, Parallel):
        return tuple(
            terminal
            for child in composition.children
            for terminal in _composition_terminals(child)
        )
    if isinstance(composition, Choice):
        return _composition_terminals(composition.arms[0].children[-1])
    return ()


def _composition_nodes(composition: Any) -> tuple[NodeOccurrence, ...]:
    if isinstance(composition, NodeOccurrence):
        return (composition,)
    if isinstance(composition, Sequence | Parallel | Repeat):
        return tuple(
            node for child in composition.children for node in _composition_nodes(child)
        )
    if isinstance(composition, Choice):
        return (
            composition.router,
            *tuple(
                node
                for arm in composition.arms
                for child in arm.children
                for node in _composition_nodes(child)
            ),
        )
    return ()


def _disposition_matches(value: Any, selector: str) -> bool:
    if isinstance(value, RecordValue):
        if value.type_name == selector:
            return True
        selected = value.fields.get(selector)
        return bool(selected) if selected is not None else False
    if isinstance(value, Mapping):
        return bool(value.get(selector, False))
    return type(value).__name__ == selector or str(value) == selector


def _choice_matches(pattern: str, value: Any) -> bool:
    constructor = pattern.split("(", 1)[0].strip()
    if constructor == "_":
        return True
    if isinstance(value, RecordValue):
        return value.type_name == constructor
    return type(value).__name__ == constructor or str(value) == constructor
