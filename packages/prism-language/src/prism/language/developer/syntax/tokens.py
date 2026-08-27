# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Tokens emitted by the indentation-aware logical-line lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from prism.language.developer.diagnostics import SourceSpan


class TokenKind(str, Enum):
    LINE = "LINE"
    INDENT = "INDENT"
    DEDENT = "DEDENT"
    EOF = "EOF"


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    value: str
    span: SourceSpan
    indent: int = 0
    source_positions: tuple[tuple[int, int], ...] = ()

    def positions_for(
        self, start: int = 0, end: int | None = None
    ) -> tuple[tuple[int, int], ...]:
        """Return physical source positions for a slice of the logical token."""

        stop = len(self.value) if end is None else end
        return self.source_positions[start:stop]
