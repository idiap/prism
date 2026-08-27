# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Canonical-AST-backed symbol index for Prism documents."""

from __future__ import annotations

import dataclasses
import io
import tokenize
from pathlib import Path
from typing import Any, Mapping

from prism.language.core import Binding, CallableContract, CoreType, TypedModule
from prism.language.developer import SourceSpan, parse_type
from prism.language.developer import api as developer_api
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
from prism.language.developer.syntax import (
    Binding as SurfaceBinding,
)
from prism.tooling.protocol import (
    PrismIdeSymbol,
    PrismIdeSymbolSpan,
    PrismIdeTypeSpan,
)

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


def build_symbol_index(
    program: Program,
    globals_scope: Mapping[str, Binding],
    *,
    callable_contracts: Mapping[str, CallableContract],
    project_root: Path,
) -> list[PrismIdeSymbol]:
    symbols: list[PrismIdeSymbol] = []
    for declaration in program.declarations:
        symbols.extend(_declaration_symbols(declaration, globals_scope))
    symbols.extend(_intrinsic_symbols(callable_contracts))
    return symbols


def _intrinsic_symbols(
    callable_contracts: Mapping[str, CallableContract],
) -> list[PrismIdeSymbol]:
    """Expose compiler intrinsics as navigable definitions for editor clients."""

    definition_path = Path(developer_api.__file__).resolve()
    lines = definition_path.read_text(encoding="utf-8").splitlines()
    result: list[PrismIdeSymbol] = []
    for name, contract in callable_contracts.items():
        if contract.kind != "intrinsic":
            continue
        needle = f'"{name}": ('
        location = next(
            (
                (line, text.index(needle) + 1)
                for line, text in enumerate(lines)
                if needle in text
            ),
            None,
        )
        if location is None:
            continue
        line, character = location
        result.append(
            PrismIdeSymbol(
                name=name,
                kind="Intrinsic",
                span=PrismIdeSymbolSpan(
                    line=line,
                    character=character,
                    end_line=line,
                    end_character=character + len(name),
                ),
                detail=contract.type.render(),
                definition_path=str(definition_path),
                source_ref="compiler-intrinsic",
            )
        )
    return result


