# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Quote-aware top-level text and delimiter scanning."""

from __future__ import annotations


def split_top_level(
    text: str, separator: str = ",", *, keep_empty: bool = False
) -> tuple[str, ...]:
    result: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            quote, escaped = _advance_quote(char, quote, escaped)
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif depth == 0 and text.startswith(separator, index):
            result.append(text[start:index].strip())
            start = index + len(separator)
            index = start
            continue
        index += 1
    result.append(text[start:].strip())
    items = tuple(result)
    return items if keep_empty else tuple(item for item in items if item)


def find_top_level(text: str, needle: str) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    index = 0
    while index <= len(text) - len(needle):
        char = text[index]
        if quote:
            quote, escaped = _advance_quote(char, quote, escaped)
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
        elif depth == 0 and text.startswith(needle, index):
            return index
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        index += 1
    return -1


def matching_delimiter(text: str, opening: int) -> int:
    pairs = {"(": ")", "[": "]", "{": "}"}
    opener = text[opening]
    closer = pairs[opener]
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if quote:
            quote, escaped = _advance_quote(char, quote, escaped)
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"unclosed delimiter `{opener}`")


def _matching_square(text: str, opening: int) -> int:
    return matching_delimiter(text, opening)


def _advance_quote(char: str, quote: str, escaped: bool) -> tuple[str | None, bool]:
    if escaped:
        return quote, False
    if char == "\\":
        return quote, True
    return (None if char == quote else quote), False
