# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Collect source definitions and locate their exact identifier spans."""

from __future__ import annotations

import dataclasses
import io
import re
import tokenize
from dataclasses import dataclass
from typing import Any

from prism.language.developer import SourceSpan
from prism.language.developer.syntax import (
    AgentDecl,
    Binding,
    FunctionDecl,
    ImportDecl,
    ModuleImportDecl,
    NodeOccurrence,
    Program,
    ReasoningDecl,
    RelationDecl,
    TheoremDecl,
    TypeDecl,
    WorkflowDecl,
)


@dataclass(frozen=True, slots=True)
class _Definition:
    name: str
    kind: str
    span: SourceSpan
    path: str
    owner: str | None = None
    module: str | None = None
    target_name: str | None = None
    exported: bool = False


def _definitions(program: Program, path: str) -> list[_Definition]:
    collector = _DefinitionCollector(program, path)
    for declaration in program.declarations:
        collector.visit(declaration)
    return collector.result


def _tokens(source: str) -> list[tokenize.TokenInfo]:
    result: list[tokenize.TokenInfo] = []
    try:
        result.extend(tokenize.generate_tokens(io.StringIO(source).readline))
    except (IndentationError, tokenize.TokenError):
        pass
    return result


class _TokenLocator:
    def __init__(self, source: str) -> None:
        self.tokens = _tokens(source)

    def find(
        self,
        name: str,
        within: SourceSpan,
        *,
        used: set[tuple[int, int]] | None = None,
        reverse: bool = False,
    ) -> SourceSpan | None:
        tokens = reversed(self.tokens) if reverse else self.tokens
        for token in tokens:
            if token.type != tokenize.NAME or token.string != name:
                continue
            span = SourceSpan(
                token.start[0], token.start[1] + 1, token.end[0], token.end[1] + 1
            )
            if used and (span.line, span.column) in used:
                continue
            if _source_position_in_span(span.line, span.column, within):
                return span
        return None


def _source_position_in_span(line: int, column: int, span: SourceSpan) -> bool:
    if line < span.line or (line == span.line and column < span.column):
        return False
    end_line = span.end_line or span.line
    end_column = span.end_column
    if line > end_line:
        return False
    return not (line == end_line and end_column is not None and column >= end_column)


class _DefinitionCollector:
    def __init__(self, program: Program, path: str) -> None:
        self.locator = _TokenLocator(program.source)
        self.result: list[_Definition] = []
        self.path = path

    def add(
        self,
        name: str,
        kind: str,
        within: SourceSpan,
        *,
        owner: str | None = None,
        module: str | None = None,
        target_name: str | None = None,
        exported: bool = False,
        reverse: bool = False,
        used: set[tuple[int, int]] | None = None,
    ) -> None:
        span = self.locator.find(name, within, reverse=reverse, used=used)
        if span is None:
            return
        if used is not None:
            used.add((span.line, span.column))
        self.result.append(
            _Definition(
                name, kind, span, self.path, owner, module, target_name, exported
            )
        )

    def visit(self, value: Any, owner: str | None = None) -> None:
        visitors = (
            (ImportDecl, self._visit_import_decl),
            (ModuleImportDecl, self._visit_module_import_decl),
            (TypeDecl, self._visit_type_decl),
            (AgentDecl, self._visit_agent_decl),
            ((WorkflowDecl, ReasoningDecl), self._visit_workflow_decl),
            (RelationDecl, self._visit_relation_decl),
            (TheoremDecl, self._visit_theorem_decl),
            (FunctionDecl, self._visit_function_decl),
            (Binding, self._visit_binding),
            (NodeOccurrence, self._visit_node_occurrence),
        )
        for node_type, visit in visitors:
            if isinstance(value, node_type):
                visit(value, owner)
                return
        if dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                if field.name != "span":
                    self.visit(getattr(value, field.name), owner)
        elif isinstance(value, (tuple, list)):
            for item in value:
                self.visit(item, owner)

    def _visit_import_decl(self, value, owner):
        used: set[tuple[int, int]] = set()
        for imported, alias in value.names:
            local = alias or imported
            self.add(
                local,
                "import",
                value.span,
                module=value.module,
                target_name=imported,
                reverse=True,
                used=used,
            )
        return

    def _visit_module_import_decl(self, value, owner):
        self.add(
            value.alias,
            "module-import",
            value.span,
            module=value.module,
            reverse=True,
        )
        return

    def _visit_type_decl(self, value, owner):
        self.add(value.name, "type", value.span, exported=True)
        for name in value.type_parameters:
            self.add(name, "type-parameter", value.span, owner=value.name)
        for field in value.fields:
            self.add(field.name, "field", field.span, owner=value.name)
        for index, alternative in enumerate(value.alternatives):
            match = re.match(r"([A-Za-z_]\w*)", alternative)
            if match:
                within = (
                    value.alternative_spans[index]
                    if index < len(value.alternative_spans)
                    else value.span
                )
                self.add(
                    match.group(1),
                    "variant",
                    within,
                    owner=value.name,
                    exported=True,
                )
        return

    def _visit_agent_decl(self, value, owner):
        self.add(value.name, "agent", value.span, exported=True)
        for parameter in value.parameters:
            self.add(parameter.name, "port", parameter.span, owner=value.name)
        return

    def _visit_workflow_decl(self, value, owner):
        self.add(
            value.name,
            "reasoning" if isinstance(value, ReasoningDecl) else "workflow",
            value.span,
            exported=True,
        )
        for name in value.type_parameters:
            self.add(name, "type-parameter", value.span, owner=value.name)
        for parameter in value.parameters:
            self.add(parameter.name, "parameter", parameter.span, owner=value.name)
        self.visit(value.composition, value.name)
        return

    def _visit_relation_decl(self, value, owner):
        self.add(value.name, "relation", value.span, exported=True)
        for name in value.type_parameters:
            self.add(name, "type-parameter", value.span, owner=value.name)
        for parameter in value.parameters:
            self.add(parameter.name, "parameter", parameter.span, owner=value.name)
        return

    def _visit_theorem_decl(self, value, owner):
        self.add(value.name, "theorem", value.span, exported=True)
        for parameter in value.parameters:
            self.add(parameter.name, "parameter", parameter.span, owner=value.name)
        for statement in value.body:
            self.visit(statement, value.name)
        return

    def _visit_function_decl(self, value, owner):
        self.add(value.name, "function", value.span, exported=True)
        for name in value.type_parameters:
            self.add(name, "type-parameter", value.span, owner=value.name)
        for parameter in value.parameters:
            self.add(parameter.name, "parameter", parameter.span, owner=value.name)
        for statement in value.body:
            self.visit(statement, value.name)
        return

    def _visit_binding(self, value, owner):
        self.add(value.name, "binding", value.span, owner=owner, exported=owner is None)
        return

    def _visit_node_occurrence(self, value, owner):
        if value.alias:
            self.add(value.alias, "workflow-node", value.span, owner=owner)
        return
