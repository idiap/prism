# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Lower expressions and reasoning invocations into executable IR."""

from __future__ import annotations

from typing import Any

from prism.language.core import CoreType, TypedModule
from prism.language.effects import Binary as IRBinary
from prism.language.effects import CallArgument as IRCallArgument
from prism.language.effects import CallExpression as IRCallExpression
from prism.language.effects import Conditional as IRConditional
from prism.language.effects import Execute as IRExecute
from prism.language.effects import Field as IRField
from prism.language.effects import Index as IRIndex
from prism.language.effects import ListValue as IRListValue
from prism.language.effects import Literal as IRLiteral
from prism.language.effects import MapValue as IRMapValue
from prism.language.effects import ReasoningInvocation as IRReasoningInvocation
from prism.language.effects import Reference as IRReference
from prism.language.effects import Solve as IRSolve
from prism.language.effects import Try as IRTry
from prism.language.effects import TupleValue as IRTupleValue
from prism.language.effects import Unary as IRUnary
from prism.language.evidence import MaterialInference as IRMaterialInference

from .checking.helpers import (
    _expression_name,
)
from .syntax.ast import (
    AgentDecl,
    BinaryExpr,
    Binding,
    CallExpr,
    ConditionalExpr,
    ExecuteExpr,
    Expression,
    FieldExpr,
    IndexExpr,
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


def _lower_expression(
    expression: Expression,
    module: TypedModule,
    *,
    namespace: str | None = None,
) -> Any:
    if isinstance(expression, LiteralExpr):
        return IRLiteral(expression.value)
    if isinstance(expression, NameExpr):
        return _lower_name(expression, module, namespace)
    if isinstance(expression, ListExpr):
        return IRListValue(
            tuple(
                _lower_expression(item, module, namespace=namespace)
                for item in expression.items
            )
        )
    if isinstance(expression, TupleExpr):
        return IRTupleValue(
            tuple(
                _lower_expression(item, module, namespace=namespace)
                for item in expression.items
            )
        )
    if isinstance(expression, MapExpr):
        return IRMapValue(
            tuple(
                (
                    _lower_expression(key, module, namespace=namespace),
                    _lower_expression(value, module, namespace=namespace),
                )
                for key, value in expression.items
            )
        )
    if isinstance(expression, FieldExpr):
        qualified = _expression_name(expression)
        if (
            qualified in module.callable_contracts
            or qualified in module.record_contracts
            or (
                qualified in module.globals
                and isinstance(module.globals[qualified].value, AgentDecl | Binding)
            )
        ):
            return IRReference(qualified)
        return IRField(
            _lower_expression(expression.value, module, namespace=namespace),
            expression.field,
        )
    if isinstance(expression, CallExpr):
        return IRCallExpression(
            _lower_expression(expression.callee, module, namespace=namespace),
            tuple(
                IRCallArgument(
                    _lower_expression(item.value, module, namespace=namespace),
                    item.name,
                )
                for item in expression.arguments
            )
            + _lower_policy_claim(expression, module),
            module.expression_types[id(expression)],
            module.expression_terms.get(id(expression)),
            _lower_proof_bindings(expression, module),
        )
    return _lower_control_expression(expression, module, namespace)


def _lower_reasoning_invocation(
    expression: Expression | None,
    module: TypedModule,
    *,
    namespace: str | None,
) -> IRReasoningInvocation | None:
    if expression is None:
        return None
    if not isinstance(expression, CallExpr):
        raise TypeError("checked reasoning invocation is not a call")
    return IRReasoningInvocation(
        _lower_expression(expression.callee, module, namespace=namespace),
        tuple(
            IRCallArgument(
                _lower_expression(argument.value, module, namespace=namespace),
                argument.name,
            )
            for argument in expression.arguments
        ),
        module.expression_types[id(expression)].invocation,
    )


def _lower_control_expression(
    expression: Expression, module: TypedModule, namespace: str | None
) -> Any:
    if isinstance(expression, ConditionalExpr):
        return IRConditional(
            _lower_expression(expression.condition, module, namespace=namespace),
            _lower_expression(expression.when_true, module, namespace=namespace),
            _lower_expression(expression.when_false, module, namespace=namespace),
        )
    if isinstance(expression, IndexExpr):
        return IRIndex(
            _lower_expression(expression.value, module, namespace=namespace),
            _lower_expression(expression.index, module, namespace=namespace),
        )
    if isinstance(expression, TryExpr):
        return IRTry(_lower_expression(expression.value, module, namespace=namespace))
    if isinstance(expression, SolveExpr):
        return IRSolve(
            _lower_reasoning_invocation(
                expression.reasoning, module, namespace=namespace
            ),
            _lower_expression(expression.workflow, module, namespace=namespace),
        )
    if isinstance(expression, ExecuteExpr):
        return IRExecute(
            _lower_reasoning_invocation(
                expression.reasoning, module, namespace=namespace
            ),
            _lower_expression(expression.workflow, module, namespace=namespace),
        )
    if isinstance(expression, MaterialInferenceExpr):
        return IRMaterialInference(
            _lower_expression(expression.evidence, module, namespace=namespace),
            _lower_expression(expression.policy, module, namespace=namespace),
            _lower_expression(expression.proposition, module, namespace=namespace),
        )
    if isinstance(expression, UnaryExpr):
        return IRUnary(
            expression.operator,
            _lower_expression(expression.operand, module, namespace=namespace),
        )
    if isinstance(expression, BinaryExpr):
        return IRBinary(
            _lower_expression(expression.left, module, namespace=namespace),
            expression.operator,
            _lower_expression(expression.right, module, namespace=namespace),
        )
    raise TypeError(f"cannot lower expression `{type(expression).__name__}`")


def _lower_name(
    expression: NameExpr, module: TypedModule, namespace: str | None
) -> IRReference:
    qualified = (
        f"{namespace}.{expression.name}"
        if namespace and "." not in expression.name
        else None
    )
    if qualified and (
        qualified in module.callable_contracts
        or qualified in module.record_contracts
        or (
            qualified in module.globals
            and isinstance(module.globals[qualified].value, AgentDecl | Binding)
        )
    ):
        return IRReference(qualified)
    return IRReference(expression.name)


def _lower_policy_claim(expression, module):
    name = _expression_name(expression.callee)
    type_ = module.expression_types[id(expression)]
    if name == "material_policy":
        claim = type_.arguments[1].proposition
    elif name == "validate":
        claim = type_.arguments[0].arguments[1].proposition
    else:
        return ()
    return (IRCallArgument(_lower_proof_binding(claim, module), "_claim"),)


def _lower_proof_binding(index, module):
    if index.kind == "reference":
        global_name = next(
            (
                name
                for name, binding in module.globals.items()
                if binding.identity == index.symbol
            ),
            None,
        )
        return IRReference(
            global_name or index.render(), global_binding=global_name is not None
        )
    if index.kind == "apply":
        return IRCallExpression(
            _lower_proof_binding(index.children[0], module),
            tuple(
                IRCallArgument(_lower_proof_binding(child, module))
                for child in index.children[1:]
            ),
            CoreType("Proposition", proposition=index)
            if index.type and index.type.name == "Prop"
            else index.type,
        )
    if index.kind == "field":
        return IRField(_lower_proof_binding(index.children[0], module), index.symbol)
    if index.kind == "index":
        return IRIndex(
            *(_lower_proof_binding(child, module) for child in index.children)
        )
    if index.kind == "binary":
        return IRBinary(
            _lower_proof_binding(index.children[0], module),
            index.symbol,
            _lower_proof_binding(index.children[1], module),
        )
    if index.kind == "literal":
        import ast

        return IRLiteral(ast.literal_eval(index.symbol))
    raise ValueError(f"unsupported checked proof binding {index.kind}")


def _lower_proof_bindings(expression, module):
    result = []
    for index in module.expression_proof_bindings.get(id(expression), ()):
        if index.type is None:
            raise ValueError("checked proof binding is missing its runtime type")
        result.append((index.render(), _lower_proof_binding(index, module), index.type))
    return tuple(result)
