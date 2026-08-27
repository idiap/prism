# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Parse canonical Prism type syntax into core types."""

from __future__ import annotations

from prism.language.core import (
    CoreType,
)

from .diagnostics import SourceSpan


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
    if text.startswith("(") and text.endswith(")"):
        items = _split_top_level(text[1:-1])
        return CoreType("Tuple", tuple(parse_type(item) for item in items))
    # Keep dependent value binders intact even when their value type is generic,
    # for example `value: Generated[Draft]`.
    if _find_top_level(text, ":") > 0:
        return CoreType(text)
    bracket = _find_top_level_open(text, "[")
    if bracket > 0 and text.endswith("]"):
        return CoreType(
            text[:bracket].strip(),
            tuple(
                parse_type(item) for item in _split_top_level(text[bracket + 1 : -1])
            ),
        )
    # Proposition applications are kept exact so dependent assurance types do
    # not accidentally apply to a different value.
    if "(" in text and text.endswith(")"):
        return CoreType(text)
    return CoreType(text)
