# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Callable, agent, theorem, tool, and relation contracts."""

from __future__ import annotations

from prism.language.core import (
    CallableContract,
    CoreType,
)
from prism.language.core import Parameter as CoreParameter
from prism.language.effects import SUPPORTED_EFFECTS

from ...syntax.ast import (
    AgentDecl,
    FunctionDecl,
    ReasoningDecl,
    RelationDecl,
    TheoremDecl,
    ToolDecl,
    WorkflowDecl,
)
from ...type_syntax import parse_type
from ..base import _CheckerPhase


class _CallableDeclarationMixin(_CheckerPhase):
    def _declare_callables_and_agents(self) -> None:
        for declaration in self.program.declarations:
            if isinstance(
                declaration,
                FunctionDecl | WorkflowDecl | ReasoningDecl | RelationDecl | AgentDecl,
            ):
                self._declare_callable(declaration)
            elif isinstance(declaration, TheoremDecl):
                self._declare_theorem(declaration)
        for declaration in self.program.declarations:
            if isinstance(declaration, ToolDecl):
                self._declare_tool(declaration)

    def _declare_callable(
        self,
        declaration: FunctionDecl
        | WorkflowDecl
        | ReasoningDecl
        | RelationDecl
        | AgentDecl,
    ) -> None:
        declared_effects = (
            declaration.effects
            if isinstance(declaration, FunctionDecl | WorkflowDecl | AgentDecl)
            else ()
        )
        unknown_effects = set(declared_effects) - SUPPORTED_EFFECTS
        if unknown_effects:
            self.fail(
                f"unknown effects: {', '.join(sorted(unknown_effects))}",
                declaration.span,
                "type-unknown-effect",
            )
        type_parameters = (
            () if isinstance(declaration, AgentDecl) else declaration.type_parameters
        )
        type_params = set(type_parameters)
        self._validate_type_parameter_declarations(
            type_parameters, declaration.span, declaration.name
        )
        parameter_scope = self._parameter_scope(
            declaration.parameters, declaration.span, type_params
        )
        parameters = tuple(
            CoreParameter(
                item.name,
                parameter_scope.resolve(item.name).type,
                parameter_scope.resolve(item.name).identity,
            )
            for item in declaration.parameters
        )
        result = self._type(
            declaration.result,
            type_params | {item.name for item in declaration.parameters},
            scope=parameter_scope,
        )
        contract = CallableContract(
            declaration.name,
            parameters,
            result,
            declared_effects,
            self._callable_kind(declaration),
            type_parameters,
            (
                self._type(declaration.failure, type_params)
                if isinstance(declaration, WorkflowDecl)
                else None
            ),
        )
        self.callables[declaration.name] = contract
        self.callable_origins[declaration.name] = self.program.path
        self._bind(declaration.name, contract.type, declaration, declaration.span)

    def _callable_kind(
        self,
        declaration: FunctionDecl
        | WorkflowDecl
        | ReasoningDecl
        | RelationDecl
        | AgentDecl,
    ) -> str:
        kind = "def"
        if isinstance(declaration, WorkflowDecl):
            kind = "workflow"
        elif isinstance(declaration, ReasoningDecl):
            kind = "reasoning"
        elif isinstance(declaration, RelationDecl):
            kind = "relation"
        elif isinstance(declaration, AgentDecl):
            kind = "agent"
        return kind

    def _declare_theorem(self, declaration: TheoremDecl) -> None:
        parameters = tuple(
            CoreParameter(
                item.name,
                self._type(item.type, {p.name for p in declaration.parameters}),
            )
            for item in declaration.parameters
        )
        result = CoreType("Proof", (parse_type(declaration.conclusion),))
        contract = CallableContract(declaration.name, parameters, result, (), "theorem")
        self.callables[declaration.name] = contract
        self.callable_origins[declaration.name] = self.program.path
        self._bind(declaration.name, contract.type, declaration, declaration.span)

    def _declare_tool(self, declaration: ToolDecl) -> None:
        tool_type = self._type(declaration.type)
        if tool_type.name != "Tool" or len(tool_type.arguments) != 1:
            self.fail(
                "a tool annotation must be `Tool[CallableContract]`",
                declaration.span,
                "type-tool-contract",
            )
        self._bind(declaration.name, tool_type, declaration, declaration.span)

    def _check_relation_declarations(self) -> None:
        for declaration in self.program.declarations:
            if not isinstance(declaration, RelationDecl):
                continue
            contract = self.callables[declaration.name]
            if len(contract.parameters) != 2:
                self.fail(
                    f"relation `{declaration.name}` must declare exactly source and target endpoints",
                    declaration.span,
                    "type-relation-endpoints",
                )