def build_type_index(program: Program, checked: TypedModule) -> list[PrismIdeTypeSpan]:
    """Return canonical compiler types for source-spanned syntax nodes."""

    locator = _NameLocator(program.source)
    result: list[PrismIdeTypeSpan] = []
    seen: set[tuple[int, int, int | None, int | None, str, str]] = set()

    def add(span, type_text: str, kind: str, name: str | None = None) -> None:
        item = PrismIdeTypeSpan(
            span=_protocol_span(span),
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
        if key not in seen:
            seen.add(key)
            result.append(item)

    def expression_type(expression) -> Any:
        inferred = checked.expression_types.get(id(expression))
        if inferred is not None:
            return inferred
        name = _surface_expression_name(expression)
        contract = checked.callable_contracts.get(name)
        if contract is not None:
            return contract.type
        record = checked.record_contracts.get(name)
        if record is not None:
            return CoreType(
                "Function",
                parameters=tuple((field.name, field.type) for field in record.fields),
                result=CoreType(name),
            )
        binding = checked.globals.get(name)
        return binding.type if binding is not None else None

    def named_type(name: str) -> Any:
        contract = checked.callable_contracts.get(name)
        if contract is not None:
            return contract.type
        binding = checked.globals.get(name)
        return binding.type if binding is not None else None

    def visit(value: Any, reasoning_name: str | None = None) -> None:
        if isinstance(value, NodeOccurrence) and reasoning_name and value.alias:
            inferred = checked.reasoning_outputs.get(reasoning_name, {}).get(
                value.alias
            )
            name_span = locator.find(value.alias, value.span)
            if inferred is not None and name_span is not None:
                add(
                    name_span,
                    inferred.render(),
                    "ReasoningOccurrence",
                    value.alias,
                )

        if isinstance(value, SurfaceBinding):
            inferred = checked.expression_types.get(id(value.value))
            name_span = locator.find(value.name, value.span)
            if inferred is not None and name_span is not None:
                add(name_span, inferred.render(), "Binding", value.name)
        elif isinstance(
            value,
            FunctionDecl | WorkflowDecl | ReasoningDecl | RelationDecl | TheoremDecl,
        ):
            binding = checked.globals.get(value.name)
            name_span = locator.find(value.name, value.span)
            if binding is not None and name_span is not None:
                add(name_span, binding.type.render(), type(value).__name__, value.name)
            contract = checked.callable_contracts.get(value.name)
            if contract is not None:
                used: set[tuple[int, int]] = set()
                for parameter in contract.parameters:
                    parameter_span = locator.find(parameter.name, value.span, used=used)
                    if parameter_span is not None:
                        used.add((parameter_span.line, parameter_span.column))
                        add(
                            parameter_span,
                            parameter.type.render(),
                            "Parameter",
                            parameter.name,
                        )
        elif isinstance(value, AgentDecl):
            binding = checked.globals.get(value.name)
            name_span = locator.find(value.name, value.span)
            if binding is not None and name_span is not None:
                add(name_span, binding.type.render(), "Agent", value.name)
            used: set[tuple[int, int]] = set()
            for parameter in value.parameters:
                parameter_span = locator.find(parameter.name, value.span, used=used)
                if parameter_span is None:
                    continue
                used.add((parameter_span.line, parameter_span.column))
                add(
                    parameter_span,
                    _resolved_surface_type(parameter.type, checked).render(),
                    "Parameter",
                    parameter.name,
                )
        elif isinstance(value, ToolDecl):
            binding = checked.globals.get(value.name)
            name_span = locator.find(value.name, value.span)
            if binding is not None and name_span is not None:
                add(name_span, binding.type.render(), "Tool", value.name)
        elif isinstance(value, TypeDecl):
            binding = checked.globals.get(value.name)
            name_span = locator.find(value.name, value.span)
            if binding is not None and name_span is not None:
                add(name_span, binding.type.render(), "Type", value.name)
            record = checked.record_contracts.get(value.name)
            if record is not None:
                for field in record.fields:
                    declaration = next(
                        (item for item in value.fields if item.name == field.name), None
                    )
                    field_span = (
                        locator.find(field.name, declaration.span)
                        if declaration is not None
                        else None
                    )
                    if field_span is not None:
                        add(
                            field_span,
                            field.type.render(),
                            "Field",
                            field.name,
                        )
        elif isinstance(value, ImportDecl):
            used: set[tuple[int, int]] = set()
            for imported, alias in value.names:
                local = alias or imported
                binding = checked.globals.get(local)
                name_span = locator.find(local, value.span, used=used, reverse=True)
                if binding is None or name_span is None:
                    continue
                used.add((name_span.line, name_span.column))
                add(name_span, binding.type.render(), "Import", local)
        elif isinstance(value, ModuleImportDecl):
            binding = checked.globals.get(value.alias)
            name_span = locator.find(value.alias, value.span, reverse=True)
            if binding is not None and name_span is not None:
                add(name_span, binding.type.render(), "ModuleImport", value.alias)
        elif (
            isinstance(
                value,
                NodeOccurrence
                | SequenceComposition
                | ParallelComposition
                | ChoiceComposition
                | RepeatComposition,
            )
            and value.relation
        ):
            relation_type = checked.expression_types.get(id(value)) or named_type(
                value.relation
            )
            relation_span = locator.find(
                value.relation.rsplit(".", 1)[-1], value.span, reverse=True
            )
            if relation_type is not None and relation_span is not None:
                add(
                    relation_span,
                    relation_type.render(),
                    "RelationReference",
                    value.relation,
                )
        elif isinstance(value, GuardedExit) and value.target:
            target_type = named_type(value.target)
            target_span = locator.find(
                value.target.rsplit(".", 1)[-1], value.span, reverse=True
            )
            if target_type is not None and target_span is not None:
                add(
                    target_span,
                    target_type.render(),
                    "ReasoningReference",
                    value.target,
                )
        elif isinstance(value, _EXPRESSION_NODES):
            inferred = expression_type(value)
            if inferred is not None:
                add(
                    value.span,
                    inferred.render(),
                    type(value).__name__,
                    _surface_expression_name(value) or None,
                )

        nested_reasoning = (
            value.name if isinstance(value, ReasoningDecl) else reasoning_name
        )
        if dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                if field.name != "span":
                    visit(getattr(value, field.name), nested_reasoning)
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item, reasoning_name)

    visit(program.declarations)
    return sorted(
        result,
        key=lambda item: (
            item.span.line,
            item.span.character,
            item.span.end_line or item.span.line,
            item.span.end_character or item.span.character,
        ),
    )


