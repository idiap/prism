# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Document symbols for top-level declarations and their metadata."""

from __future__ import annotations

from typing import Any, Mapping

from prism.language.core import Binding
from prism.language.developer.syntax import (
    AgentDecl,
    FunctionDecl,
    ImportDecl,
    ModuleImportDecl,
    ReasoningDecl,
    RelationDecl,
    TheoremDecl,
    ToolDecl,
    TypeDecl,
    WorkflowDecl,
)
from prism.language.developer.syntax import Binding as SurfaceBinding
from prism.tooling.protocol import PrismIdeSymbol

from .compositions import workflow_symbols
from .spans import symbol


def declaration_symbols(
    declaration: Any, globals_scope: Mapping[str, Binding], occurrence_contracts=None
) -> list[PrismIdeSymbol]:
    if isinstance(declaration, TypeDecl):
        return _type_symbols(declaration)
    if isinstance(declaration, SurfaceBinding):
        return _binding_symbols(declaration, globals_scope)
    if isinstance(declaration, ImportDecl):
        return [
            symbol(
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
            symbol(
                declaration.alias,
                "ModuleImport",
                declaration.span,
                detail=declaration.module,
                module_path=declaration.module,
            )
        ]
    return _callable_symbols(declaration, occurrence_contracts)


def _callable_symbols(
    declaration: Any, occurrence_contracts=None
) -> list[PrismIdeSymbol]:
    if isinstance(declaration, FunctionDecl):
        return [
            symbol(
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
            symbol(
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
            *workflow_symbols(declaration.composition, occurrence_contracts),
        ]
    if isinstance(declaration, ReasoningDecl):
        return [
            symbol(
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
            *workflow_symbols(declaration.composition, occurrence_contracts),
        ]
    if isinstance(declaration, RelationDecl):
        return [
            symbol(
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
            symbol(
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
            symbol(
                declaration.name,
                "Tool",
                declaration.span,
                detail=declaration.type.text,
            )
        ]
    if isinstance(declaration, TheoremDecl):
        return [
            symbol(
                declaration.name,
                "Theorem",
                declaration.span,
                detail=f"{{{', '.join(declaration.premises)}}} |- {declaration.conclusion}",
                metadata={"assurance": "Proof", "premises": declaration.premises},
            )
        ]
    return []


def _type_symbols(declaration: TypeDecl) -> list[PrismIdeSymbol]:
    return [
        symbol(
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
                "fields": {item.name: item.type.text for item in declaration.fields},
                "variants": declaration.alternatives,
            },
        )
    ]


def _binding_symbols(
    declaration: SurfaceBinding, globals_scope: Mapping[str, Binding]
) -> list[PrismIdeSymbol]:
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
        symbol(
            declaration.name,
            kind,
            declaration.span,
            detail=(
                declaration.annotation.text
                if declaration.annotation
                else (
                    resolved_type.render() if resolved_type is not None else "inferred"
                )
            ),
            metadata={
                "canonical_type": (
                    resolved_type.render() if resolved_type is not None else None
                ),
            },
        )
    ]


def _callable_detail(parameters, result: str) -> str:
    return f"({', '.join(f'{item.name}: {item.type.text}' for item in parameters)}) -> {result}"
