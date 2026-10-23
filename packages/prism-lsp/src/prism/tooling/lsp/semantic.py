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
    collector = _SemanticCollector(program)
    collector.visit(program.declarations)
    return sorted(
        collector.result, key=lambda item: (item.span.line, item.span.character)
    )


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


class _SemanticCollector:
    def __init__(self, program: Program) -> None:
        self.locator = _TokenLocator(program.source)
        self.result: list[PrismIdeSemanticToken] = []
        self.seen: set[tuple[int, int, str]] = set()

    def add(
        self,
        name: str,
        token_type: _TokenType,
        within: SourceSpan,
        *,
        modifiers: tuple[str, ...] = (),
        reverse: bool = False,
    ) -> None:
        span = self.locator.find(name, within, reverse=reverse)
        if span is None:
            return
        key = (span.line, span.column, token_type)
        if key in self.seen:
            return
        self.seen.add(key)
        self.result.append(
            PrismIdeSemanticToken(
                span=_protocol_span(span),
                token_type=token_type,
                modifiers=list(modifiers),
            )
        )

    def declaration(
        self,
        value: Any,
        keyword: str,
        name_type: _TokenType,
        *,
        owner: str | None = None,
    ) -> None:
        self.add(keyword, "keyword", value.span)
        self.add(value.name, name_type, value.span, modifiers=("declaration",))
        for parameter in getattr(value, "parameters", ()):
            self.add(
                parameter.name,
                "parameter",
                parameter.span,
                modifiers=("declaration",),
            )
        for type_parameter in getattr(value, "type_parameters", ()):
            self.add(type_parameter, "type", value.span, modifiers=("declaration",))

    def visit(self, value: Any, owner: str | None = None) -> None:
        if isinstance(value, TypeDecl):
            self._classify_type(value)
            return
        self._classify(value)

        if dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                if field.name != "span":
                    self.visit(
                        getattr(value, field.name), getattr(value, "name", owner)
                    )
        elif isinstance(value, (tuple, list)):
            for item in value:
                self.visit(item, owner)

    def _classify_type(self, value) -> None:
        self.declaration(value, "type", "type")
        if value.metadata is not None:
            self.add("with", "keyword", value.span)
            self.add("taxonomy", "property", value.metadata.span)
            for facet, _ in value.metadata.facets:
                self.add(facet, "property", value.metadata.span)
        for field in value.fields:
            self.add(field.name, "property", field.span, modifiers=("declaration",))

    def _classify(self, value: Any) -> None:
        declarations: tuple[tuple[type, str, _TokenType], ...] = (
            (FunctionDecl, "def", "function"),
            (AgentDecl, "agent", "type"),
            (WorkflowDecl, "workflow", "function"),
            (ReasoningDecl, "reasoning", "function"),
            (RelationDecl, "relation", "function"),
            (TheoremDecl, "theorem", "function"),
        )
        for node_type, keyword, name_type in declarations:
            if isinstance(value, node_type):
                self.declaration(value, keyword, name_type)
                return
        classifiers = (
            (ImportDecl, self._classify_import_decl),
            (ModuleImportDecl, self._classify_module_import_decl),
            (Binding, self._classify_binding),
            (NodeOccurrence, self._classify_node_occurrence),
            (
                (SequenceComposition, ParallelComposition),
                self._classify_sequence_composition,
            ),
            (ChoiceComposition, self._classify_choice_composition),
            (RepeatComposition, self._classify_repeat_composition),
            (GuardedExit, self._classify_guarded_exit),
        )
        for node_type, classify in classifiers:
            if isinstance(value, node_type):
                classify(value)
                return

    def _classify_import_decl(self, value) -> None:
        self.add("from", "keyword", value.span)
        self.add("import", "keyword", value.span)

    def _classify_module_import_decl(self, value) -> None:
        self.add("import", "keyword", value.span)

    def _classify_binding(self, value) -> None:
        self.add(value.name, "variable", value.span, modifiers=("declaration",))

    def _classify_node_occurrence(self, value) -> None:
        if value.constraints:
            self.add("with", "keyword", value.span)
            for constraint in value.constraints:
                self.add(constraint.subject, "property", constraint.span)
                self.add(constraint.dimension, "property", constraint.span)
        if value.alias:
            self.add(value.alias, "label", value.span, modifiers=("declaration",))
        if value.relation:
            self.add("by", "keyword", value.span, reverse=True)
            self.add(
                value.relation.rsplit(".", 1)[-1],
                "function",
                value.span,
                reverse=True,
            )

    def _classify_sequence_composition(self, value) -> None:
        self.add(
            "sequence" if isinstance(value, SequenceComposition) else "parallel",
            "keyword",
            value.span,
        )
        if value.relation:
            self.add("by", "keyword", value.span, reverse=True)
            self.add(
                value.relation.rsplit(".", 1)[-1],
                "function",
                value.span,
                reverse=True,
            )

    def _classify_choice_composition(self, value) -> None:
        self.add("choice", "keyword", value.span)
        if value.relation:
            self.add("by", "keyword", value.span, reverse=True)
            self.add(
                value.relation.rsplit(".", 1)[-1],
                "function",
                value.span,
                reverse=True,
            )

    def _classify_repeat_composition(self, value) -> None:
        self.add("repeat", "keyword", value.span)
        if value.relation:
            self.add("by", "keyword", value.span, reverse=True)
            self.add(
                value.relation.rsplit(".", 1)[-1],
                "function",
                value.span,
                reverse=True,
            )

    def _classify_guarded_exit(self, value) -> None:
        self.add("on", "keyword", value.span)
        self.add(value.occurrence, "label", value.span)
        self.add(value.selector, "property", value.span)
        self.add(value.action, "keyword", value.span)
        if value.target:
            self.add(
                value.target.rsplit(".", 1)[-1],
                "function",
                value.span,
                reverse=True,
            )
