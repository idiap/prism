# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Collect canonical compiler types from source-spanned syntax nodes."""

from __future__ import annotations

import dataclasses
from typing import Any

from prism.language.core import CoreType, TypedModule
from prism.language.developer import SourceSpan
from prism.language.developer.syntax import (
    AgentDecl,
    BinaryExpr,
    CallExpr,
    ChoiceComposition,
    ExecuteExpr,
    FieldExpr,
    FunctionDecl,
    GuardedExit,
    ImportDecl,
    ListExpr,
    LiteralExpr,
    MapExpr,
    MaterialInferenceExpr,
    ModuleImportDecl,
    NameExpr,
    NodeOccurrence,
    ParallelComposition,
    Program,
    ReasoningDecl,
    RelationDecl,
    RepeatComposition,
    SequenceComposition,
    SolveExpr,
    TheoremDecl,
    ToolDecl,
    TryExpr,
    TupleExpr,
    TypeDecl,
    UnaryExpr,
    WorkflowDecl,
)
from prism.language.developer.syntax import Binding as SurfaceBinding
from prism.tooling.protocol import PrismIdeTypeSpan

from .expressions import (
    expression_type,
    named_type,
    resolved_surface_type,
    surface_expression_name,
)
from .spans import NameLocator, protocol_span

_EXPRESSION_NODES = (
    BinaryExpr,
    CallExpr,
    ExecuteExpr,
    FieldExpr,
    ListExpr,
    LiteralExpr,
    MapExpr,
    MaterialInferenceExpr,
    NameExpr,
    SolveExpr,
    TryExpr,
    TupleExpr,
    UnaryExpr,
)
_CALLABLE_DECLARATIONS = (
    FunctionDecl,
    WorkflowDecl,
    ReasoningDecl,
    RelationDecl,
    TheoremDecl,
)
_COMPOSITIONS = (
    NodeOccurrence,
    SequenceComposition,
    ParallelComposition,
    ChoiceComposition,
    RepeatComposition,
)


def build_type_index(program: Program, checked: TypedModule) -> list[PrismIdeTypeSpan]:
    """Return canonical compiler types for source-spanned syntax nodes."""

    index = _TypeIndex(program.source, checked)
    index.visit(program.declarations)
    return sorted(
        index.result,
        key=lambda item: (
            item.span.line,
            item.span.character,
            item.span.end_line or item.span.line,
            item.span.end_character or item.span.character,
        ),
    )


