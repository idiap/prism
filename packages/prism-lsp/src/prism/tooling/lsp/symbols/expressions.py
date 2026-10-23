# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Expression names and canonical type resolution for editor indexes."""

from __future__ import annotations

from typing import Any

from prism.language.core import CoreType, TypedModule
from prism.language.developer import parse_type
from prism.language.developer.syntax import FieldExpr, NameExpr


def surface_expression_name(expression: Any) -> str:
    if isinstance(expression, NameExpr):
        return expression.name
    if isinstance(expression, FieldExpr):
        owner = surface_expression_name(expression.value)
        return f"{owner}.{expression.field}" if owner else expression.field
    return ""


def resolved_surface_type(type_expression, checked: TypedModule) -> CoreType:
    parsed = parse_type(type_expression.text, type_expression.span)
    return checked.aliases.get(parsed.name, parsed) if not parsed.arguments else parsed


def expression_type(expression: Any, checked: TypedModule) -> CoreType | None:
    inferred = checked.expression_types.get(id(expression))
    if inferred is not None:
        return inferred
    name = surface_expression_name(expression)
    contract = checked.callable_contracts.get(name)
    if contract is not None:
        return contract.type
    record = checked.record_contracts.get(name)
    if record is not None:
        return CoreType(
            "Function",
            parameters=tuple((field.name, field.type) for field in record.fields),
            result=CoreType(name),
        )
    binding = checked.globals.get(name)
    return binding.type if binding is not None else None


def named_type(name: str, checked: TypedModule) -> CoreType | None:
    contract = checked.callable_contracts.get(name)
    if contract is not None:
        return contract.type
    binding = checked.globals.get(name)
    return binding.type if binding is not None else None
