# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Dependencies of imported top-level value bindings."""

from __future__ import annotations

from typing import Any

from prism.language.core.indices import ValueIndex

from ..syntax.ast import (
    NameExpr,
    NodeOccurrence,
    TypeExpr,
)
from ..type_syntax import parse_type


def _binding_value_dependencies(
    expression: Any,
    candidates: set[str],
    *,
    namespace: str | None = None,
) -> tuple[str, ...]:
    """Return top-level values required to evaluate an imported binding."""

    result: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, TypeExpr):
            walk(parse_type(value.text, value.span))
            return
        if _collect_binding_reference(value, candidates, namespace, result):
            return
        if not hasattr(value, "__dataclass_fields__"):
            return
        for name in value.__dataclass_fields__:
            item = getattr(value, name)
            if isinstance(item, tuple):
                for child in item:
                    walk(getattr(child, "value", child))
            elif hasattr(item, "__dataclass_fields__"):
                walk(item)

    walk(expression)
    return tuple(sorted(result))


def _collect_binding_reference(
    value: Any, candidates: set[str], namespace: str | None, result: set[str]
) -> bool:
    if isinstance(value, NodeOccurrence) and value.relation:
        relation_name = value.relation
        if relation_name in candidates:
            result.add(relation_name)
        elif namespace and "." not in relation_name:
            qualified = f"{namespace}.{relation_name}"
            if qualified in candidates:
                result.add(qualified)
    if isinstance(value, NameExpr) or (
        isinstance(value, ValueIndex) and value.kind == "reference"
    ):
        name = value.name if isinstance(value, NameExpr) else value.symbol
        if name in candidates:
            result.add(name)
            return True
        qualified = f"{namespace}.{name}" if namespace and "." not in name else None
        if qualified in candidates:
            result.add(qualified)
            return True
    return False