def _declaration_symbols(
    declaration: Any, globals_scope: Mapping[str, Binding]
) -> list[PrismIdeSymbol]:
    if isinstance(declaration, TypeDecl):
        return [
            _symbol(
                declaration.name,
                "Type",
                declaration.span,
                detail=(
                    declaration.alias.text
                    if declaration.alias
                    else ", ".join(
                        f"{item.name}: {item.type.text}" for item in declaration.fields
                    )
                ),
                metadata={
                    "fields": {
                        item.name: item.type.text for item in declaration.fields
                    },
                    "variants": declaration.alternatives,
                },
            )
        ]
    if isinstance(declaration, FunctionDecl):
        return [
            _symbol(
                declaration.name,
                "Function",
                declaration.span,
                detail=_callable_detail(
                    declaration.parameters, declaration.result.text
                ),
                metadata={
                    "effects": declaration.effects,
                    "assurance": declaration.result.text,
                },
            )
        ]
    if isinstance(declaration, WorkflowDecl):
        return [
            _symbol(
                declaration.name,
                "Workflow",
                declaration.span,
                detail=_callable_detail(
                    declaration.parameters, declaration.result.text
                ),
                metadata={
                    "effects": declaration.effects,
                    "failure": declaration.failure.text,
                    "assurance": declaration.result.text,
                },
            ),
            *_workflow_symbols(declaration.composition),
        ]
    if isinstance(declaration, ReasoningDecl):
        return [
            _symbol(
                declaration.name,
                "Reasoning",
                declaration.span,
                detail=_callable_detail(
                    declaration.parameters, declaration.result.text
                ),
                metadata={
                    "exits": tuple(
                        f"{item.occurrence}.{item.selector}:{item.action}"
                        for item in declaration.exits
                    ),
                    "assurance": declaration.result.text,
                },
            ),
            *_workflow_symbols(declaration.composition),
        ]
    if isinstance(declaration, RelationDecl):
        return [
            _symbol(
                declaration.name,
                "Relation",
                declaration.span,
                detail=_callable_detail(
                    declaration.parameters, declaration.result.text
                ),
                metadata={"certificate": declaration.result.text},
            )
        ]
    if isinstance(declaration, AgentDecl):
        return [
            _symbol(
                declaration.name,
                "Agent",
                declaration.span,
                detail=_callable_detail(
                    declaration.parameters, declaration.result.text
                ),
                metadata={
                    "capabilities": {
                        item.name: item.annotation.text
                        for item in declaration.capabilities
                        if item.annotation is not None
                    },
                    "effects": declaration.effects,
                },
            )
        ]
    if isinstance(declaration, ToolDecl):
        return [
            _symbol(
                declaration.name,
                "Tool",
                declaration.span,
                detail=declaration.type.text,
            )
        ]
    if isinstance(declaration, TheoremDecl):
        return [
            _symbol(
                declaration.name,
                "Theorem",
                declaration.span,
                detail=f"{{{', '.join(declaration.premises)}}} |- {declaration.conclusion}",
                metadata={"assurance": "Proof", "premises": declaration.premises},
            )
        ]
    if isinstance(declaration, SurfaceBinding):
        resolved = globals_scope.get(declaration.name)
        resolved_type = resolved.type if resolved is not None else None
        kind = {
            "Skill": "Skill",
            "Skills": "Skills",
            "Hooks": "Hooks",
            "Tool": "Tool",
            "Tools": "Tools",
        }.get(resolved_type.name if resolved_type else "", "Binding")
        return [
            _symbol(
                declaration.name,
                kind,
                declaration.span,
                detail=(
                    declaration.annotation.text
                    if declaration.annotation
                    else (
                        resolved_type.render()
                        if resolved_type is not None
                        else "inferred"
                    )
                ),
                metadata={
                    "canonical_type": (
                        resolved_type.render() if resolved_type is not None else None
                    ),
                },
            )
        ]
    if isinstance(declaration, ImportDecl):
        return [
            _symbol(
                alias or name,
                "Import",
                declaration.span,
                detail=f"{name} from {declaration.module}",
                module_path=declaration.module,
            )
            for name, alias in declaration.names
        ]
    if isinstance(declaration, ModuleImportDecl):
        return [
            _symbol(
                declaration.alias,
                "ModuleImport",
                declaration.span,
                detail=declaration.module,
                module_path=declaration.module,
            )
        ]
    return []


