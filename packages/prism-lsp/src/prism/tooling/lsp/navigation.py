# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Canonical-AST-backed definition navigation for Prism editor clients."""

from __future__ import annotations

import dataclasses
import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from prism.language import parse_source
from prism.language.core import CoreType
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
from prism.sdk.workspace import WorkspaceModuleLoader
from prism.tooling.protocol import (
    PrismIdeDefinitionResult,
    PrismIdeDefinitionTarget,
    PrismIdeSymbol,
    PrismIdeSymbolSpan,
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


def definition_at(
    program: Program,
    *,
    document_path: Path,
    modules: WorkspaceModuleLoader,
    line: int,
    character: int,
    intrinsic_symbols: Iterable[PrismIdeSymbol] = (),
    variants: Mapping[str, tuple[str, ...]] | None = None,
    reasoning_outputs: Mapping[str, Mapping[str, CoreType]] | None = None,
    aliases: Mapping[str, CoreType] | None = None,
) -> PrismIdeDefinitionResult | None:
    """Resolve a source position without re-parsing Prism in an editor client."""

    token = _name_token_at(program.source, line, character)
    if token is None:
        return None
    query_name, origin = token
    path = str(document_path.resolve())
    definitions = _definitions(program, path)
    exact = [item for item in definitions if _contains(item.span, line, character)]
    for item in exact:
        if item.module:
            targets = _module_export_targets(modules, item.module, item.target_name)
            if targets:
                return _result(origin, targets)
        return _result(origin, [item])

    source_import = _import_at(program, line, character)
    if source_import is not None:
        module = source_import.module
        targets = _module_export_targets(modules, module, None)
        if targets:
            return _result(origin, targets)

    imports = _imports(program)
    imported = imports.get(query_name)
    qualifier = _qualifier_before(program.source, line, origin.column - 1)
    if qualifier:
        module_import = imports.get(qualifier.split(".", 1)[0])
        if module_import and module_import[1] is None:
            targets = _module_export_targets(modules, module_import[0], query_name)
            if targets:
                return _result(origin, targets)
    if imported is not None and (not qualifier or imported[1] is not None):
        targets = _module_export_targets(
            modules, imported[0], imported[1] or query_name
        )
        if targets:
            return _result(origin, targets)

    owner = _enclosing_owner(program, line, character)
    if qualifier and owner and reasoning_outputs:
        receiver = qualifier.rsplit(".", 1)[-1]
        receiver_type = reasoning_outputs.get(owner, {}).get(receiver)
        if receiver_type is not None:
            resolved = (aliases or {}).get(receiver_type.name, receiver_type)
            variant_owners = {
                receiver_type.name,
                receiver_type.name.rsplit(".", 1)[-1],
                resolved.name,
                resolved.name.rsplit(".", 1)[-1],
            }
            declared_variants = (variants or {}).get(receiver_type.name) or (
                variants or {}
            ).get(resolved.name, ())
            if query_name in declared_variants:
                candidates = definitions + _imported_definitions(modules, program)
                targets = [
                    item
                    for item in candidates
                    if item.name == query_name
                    and item.kind == "variant"
                    and item.owner in variant_owners
                ]
                if targets:
                    return _result(origin, targets)
    local = [
        item
        for item in definitions
        if item.name == query_name
        and (item.owner is None or item.owner == owner)
        and (item.exported or item.span.line - 1 <= line)
    ]
    if qualifier:
        fields = [
            item
            for item in definitions
            if item.name == query_name
            and item.kind in {"field", "port", "variant", "variant-field"}
        ]
        fields.extend(
            item
            for item in _imported_definitions(modules, program)
            if item.name == query_name
            and item.kind in {"field", "port", "variant", "variant-field"}
        )
        if fields:
            return _result(origin, fields)
    if local:
        local.sort(
            key=lambda item: (item.owner == owner, item.span.line, item.span.column),
            reverse=True,
        )
        return _result(origin, [local[0]])

    call_owner = _call_owner_for_named_argument(program.source, line, origin)
    if call_owner:
        imported_owner = imports.get(call_owner)
        if imported_owner:
            owned = [
                item
                for item in _module_definitions(modules, imported_owner[0])
                if item.name == query_name
                and item.owner == (imported_owner[1] or call_owner)
            ]
            if owned:
                return _result(origin, owned)
        owned = _workspace_definitions(
            modules, program, path, query_name, owner=call_owner
        )
        if owned:
            return _result(origin, owned)

    if qualifier:
        members = [
            item
            for item in _imported_definitions(modules, program)
            if item.name == query_name
            and item.kind in {"field", "port", "variant-field"}
        ]
        members.extend(
            _workspace_definitions(
                modules,
                program,
                path,
                query_name,
                kinds={"field", "port", "variant-field"},
            )
        )
        if members:
            return _result(origin, members)

    intrinsic = [
        item
        for item in intrinsic_symbols
        if item.name == query_name and item.definition_path
    ]
    if intrinsic:
        return PrismIdeDefinitionResult(
            origin=_protocol_span(origin),
            targets=[
                PrismIdeDefinitionTarget(
                    definition_path=str(item.definition_path), span=item.span
                )
                for item in intrinsic
            ],
        )

    exported = _workspace_definitions(modules, program, path, query_name, exported=True)
    return _result(origin, exported) if exported else None


def _definitions(program: Program, path: str) -> list[_Definition]:
    locator = _TokenLocator(program.source)
    result: list[_Definition] = []

    def add(
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
        span = locator.find(name, within, reverse=reverse, used=used)
        if span is None:
            return
        if used is not None:
            used.add((span.line, span.column))
        result.append(
            _Definition(name, kind, span, path, owner, module, target_name, exported)
        )

    def visit(value: Any, owner: str | None = None) -> None:
        if isinstance(value, ImportDecl):
            used: set[tuple[int, int]] = set()
            for imported, alias in value.names:
                local = alias or imported
                add(
                    local,
                    "import",
                    value.span,
                    module=value.module,
                    target_name=imported,
                    reverse=True,
                    used=used,
                )
            return
        if isinstance(value, ModuleImportDecl):
            add(
                value.alias,
                "module-import",
                value.span,
                module=value.module,
                reverse=True,
            )
            return
        if isinstance(value, TypeDecl):
            add(value.name, "type", value.span, exported=True)
            for name in value.type_parameters:
                add(name, "type-parameter", value.span, owner=value.name)
            for field in value.fields:
                add(field.name, "field", field.span, owner=value.name)
            for index, alternative in enumerate(value.alternatives):
                match = re.match(r"([A-Za-z_]\w*)", alternative)
                if match:
                    within = (
                        value.alternative_spans[index]
                        if index < len(value.alternative_spans)
                        else value.span
                    )
                    add(
                        match.group(1),
                        "variant",
                        within,
                        owner=value.name,
                        exported=True,
                    )
            return
        if isinstance(value, AgentDecl):
            add(value.name, "agent", value.span, exported=True)
            for parameter in value.parameters:
                add(parameter.name, "port", parameter.span, owner=value.name)
            return
        if isinstance(value, (WorkflowDecl, ReasoningDecl)):
            add(
                value.name,
                "reasoning" if isinstance(value, ReasoningDecl) else "workflow",
                value.span,
                exported=True,
            )
            for name in value.type_parameters:
                add(name, "type-parameter", value.span, owner=value.name)
            for parameter in value.parameters:
                add(parameter.name, "parameter", parameter.span, owner=value.name)
            visit(value.composition, value.name)
            return
        if isinstance(value, RelationDecl):
            add(value.name, "relation", value.span, exported=True)
            for name in value.type_parameters:
                add(name, "type-parameter", value.span, owner=value.name)
            for parameter in value.parameters:
                add(parameter.name, "parameter", parameter.span, owner=value.name)
            return
        if isinstance(value, TheoremDecl):
            add(value.name, "theorem", value.span, exported=True)
            for parameter in value.parameters:
                add(parameter.name, "parameter", parameter.span, owner=value.name)
            for statement in value.body:
                visit(statement, value.name)
            return
        if isinstance(value, FunctionDecl):
            add(value.name, "function", value.span, exported=True)
            for name in value.type_parameters:
                add(name, "type-parameter", value.span, owner=value.name)
            for parameter in value.parameters:
                add(parameter.name, "parameter", parameter.span, owner=value.name)
            for statement in value.body:
                visit(statement, value.name)
            return
        if isinstance(value, Binding):
            add(value.name, "binding", value.span, owner=owner, exported=owner is None)
            return
        if isinstance(value, NodeOccurrence):
            if value.alias:
                add(value.alias, "workflow-node", value.span, owner=owner)
            return
        if dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                if field.name != "span":
                    visit(getattr(value, field.name), owner)
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item, owner)

    for declaration in program.declarations:
        visit(declaration)
    return result


def _imports(program: Program) -> dict[str, tuple[str, str | None]]:
    result: dict[str, tuple[str, str | None]] = {}
    for declaration in program.declarations:
        if isinstance(declaration, ImportDecl):
            for imported, alias in declaration.names:
                result[alias or imported] = (declaration.module, imported)
        elif isinstance(declaration, ModuleImportDecl):
            result[declaration.alias] = (declaration.module, None)
    return result


def _module_export_targets(
    modules: WorkspaceModuleLoader, module_name: str, export_name: str | None
) -> list[_Definition]:
    try:
        source = modules.load_module(module_name)
        program = parse_source(source.source, path=source.origin)
    except ValueError:
        return []
    if not source.origin:
        return []
    definitions = _definitions(program, source.origin)
    if export_name is None:
        return [
            _Definition(module_name, "module", SourceSpan(1, 1, 1, 1), source.origin)
        ]
    return [item for item in definitions if item.exported and item.name == export_name]


def _module_definitions(
    modules: WorkspaceModuleLoader, module_name: str
) -> list[_Definition]:
    try:
        source = modules.load_module(module_name)
        if not source.origin:
            return []
        return _definitions(
            parse_source(source.source, path=source.origin), source.origin
        )
    except ValueError:
        return []


def _imported_definitions(
    modules: WorkspaceModuleLoader, program: Program
) -> list[_Definition]:
    result: list[_Definition] = []
    seen: set[str] = set()
    for declaration in program.declarations:
        if not isinstance(declaration, (ImportDecl, ModuleImportDecl)):
            continue
        if declaration.module in seen:
            continue
        seen.add(declaration.module)
        result.extend(_module_definitions(modules, declaration.module))
    return result


def _workspace_definitions(
    modules: WorkspaceModuleLoader,
    current: Program,
    current_path: str,
    name: str,
    *,
    owner: str | None = None,
    kinds: set[str] | None = None,
    exported: bool = False,
) -> list[_Definition]:
    result = _definitions(current, current_path)
    seen_paths = {current_path}
    for module_name in modules.iter_workspace_modules():
        try:
            source = modules.load_module(module_name)
            if not source.origin or source.origin in seen_paths:
                continue
            seen_paths.add(source.origin)
            result.extend(
                _definitions(
                    parse_source(source.source, path=source.origin), source.origin
                )
            )
        except ValueError:
            continue
    return [
        item
        for item in result
        if item.name == name
        and (owner is None or item.owner == owner)
        and (kinds is None or item.kind in kinds)
        and (not exported or item.exported)
    ]


def _import_at(
    program: Program, line: int, character: int
) -> ImportDecl | ModuleImportDecl | None:
    for declaration in program.declarations:
        if isinstance(declaration, (ImportDecl, ModuleImportDecl)) and _contains(
            declaration.span, line, character
        ):
            line_text = (
                program.source.splitlines()[line]
                if line < len(program.source.splitlines())
                else ""
            )
            module = declaration.module.lstrip(".")
            start = line_text.find(module)
            if start >= 0 and start <= character <= start + len(module):
                return declaration
    return None


def _enclosing_owner(program: Program, line: int, character: int) -> str | None:
    declarations = program.declarations
    for index, declaration in enumerate(declarations):
        if not isinstance(
            declaration,
            (
                AgentDecl,
                FunctionDecl,
                ReasoningDecl,
                RelationDecl,
                TheoremDecl,
                TypeDecl,
                WorkflowDecl,
            ),
        ):
            continue
        start_line = declaration.span.line - 1
        next_line = (
            declarations[index + 1].span.line - 1
            if index + 1 < len(declarations)
            else len(program.source.splitlines())
        )
        if start_line <= line < next_line:
            return declaration.name
    return None


def _name_token_at(
    source: str, line: int, character: int
) -> tuple[str, SourceSpan] | None:
    for token in _tokens(source):
        if token.type != tokenize.NAME or token.start[0] - 1 != line:
            continue
        if token.start[1] <= character < token.end[1] or (
            character == token.end[1] and token.start[1] < character
        ):
            return token.string, SourceSpan(
                token.start[0], token.start[1] + 1, token.end[0], token.end[1] + 1
            )
    return None


def _qualifier_before(source: str, line: int, character: int) -> str | None:
    lines = source.splitlines()
    if line >= len(lines):
        return None
    match = re.search(
        r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\.\s*$", lines[line][:character]
    )
    return match.group(1) if match else None


def _call_owner_for_named_argument(
    source: str, line: int, origin: SourceSpan
) -> str | None:
    lines = source.splitlines()
    if line >= len(lines) or not re.match(
        r"\s*=(?!=)", lines[line][(origin.end_column or origin.column) - 1 :]
    ):
        return None
    prefix = "\n".join(lines[:line] + [lines[line][: origin.column - 1]])
    open_at = prefix.rfind("(")
    if open_at < 0:
        return None
    match = re.search(r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*$", prefix[:open_at])
    return match.group(1).rsplit(".", 1)[-1] if match else None


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


def _contains(span: SourceSpan, zero_line: int, zero_character: int) -> bool:
    return _source_position_in_span(zero_line + 1, zero_character + 1, span)


def _source_position_in_span(line: int, column: int, span: SourceSpan) -> bool:
    if line < span.line or (line == span.line and column < span.column):
        return False
    end_line = span.end_line or span.line
    end_column = span.end_column
    if line > end_line:
        return False
    return not (line == end_line and end_column is not None and column >= end_column)


def _protocol_span(span: SourceSpan) -> PrismIdeSymbolSpan:
    return PrismIdeSymbolSpan(
        line=span.line - 1,
        character=span.column - 1,
        end_line=(span.end_line - 1) if span.end_line else span.line - 1,
        end_character=(span.end_column - 1) if span.end_column else span.column,
    )


def _result(
    origin: SourceSpan, definitions: Iterable[_Definition]
) -> PrismIdeDefinitionResult:
    unique: dict[tuple[str, int, int], _Definition] = {}
    for item in definitions:
        unique[(item.path, item.span.line, item.span.column)] = item
    return PrismIdeDefinitionResult(
        origin=_protocol_span(origin),
        targets=[
            PrismIdeDefinitionTarget(
                definition_path=item.path, span=_protocol_span(item.span)
            )
            for item in unique.values()
        ],
    )
