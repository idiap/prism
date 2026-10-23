# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Source token lookup and conversion to editor coordinates."""

from __future__ import annotations

import io
import tokenize
from typing import Any

from prism.language.developer import SourceSpan
from prism.tooling.protocol import PrismIdeSymbol, PrismIdeSymbolSpan


def protocol_span(span: SourceSpan) -> PrismIdeSymbolSpan:
    return PrismIdeSymbolSpan(
        line=max(span.line - 1, 0),
        character=max(span.column - 1, 0),
        end_line=(span.end_line - 1) if span.end_line else None,
        end_character=(span.end_column - 1) if span.end_column else None,
    )


class NameLocator:
    def __init__(self, source: str) -> None:
        self.tokens: list[tokenize.TokenInfo] = []
        stream = tokenize.generate_tokens(io.StringIO(source).readline)
        try:
            self.tokens.extend(stream)
        except (IndentationError, tokenize.TokenError):
            # Tokens emitted before an incomplete trailing construct remain useful.
            pass

    def find(
        self,
        name: str,
        within: SourceSpan,
        *,
        used: set[tuple[int, int]] | None = None,
        reverse: bool = False,
    ) -> SourceSpan | None:
        excluded = used or set()
        tokens = reversed(self.tokens) if reverse else self.tokens
        for token in tokens:
            if token.type != tokenize.NAME or token.string != name:
                continue
            line, zero_column = token.start
            end_line, zero_end_column = token.end
            column = zero_column + 1
            if (line, column) in excluded or not _position_in_span(
                line, column, within
            ):
                continue
            return SourceSpan(line, column, end_line, zero_end_column + 1)
        return None


def _position_in_span(line: int, column: int, span: SourceSpan) -> bool:
    if line < span.line or (line == span.line and column < span.column):
        return False
    end_line = span.end_line or span.line
    end_column = span.end_column
    if line > end_line:
        return False
    return not (line == end_line and end_column is not None and column >= end_column)


def symbol(name: str, kind: str, span: SourceSpan, **values: Any) -> PrismIdeSymbol:
    return PrismIdeSymbol(
        name=name,
        kind=kind,
        span=protocol_span(span),
        **values,
    )