def _workflow_symbols(composition: Any) -> list[PrismIdeSymbol]:
    if isinstance(composition, NodeOccurrence):
        component = _surface_expression_name(composition.component)
        name = composition.alias or component.rsplit(".", 1)[-1]
        return [
            _symbol(
                name,
                "WorkflowNode",
                composition.span,
                detail=component,
                metadata={"component": component, "node_id": name},
            )
        ]
    if isinstance(composition, SequenceComposition | ParallelComposition):
        return [
            symbol
            for child in composition.children
            for symbol in _workflow_symbols(child)
        ]
    if isinstance(composition, ChoiceComposition):
        return [
            *_workflow_symbols(composition.router),
            *(
                symbol
                for arm in composition.arms
                for child in arm.children
                for symbol in _workflow_symbols(child)
            ),
        ]
    if isinstance(composition, RepeatComposition):
        return [
            symbol
            for child in composition.children
            for symbol in _workflow_symbols(child)
        ]
    return []


def _callable_detail(parameters, result: str) -> str:
    return f"({', '.join(f'{item.name}: {item.type.text}' for item in parameters)}) -> {result}"


def _symbol(name: str, kind: str, span, **values: Any) -> PrismIdeSymbol:
    return PrismIdeSymbol(
        name=name,
        kind=kind,
        span=_protocol_span(span),
        **values,
    )


def _protocol_span(span) -> PrismIdeSymbolSpan:
    return PrismIdeSymbolSpan(
        line=max(span.line - 1, 0),
        character=max(span.column - 1, 0),
        end_line=(span.end_line - 1) if span.end_line else None,
        end_character=(span.end_column - 1) if span.end_column else None,
    )


def _surface_expression_name(expression: Any) -> str:
    if isinstance(expression, NameExpr):
        return expression.name
    if isinstance(expression, FieldExpr):
        owner = _surface_expression_name(expression.value)
        return f"{owner}.{expression.field}" if owner else expression.field
    return ""


def _resolved_surface_type(type_expression, checked: TypedModule) -> CoreType:
    parsed = parse_type(type_expression.text, type_expression.span)
    return checked.aliases.get(parsed.name, parsed) if not parsed.arguments else parsed


class _NameLocator:
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
        within,
        *,
        used: set[tuple[int, int]] | None = None,
        reverse: bool = False,
    ):
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


def _position_in_span(line: int, column: int, span) -> bool:
    if line < span.line or (line == span.line and column < span.column):
        return False
    end_line = span.end_line or span.line
    end_column = span.end_column
    if line > end_line:
        return False
    return not (line == end_line and end_column is not None and column >= end_column)
