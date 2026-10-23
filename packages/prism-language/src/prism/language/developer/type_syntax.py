# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Parse canonical Prism type syntax into core types."""

from __future__ import annotations

from prism.language.core import (
    CoreType,
)
from prism.language.core.indices import ValueIndex

from .diagnostics import SourceSpan
from .syntax import ast
from .syntax.expressions import parse_expression


def _split_top_level(text: str) -> tuple[str, ...]:
    result = []
    start = 0
    depth = 0
    quote = None
    for index, char in enumerate(text):
        if quote:
            if char == quote and (index == 0 or text[index - 1] != "\\"):
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        result.append(tail)
    return tuple(result)


def _find_top_level(text: str, needle: str) -> int:
    depth = 0
    quote = None
    index = 0
    while index <= len(text) - len(needle):
        char = text[index]
        if quote:
            if char == quote and (index == 0 or text[index - 1] != "\\"):
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif depth == 0 and text.startswith(needle, index):
            return index
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        index += 1
    return -1


def _find_top_level_open(text: str, needle: str) -> int:
    # Unlike _find_top_level, opening delimiters themselves are candidates.
    depth = 0
    quote = None
    for index, char in enumerate(text):
        if quote:
            if char == quote and (index == 0 or text[index - 1] != "\\"):
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == needle and depth == 0:
            return index
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
    return -1


def parse_type(text: str, span: SourceSpan | None = None) -> CoreType:
    """Parse the supported structural type syntax into the typed core."""

    text = text.strip()
    if not text:
        raise ValueError("empty type")
    effects: tuple[str, ...] = ()
    effect_index = _find_top_level(text, "!")
    if effect_index >= 0:
        row = text[effect_index + 1 :].strip()
        if not row.startswith("{") or not row.endswith("}"):
            raise ValueError("malformed effect row")
        effects = tuple(_split_top_level(row[1:-1]))
        text = text[:effect_index].strip()
    arrow = _find_top_level(text, "->")
    if arrow >= 0:
        return _parse_function_type(text, arrow, effects)
    if text.startswith("(") and text.endswith(")"):
        items = _split_top_level(text[1:-1])
        return CoreType("Tuple", tuple(parse_type(item) for item in items))
    # Keep dependent value binders intact even when their value type is generic,
    # for example `value: Generated[Draft]`.
    colon = _find_top_level(text, ":")
    if colon > 0:
        return CoreType(
            "ValueBinder", (parse_type(text[colon + 1 :]),), binder=text[:colon].strip()
        )
    bracket = _find_top_level_open(text, "[")
    if bracket > 0 and text.endswith("]"):
        return CoreType(
            text[:bracket].strip(),
            tuple(
                parse_type(item) for item in _split_top_level(text[bracket + 1 : -1])
            ),
            effects=effects,
        )
    # Proposition applications are kept exact so dependent assurance types do
    # not accidentally apply to a different value.
    if "(" in text and text.endswith(")"):
        return CoreType("Proposition", proposition=parse_index(text, span))
    return CoreType(text)


def _parse_function_type(text: str, arrow: int, effects: tuple[str, ...]) -> CoreType:
    left, right = text[:arrow].strip(), text[arrow + 2 :].strip()
    if left.startswith("(") and left.endswith(")"):
        left = left[1:-1]
    parameters = []
    for item in _split_top_level(left):
        colon = _find_top_level(item, ":")
        if colon >= 0:
            parameters.append((item[:colon].strip(), parse_type(item[colon + 1 :])))
        elif item:
            parameters.append((None, parse_type(item)))
    return CoreType(
        "Function",
        parameters=tuple(parameters),
        result=parse_type(right),
        effects=effects,
    )


def parse_index(text: str, span: SourceSpan | None = None) -> ValueIndex:
    return index_from_expression(parse_expression(text, span or SourceSpan(1)))


def index_from_expression(expression: ast.Expression) -> ValueIndex:
    if isinstance(expression, ast.NameExpr):
        return ValueIndex("reference", expression.name)
    if isinstance(expression, ast.LiteralExpr):
        return ValueIndex("literal", repr(expression.value))
    if isinstance(expression, ast.FieldExpr):
        return ValueIndex(
            "field", expression.field, (index_from_expression(expression.value),)
        )
    if isinstance(expression, ast.IndexExpr):
        return ValueIndex(
            "index",
            "",
            (
                index_from_expression(expression.value),
                index_from_expression(expression.index),
            ),
        )
    if isinstance(expression, ast.UnaryExpr):
        return ValueIndex(
            "unary", expression.operator, (index_from_expression(expression.operand),)
        )
    if isinstance(expression, ast.BinaryExpr):
        return ValueIndex(
            "binary",
            expression.operator,
            (
                index_from_expression(expression.left),
                index_from_expression(expression.right),
            ),
        )
    if isinstance(expression, ast.CallExpr):
        return ValueIndex(
            "apply",
            "",
            (
                index_from_expression(expression.callee),
                *(
                    index_from_expression(argument.value)
                    for argument in expression.arguments
                ),
            ),
            argument_names=tuple(argument.name for argument in expression.arguments),
            type_arguments=tuple(
                parse_type(item.text, item.span) for item in expression.type_arguments
            ),
        )
    raise ValueError(
        f"unsupported expression in proposition index: {type(expression).__name__}"
    )
