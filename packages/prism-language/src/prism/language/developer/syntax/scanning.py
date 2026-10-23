# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Physical-line scanning for strings, comments, and balanced delimiters."""

from __future__ import annotations

from prism.language.developer.diagnostics import (
    Diagnostic,
    PrismSyntaxError,
    SourceSpan,
)


def _scan_line(
    text: str,
    delimiters: list[tuple[str, int, int]],
    line: int,
    start_column: int,
    quote: str | None,
    triple: bool,
    escaped: bool,
    path: str | None,
) -> tuple[str, str | None, bool, bool]:
    pairs = {")": "(", "]": "[", "}": "{"}
    result: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        lookahead = text[index : index + 3]
        if quote is not None:
            index, quote, triple, escaped = _scan_quoted(
                text, index, quote, triple, escaped, result
            )
            continue
        if lookahead in {'"""', "'''"}:
            quote = lookahead[0]
            triple = True
            result.append(lookahead)
            index += 3
            continue
        if char in {'"', "'"}:
            quote = char
            triple = False
            result.append(char)
        elif char == "#":
            break
        elif char in "([{":
            delimiters.append((char, line, start_column + index))
            result.append(char)
        elif char in ")]}":
            if not delimiters or delimiters[-1][0] != pairs[char]:
                raise _syntax(
                    f"unmatched closing delimiter `{char}`",
                    line,
                    start_column + index,
                    "syntax-unmatched-delimiter",
                    path,
                )
            delimiters.pop()
            result.append(char)
        else:
            result.append(char)
        index += 1
    return "".join(result), quote, triple, escaped


def _syntax(
    message: str, line: int, column: int, code: str, path: str | None
) -> PrismSyntaxError:
    return PrismSyntaxError(Diagnostic(message, SourceSpan(line, column), code), path)


def _scan_quoted(text, index, quote, triple, escaped, result):
    char = text[index]
    result.append(char)
    if triple and text[index : index + 3] == quote * 3:
        result.extend(text[index + 1 : index + 3])
        return index + 3, None, False, False
    if not triple:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            quote = None
    return index + 1, quote, triple, escaped