class _TypeIndex:
    def __init__(self, source: str, checked: TypedModule) -> None:
        self.checked = checked
        self.locator = NameLocator(source)
        self.result: list[PrismIdeTypeSpan] = []
        self.seen: set[tuple[int, int, int | None, int | None, str, str]] = set()

    def _add(
        self, span: SourceSpan, type_text: str, kind: str, name: str | None = None
    ) -> None:
        item = PrismIdeTypeSpan(
            span=protocol_span(span),
            type_text=type_text,
            kind=kind,
            name=name,
        )
        key = (
            item.span.line,
            item.span.character,
            item.span.end_line,
            item.span.end_character,
            item.type_text,
            item.kind,
        )
        if key not in self.seen:
            self.seen.add(key)
            self.result.append(item)

    def _add_named(
        self,
        name: str,
        within: SourceSpan,
        inferred: CoreType | None,
        kind: str,
        *,
        reverse: bool = False,
    ) -> None:
        name_span = self.locator.find(name, within, reverse=reverse)
        if inferred is not None and name_span is not None:
            self._add(name_span, inferred.render(), kind, name)

    def _global(self, name: str, span: SourceSpan, kind: str, *, reverse=False) -> None:
        binding = self.checked.globals.get(name)
        self._add_named(
            name,
            span,
            binding.type if binding is not None else None,
            kind,
            reverse=reverse,
        )

    def visit(self, value: Any, reasoning_name: str | None = None) -> None:
        if isinstance(value, NodeOccurrence) and reasoning_name and value.alias:
            inferred = self.checked.reasoning_outputs.get(reasoning_name, {}).get(
                value.alias
            )
            self._add_named(value.alias, value.span, inferred, "ReasoningOccurrence")

        if not self._visit_declaration(value):
            self._visit_reference(value)

        nested_reasoning = (
            value.name if isinstance(value, ReasoningDecl) else reasoning_name
        )
        if dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                if field.name != "span":
                    self.visit(getattr(value, field.name), nested_reasoning)
        elif isinstance(value, (tuple, list)):
            for item in value:
                self.visit(item, reasoning_name)

    def _visit_declaration(self, value: Any) -> bool:
        if isinstance(value, SurfaceBinding):
            inferred = self.checked.expression_types.get(id(value.value))
            self._add_named(value.name, value.span, inferred, "Binding")
        elif isinstance(value, _CALLABLE_DECLARATIONS):
            self._callable(value)
        elif isinstance(value, AgentDecl):
            self._agent(value)
        elif isinstance(value, ToolDecl):
            self._global(value.name, value.span, "Tool")
        elif isinstance(value, TypeDecl):
            self._record(value)
        elif isinstance(value, ImportDecl):
            self._imports(value)
        elif isinstance(value, ModuleImportDecl):
            self._global(value.alias, value.span, "ModuleImport", reverse=True)
        else:
            return False
        return True

    def _callable(self, value: Any) -> None:
        self._global(value.name, value.span, type(value).__name__)
        contract = self.checked.callable_contracts.get(value.name)
        if contract is None:
            return
        used: set[tuple[int, int]] = set()
        for parameter in contract.parameters:
            parameter_span = self.locator.find(parameter.name, value.span, used=used)
            if parameter_span is not None:
                used.add((parameter_span.line, parameter_span.column))
                self._add(
                    parameter_span, parameter.type.render(), "Parameter", parameter.name
                )

    def _agent(self, value: AgentDecl) -> None:
        self._global(value.name, value.span, "Agent")
        used: set[tuple[int, int]] = set()
        for parameter in value.parameters:
            parameter_span = self.locator.find(parameter.name, value.span, used=used)
            if parameter_span is None:
                continue
            used.add((parameter_span.line, parameter_span.column))
            self._add(
                parameter_span,
                resolved_surface_type(parameter.type, self.checked).render(),
                "Parameter",
                parameter.name,
            )

    def _record(self, value: TypeDecl) -> None:
        self._global(value.name, value.span, "Type")
        record = self.checked.record_contracts.get(value.name)
        if record is None:
            return
        for field in record.fields:
            declaration = next(
                (item for item in value.fields if item.name == field.name), None
            )
            if declaration is not None:
                self._add_named(field.name, declaration.span, field.type, "Field")

    def _imports(self, value: ImportDecl) -> None:
        used: set[tuple[int, int]] = set()
        for imported, alias in value.names:
            local = alias or imported
            binding = self.checked.globals.get(local)
            name_span = self.locator.find(local, value.span, used=used, reverse=True)
            if binding is None or name_span is None:
                continue
            used.add((name_span.line, name_span.column))
            self._add(name_span, binding.type.render(), "Import", local)

    def _visit_reference(self, value: Any) -> None:
        if isinstance(value, _COMPOSITIONS) and value.relation:
            relation_type = self.checked.expression_types.get(id(value)) or named_type(
                value.relation, self.checked
            )
            self._reference(
                value.relation, value.span, relation_type, "RelationReference"
            )
        elif isinstance(value, GuardedExit) and value.target:
            self._reference(
                value.target,
                value.span,
                named_type(value.target, self.checked),
                "ReasoningReference",
            )
        elif isinstance(value, _EXPRESSION_NODES):
            inferred = expression_type(value, self.checked)
            if inferred is not None:
                self._add(
                    value.span,
                    inferred.render(),
                    type(value).__name__,
                    surface_expression_name(value) or None,
                )

    def _reference(
        self, name: str, within: SourceSpan, inferred: CoreType | None, kind: str
    ) -> None:
        name_span = self.locator.find(name.rsplit(".", 1)[-1], within, reverse=True)
        if inferred is not None and name_span is not None:
            self._add(name_span, inferred.render(), kind, name)
