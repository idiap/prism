# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Semantic tokens derived from the canonical Prism AST."""

from __future__ import annotations

import dataclasses
import io
import tokenize
from typing import Any, Literal

from prism.language.developer import SourceSpan
from prism.language.developer.syntax import (
    AgentDecl,
    Binding,
    ChoiceComposition,
    FunctionDecl,
    GuardedExit,
    ImportDecl,
    ModuleImportDecl,
    NodeOccurrence,
    ParallelComposition,
    Program,
    ReasoningDecl,
    RelationDecl,
    RepeatComposition,
    SequenceComposition,
    TheoremDecl,
    TypeDecl,
    WorkflowDecl,
)
from prism.tooling.protocol import PrismIdeSemanticToken, PrismIdeSymbolSpan

_TokenType = Literal[
    "keyword",
    "function",
    "type",
    "parameter",
    "variable",
    "property",
    "label",
    "operator",
]


def build_semantic_index(program: Program) -> list[PrismIdeSemanticToken]:
    """Classify syntax from AST nodes so editor clients never parse Prism."""

    locator = _TokenLocator(program.source)
    result: list[PrismIdeSemanticToken] = []
    seen: set[tuple[int, int, str]] = set()

    def add(
        name: str,
        token_type: _TokenType,
        within: SourceSpan,
        *,
        modifiers: tuple[str, ...] = (),
        reverse: bool = False,
    ) -> None:
        span = locator.find(name, within, reverse=reverse)
        if span is None:
            return
        key = (span.line, span.column, token_type)
        if key in seen:
            return
        seen.add(key)
        result.append(
            PrismIdeSemanticToken(
                span=_protocol_span(span),
                token_type=token_type,
                modifiers=list(modifiers),
            )
        )

    def declaration(
        value: Any,
        keyword: str,
        name_type: _TokenType,
        *,
        owner: str | None = None,
    ) -> None:
        add(keyword, "keyword", value.span)
        add(value.name, name_type, value.span, modifiers=("declaration",))
        for parameter in getattr(value, "parameters", ()):
            add(
                parameter.name,
                "parameter",
                parameter.span,
                modifiers=("declaration",),
            )
        for type_parameter in getattr(value, "type_parameters", ()):
            add(type_parameter, "type", value.span, modifiers=("declaration",))

    def visit(value: Any, owner: str | None = None) -> None:
        if isinstance(value, TypeDecl):
            declaration(value, "type", "type")
            for field in value.fields:
                add(field.name, "property", field.span, modifiers=("declaration",))
            return
        if isinstance(value, FunctionDecl):
            declaration(value, "def", "function")
        elif isinstance(value, AgentDecl):
            declaration(value, "agent", "type")
        elif isinstance(value, WorkflowDecl):
            declaration(value, "workflow", "function")
        elif isinstance(value, ReasoningDecl):
            declaration(value, "reasoning", "function")
        elif isinstance(value, RelationDecl):
            declaration(value, "relation", "function")
        elif isinstance(value, TheoremDecl):
            declaration(value, "theorem", "function")
        elif isinstance(value, ImportDecl):
            add("from", "keyword", value.span)
            add("import", "keyword", value.span)
        elif isinstance(value, ModuleImportDecl):
            add("import", "keyword", value.span)
        elif isinstance(value, Binding):
            add(value.name, "variable", value.span, modifiers=("declaration",))
        elif isinstance(value, NodeOccurrence):
            if value.alias:
                add(value.alias, "label", value.span, modifiers=("declaration",))
            if value.relation:
                add("by", "keyword", value.span, reverse=True)
                add(
                    value.relation.rsplit(".", 1)[-1],
                    "function",
                    value.span,
                    reverse=True,
                )
        elif isinstance(value, (SequenceComposition, ParallelComposition)):
            add(
                "sequence" if isinstance(value, SequenceComposition) else "parallel",
                "keyword",
                value.span,
            )
            if value.relation:
                add("by", "keyword", value.span, reverse=True)
                add(
                    value.relation.rsplit(".", 1)[-1],
                    "function",
                    value.span,
                    reverse=True,
                )
        elif isinstance(value, ChoiceComposition):
            add("choice", "keyword", value.span)
            if value.relation:
                add("by", "keyword", value.span, reverse=True)
                add(
                    value.relation.rsplit(".", 1)[-1],
                    "function",
                    value.span,
                    reverse=True,
                )
        elif isinstance(value, RepeatComposition):
            add("repeat", "keyword", value.span)
            if value.relation:
                add("by", "keyword", value.span, reverse=True)
                add(
                    value.relation.rsplit(".", 1)[-1],
                    "function",
                    value.span,
                    reverse=True,
                )
        elif isinstance(value, GuardedExit):
            add("on", "keyword", value.span)
            add(value.occurrence, "label", value.span)
            add(value.selector, "property", value.span)
            add(value.action, "keyword", value.span)
            if value.target:
                add(
                    value.target.rsplit(".", 1)[-1],
                    "function",
                    value.span,
                    reverse=True,
                )

        if dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                if field.name != "span":
                    visit(getattr(value, field.name), getattr(value, "name", owner))
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item, owner)

    visit(program.declarations)
    return sorted(result, key=lambda item: (item.span.line, item.span.character))


class _TokenLocator:
    def __init__(self, source: str) -> None:
        self.tokens: list[tokenize.TokenInfo] = []
        try:
            self.tokens.extend(tokenize.generate_tokens(io.StringIO(source).readline))
        except (IndentationError, tokenize.TokenError):
            pass

    def find(
        self, name: str, within: SourceSpan, *, reverse: bool = False
    ) -> SourceSpan | None:
        tokens = reversed(self.tokens) if reverse else self.tokens
        for token in tokens:
            if token.type != tokenize.NAME or token.string != name:
                continue
            line, column = token.start[0], token.start[1] + 1
            if not _position_in_span(line, column, within):
                continue
            return SourceSpan(line, column, token.end[0], token.end[1] + 1)
        return None


def _position_in_span(line: int, column: int, span: SourceSpan) -> bool:
    if line < span.line or (line == span.line and column < span.column):
        return False
    end_line = span.end_line or span.line
    if line > end_line:
        return False
    return not (
        line == end_line and span.end_column is not None and column >= span.end_column
    )


def _protocol_span(span: SourceSpan) -> PrismIdeSymbolSpan:
    return PrismIdeSymbolSpan(
        line=span.line - 1,
        character=span.column - 1,
        end_line=(span.end_line - 1) if span.end_line else span.line - 1,
        end_character=(span.end_column - 1) if span.end_column else span.column,
    )
