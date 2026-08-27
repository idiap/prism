# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Python-style significant-indentation lexer for Prism logical lines."""

from __future__ import annotations

from prism.language.developer.diagnostics import (
    Diagnostic,
    PrismSyntaxError,
    SourceSpan,
)

from .tokens import Token, TokenKind


def tokenize(source: str, *, path: str | None = None) -> tuple[Token, ...]:
    if not isinstance(source, str):
        raise TypeError("Prism source must be UTF-8 text")
    tokens: list[Token] = []
    indents = [0]
    buffer: list[str] = []
    buffer_positions: list[tuple[int, int]] = []
    buffer_line = 1
    buffer_indent = 0
    delimiters: list[tuple[str, int, int]] = []
    quote: str | None = None
    triple = False
    escaped = False

    lines = source.splitlines()
    for number, physical in enumerate(lines, start=1):
        prefix = physical[: len(physical) - len(physical.lstrip(" \t"))]
        if "\t" in prefix:
            raise _syntax(
                "tabs are not allowed in leading indentation",
                number,
                prefix.index("\t") + 1,
                "layout-leading-tab",
                path,
            )
        stripped = physical[len(prefix) :]
        continuation = bool(buffer)
        if not continuation and (not stripped or stripped.startswith("#")):
            continue
        indent = len(prefix)
        if not continuation:
            if indent % 4:
                raise _syntax(
                    "indentation must use canonical four-space levels",
                    number,
                    1,
                    "layout-indent-width",
                    path,
                )
            if indent > indents[-1]:
                if not _opens_suite(tokens):
                    raise _syntax(
                        "unexpected indentation; the preceding logical line does not open a suite",
                        number,
                        1,
                        "layout-unexpected-indent",
                        path,
                    )
                indents.append(indent)
                tokens.append(
                    Token(TokenKind.INDENT, "", SourceSpan(number, 1), indent)
                )
            elif indent < indents[-1]:
                if indent not in indents:
                    raise _syntax(
                        f"dedent to unopened indentation level {indent}",
                        number,
                        1,
                        "layout-inconsistent-dedent",
                        path,
                    )
                while indent < indents[-1]:
                    indents.pop()
                    tokens.append(
                        Token(TokenKind.DEDENT, "", SourceSpan(number, 1), indent)
                    )
            buffer_line = number
            buffer_indent = indent
        text, quote, triple, escaped = _scan_line(
            stripped,
            delimiters,
            number,
            len(prefix) + 1,
            quote,
            triple,
            escaped,
            path,
        )
        trimmed_start = len(text) - len(text.lstrip())
        trimmed_end = len(text.rstrip())
        part = text[trimmed_start:trimmed_end]
        if part:
            if buffer:
                buffer.append(" ")
                buffer_positions.append((number, len(prefix) + trimmed_start + 1))
            buffer.append(part)
            buffer_positions.extend(
                (number, len(prefix) + index + 1)
                for index in range(trimmed_start, trimmed_end)
            )
        if quote is None and not delimiters:
            logical = "".join(buffer)
            if logical.startswith(("workflow ", "agent ")) and not logical.endswith(
                ":"
            ):
                continue
            if logical:
                tokens.append(
                    Token(
                        TokenKind.LINE,
                        logical,
                        SourceSpan(
                            buffer_line, buffer_indent + 1, number, len(physical) + 1
                        ),
                        buffer_indent,
                        tuple(buffer_positions),
                    )
                )
            buffer.clear()
            buffer_positions.clear()
    if quote is not None:
        raise _syntax(
            "unterminated string literal", buffer_line, 1, "syntax-string", path
        )
    if delimiters:
        opening, line, column = delimiters[-1]
        raise _syntax(
            f"unclosed delimiter `{opening}`",
            line,
            column,
            "syntax-unclosed-delimiter",
            path,
        )
    if buffer:
        raise _syntax(
            "workflow or agent declaration must end in `:`",
            buffer_line,
            buffer_indent + 1,
            "syntax-workflow",
            path,
        )
    while len(indents) > 1:
        indents.pop()
        tokens.append(
            Token(TokenKind.DEDENT, "", SourceSpan(len(lines) + 1, 1), indents[-1])
        )
    tokens.append(Token(TokenKind.EOF, "", SourceSpan(len(lines) + 1, 1)))
    return tuple(tokens)


def _opens_suite(tokens: list[Token]) -> bool:
    return bool(
        tokens and tokens[-1].kind == TokenKind.LINE and tokens[-1].value.endswith(":")
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
            result.append(char)
            if triple and lookahead == quote * 3:
                result.extend(text[index + 1 : index + 3])
                index += 3
                quote = None
                triple = False
                escaped = False
                continue
            if not triple:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            index += 1
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
