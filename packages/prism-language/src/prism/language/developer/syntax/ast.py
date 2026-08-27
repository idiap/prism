# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Source-faithful AST for the supported Prism surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prism.language.developer.diagnostics import SourceSpan


@dataclass(frozen=True, slots=True)
class TypeExpr:
    text: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type: TypeExpr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class LiteralExpr:
    value: Any
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class NameExpr:
    name: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class LambdaExpr:
    parameter: str
    body: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ListExpr:
    items: tuple["Expression", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class TupleExpr:
    items: tuple["Expression", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class MapExpr:
    items: tuple[tuple["Expression", "Expression"], ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class CallArgument:
    value: "Expression"
    name: str | None = None


@dataclass(frozen=True, slots=True)
class CallExpr:
    callee: "Expression"
    arguments: tuple[CallArgument, ...]
    span: SourceSpan
    type_arguments: tuple[TypeExpr, ...] = ()


@dataclass(frozen=True, slots=True)
class FieldExpr:
    value: "Expression"
    field: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class UnaryExpr:
    operator: str
    operand: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class BinaryExpr:
    left: "Expression"
    operator: str
    right: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ConditionalExpr:
    condition: "Expression"
    when_true: "Expression"
    when_false: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IndexExpr:
    value: "Expression"
    index: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class TryExpr:
    value: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class SolveExpr:
    reasoning: "Expression | None"
    workflow: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ExecuteExpr:
    reasoning: "Expression | None"
    workflow: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class MaterialInferenceExpr:
    evidence: "Expression"
    policy: "Expression"
    proposition: "Expression"
    span: SourceSpan


Expression = (
    LiteralExpr
    | NameExpr
    | LambdaExpr
    | ListExpr
    | TupleExpr
    | MapExpr
    | CallExpr
    | FieldExpr
    | UnaryExpr
    | BinaryExpr
    | ConditionalExpr
    | IndexExpr
    | TryExpr
    | SolveExpr
    | ExecuteExpr
    | MaterialInferenceExpr
)


@dataclass(frozen=True, slots=True)
class Binding:
    name: str
    value: Expression
    span: SourceSpan
    annotation: TypeExpr | None = None


@dataclass(frozen=True, slots=True)
class Return:
    value: Expression
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Exact:
    proof: Expression
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ExpressionStatement:
    value: Expression
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ImportDecl:
    module: str
    names: tuple[tuple[str, str | None], ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ModuleImportDecl:
    module: str
    alias: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class TypeField:
    name: str
    type: TypeExpr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class TypeDecl:
    name: str
    fields: tuple[TypeField, ...]
    span: SourceSpan
    type_parameters: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    alias: TypeExpr | None = None
    alternative_spans: tuple[SourceSpan, ...] = ()


@dataclass(frozen=True, slots=True)
class FunctionDecl:
    name: str
    parameters: tuple[Parameter, ...]
    result: TypeExpr
    body: tuple["Statement", ...]
    span: SourceSpan
    effects: tuple[str, ...] = ()
    type_parameters: tuple[str, ...] = ()
    is_proposition_declaration: bool = False


@dataclass(frozen=True, slots=True)
class AgentDecl:
    name: str
    parameters: tuple[Parameter, ...]
    result: TypeExpr
    capabilities: tuple[Binding, ...]
    span: SourceSpan
    effects: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolDecl:
    name: str
    type: TypeExpr
    callable: Expression
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class NodeOccurrence:
    component: Expression
    alias: str | None
    span: SourceSpan
    relation: str | None = None


@dataclass(frozen=True, slots=True)
class SequenceComposition:
    children: tuple["Composition", ...]
    span: SourceSpan
    relation: str | None = None


@dataclass(frozen=True, slots=True)
class ParallelComposition:
    children: tuple["Composition", ...]
    span: SourceSpan
    relation: str | None = None


@dataclass(frozen=True, slots=True)
class ChoiceArm:
    pattern: str
    children: tuple["Composition", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ChoiceComposition:
    router: NodeOccurrence
    arms: tuple[ChoiceArm, ...]
    span: SourceSpan
    relation: str | None = None


@dataclass(frozen=True, slots=True)
class RepeatComposition:
    policy: Expression
    children: tuple["Composition", ...]
    span: SourceSpan
    relation: str | None = None
    until: Expression | None = None


Composition = (
    NodeOccurrence
    | SequenceComposition
    | ParallelComposition
    | ChoiceComposition
    | RepeatComposition
)


@dataclass(frozen=True, slots=True)
class WorkflowDecl:
    name: str
    parameters: tuple[Parameter, ...]
    result: TypeExpr
    failure: TypeExpr
    composition: Composition
    result_alias: str | None
    span: SourceSpan
    effects: tuple[str, ...] = ()
    type_parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GuardedExit:
    occurrence: str
    selector: str
    action: str
    span: SourceSpan
    target: str | None = None


@dataclass(frozen=True, slots=True)
class ReasoningDecl:
    name: str
    parameters: tuple[Parameter, ...]
    result: TypeExpr
    composition: Composition
    exits: tuple[GuardedExit, ...]
    result_alias: str | None
    span: SourceSpan
    type_parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationDecl:
    name: str
    parameters: tuple[Parameter, ...]
    result: TypeExpr
    span: SourceSpan
    type_parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TheoremDecl:
    name: str
    parameters: tuple[Parameter, ...]
    premises: tuple[str, ...]
    conclusion: str
    body: tuple["Statement", ...]
    span: SourceSpan


Statement = Binding | Return | Exact | ExpressionStatement
Declaration = (
    ImportDecl
    | ModuleImportDecl
    | TypeDecl
    | FunctionDecl
    | AgentDecl
    | ToolDecl
    | WorkflowDecl
    | ReasoningDecl
    | RelationDecl
    | TheoremDecl
    | Binding
)


@dataclass(frozen=True, slots=True)
class Program:
    declarations: tuple[Declaration, ...]
    source: str
    path: str | None = None
