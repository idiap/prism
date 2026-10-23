# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Reasoning invocation and workflow resolution."""

from __future__ import annotations

from dataclasses import replace

from prism.language.core import (
    BindingError,
    BindingScope,
    CoreType,
)
from prism.language.core.declarations import ReasoningInvocationContract

from ...diagnostics import SourceSpan
from ...syntax.ast import (
    CallExpr,
    Expression,
    ReasoningDecl,
)
from ..base import _CheckerPhase
from ..helpers import (
    _expression_name,
    _substitute,
)


class _ResolutionCheckingMixin(_CheckerPhase):
    def _infer_resolution(
        self,
        reasoning: Expression | None,
        workflow: Expression,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        *,
        execute: bool,
        span: SourceSpan,
    ) -> tuple[CoreType, tuple[str, ...]]:
        reasoning_effects: tuple[str, ...] = ()
        reasoning_success: CoreType | None = None
        if reasoning is not None:
            reasoning_success, reasoning_effects = self._infer_reasoning_invocation(
                reasoning, scope, enclosing_result
            )
        workflow_type, construction_effects = self._infer(
            workflow, scope, enclosing_result
        )
        if workflow_type.name != "Workflow" or len(workflow_type.arguments) < 2:
            self.fail(
                "resolution requires a bound Workflow value after `using`",
                span,
                "type-solve-workflow",
            )
        workflow_success, failure = workflow_type.arguments[:2]
        success = reasoning_success or workflow_success
        if reasoning_success is not None:
            self._expect(
                reasoning_success,
                workflow_success,
                span,
                "reasoning materialization output",
            )

        workflow_effects = tuple(item.name for item in workflow_type.arguments[2:])
        result = (
            success
            if failure.name == "Never"
            else CoreType("Result", (success, failure))
        )
        if execute:
            result = CoreType("Execution", (success, failure))
        return (
            result,
            tuple(
                dict.fromkeys(
                    (*reasoning_effects, *construction_effects, *workflow_effects)
                )
            ),
        )

    def _infer_reasoning_invocation(
        self,
        expression: Expression,
        scope: BindingScope,
        enclosing_result: CoreType | None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        if not isinstance(expression, CallExpr):
            self.fail(
                "the left side of `using` must invoke a reasoning declaration",
                expression.span,
                "type-solve-reasoning",
            )
        reasoning_name = _expression_name(expression.callee)
        contract = self.callables.get(reasoning_name)
        if contract is None or contract.kind != "reasoning":
            self.fail(
                f"`{reasoning_name}` is not a reasoning declaration",
                expression.span,
                "type-solve-reasoning",
            )
        if expression.type_arguments and len(expression.type_arguments) != len(
            contract.type_parameters
        ):
            self.fail(
                f"`{reasoning_name}` expects {len(contract.type_parameters)} type "
                f"arguments, got {len(expression.type_arguments)}",
                expression.span,
                "type-call-type-arguments",
            )
        argument_types: list[tuple[str | None, CoreType]] = []
        effects: list[str] = []
        for argument in expression.arguments:
            type_, argument_effects = self._infer(
                argument.value, scope, enclosing_result
            )
            argument_types.append((argument.name, type_))
            effects.extend(argument_effects)
        substitutions = (
            {
                parameter: self._type(argument)
                for parameter, argument in zip(
                    contract.type_parameters, expression.type_arguments, strict=True
                )
            }
            if expression.type_arguments
            else {}
        )
        substitutions = self._check_arguments(
            contract.parameters,
            argument_types,
            expression.span,
            reasoning_name,
            substitutions,
        )
        result = _substitute(contract.result, substitutions)
        missing = set(contract.type_parameters) - substitutions.keys()
        if missing:
            self.fail(
                f"cannot infer reasoning specialization: {', '.join(sorted(missing))}",
                expression.span,
                "type-reasoning-specialization",
            )
        invocation = ReasoningInvocationContract(
            self.scope.resolve(reasoning_name).identity,
            tuple(
                replace(parameter, type=_substitute(parameter.type, substitutions))
                for parameter in contract.parameters
            ),
            tuple(substitutions[name] for name in contract.type_parameters),
        )
        self.expression_types[id(expression)] = CoreType(
            "Reasoning", (result,), invocation=invocation
        )
        return result, tuple(dict.fromkeys(effects))

    def _reasoning_declaration(
        self, name: str, scope: BindingScope, span: SourceSpan
    ) -> ReasoningDecl:
        try:
            value = scope.resolve(name).value
        except BindingError:
            value = self.scope.resolve(name).value
        if isinstance(value, ReasoningDecl):
            return value
        self.fail(
            f"cannot inspect reasoning declaration `{name}`",
            span,
            "type-reasoning-declaration",
        )
