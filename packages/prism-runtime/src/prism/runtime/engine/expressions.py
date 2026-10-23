# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""IR expression evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from prism.language.core import (
    ComputedValue,
    Err,
    ExecutionValue,
    GeneratedValue,
    Ok,
    RecordValue,
    ValidatedValue,
)
from prism.language.effects import (
    Binary,
    CallExpression,
    Conditional,
    Execute,
    Field,
    Index,
    ListValue,
    Literal,
    MapValue,
    ReasoningInvocation,
    Reference,
    Return,
    Solve,
    Try,
    TupleValue,
    Unary,
    ValueBinding,
)
from prism.language.evidence import Evidence, MaterialInference

from .evidence import _eval_material_inference
from .provenance import CallReferences, ValueEnvironment, finish_evaluation
from .values import (
    ReasoningInvocationValue,
    _Builtin,
    _Propagate,
    _ReasoningFactory,
    _ReturnSignal,
)

if TYPE_CHECKING:
    from .execution import _Engine


def _execute_statements(
    self: _Engine, statements: tuple[Any, ...], env: dict[str, Any]
) -> None:
    for statement in statements:
        self._execute_statement(statement, env)


def _execute_statement(self: _Engine, statement: Any, env: dict[str, Any]) -> None:
    if isinstance(statement, ValueBinding):
        if statement.name in env and statement.name not in self.global_env:
            raise ValueError(f"duplicate immutable runtime binding `{statement.name}`")
        value = self._eval(statement.expression, env)
        env[statement.name] = value
        if isinstance(env, ValueEnvironment):
            assert self.provenance.last is not None
            env.references[statement.name] = self.provenance.last
    elif isinstance(statement, Return):
        raise _ReturnSignal(self._eval(statement.expression, env))
    else:
        self._eval(statement, env)


def _eval(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    children = []
    self.provenance.evaluations.append(children)
    try:
        for type_, handler in _EVAL_HANDLERS:
            if isinstance(expression, type_):
                value = handler(self, expression, env)
                reference_environment = (
                    self.global_env
                    if isinstance(expression, Reference) and expression.global_binding
                    else env
                )
                reference = finish_evaluation(
                    self.provenance, expression, value, reference_environment, children
                )
                self.provenance.last = reference
                break
        else:
            raise TypeError(f"unsupported IR expression `{type(expression).__name__}`")
    finally:
        self.provenance.evaluations.pop()
    if self.provenance.evaluations:
        self.provenance.evaluations[-1].append((value, reference))
    return value


def _field(self: _Engine, value: Any, name: str) -> Any:
    if isinstance(value, RecordValue):
        return value.fields[name]
    if isinstance(value, Evidence) and name == "value":
        return value.value
    if (
        isinstance(value, ComputedValue | GeneratedValue | ValidatedValue)
        and name == "value"
    ):
        return value.value
    if isinstance(value, _Builtin) and value.name == "kernel" and name == "check":
        return _Builtin("kernel.check")
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _binary(operator: str, left: Any, right: Any) -> Any:
    operations = {
        "+": lambda: left + right,
        "-": lambda: left - right,
        "*": lambda: left * right,
        "/": lambda: left / right,
        "**": lambda: left**right,
        "%": lambda: left % right,
        "==": lambda: left == right,
        "!=": lambda: left != right,
        "<": lambda: left < right,
        "<=": lambda: left <= right,
        ">": lambda: left > right,
        ">=": lambda: left >= right,
        "and": lambda: bool(left and right),
        "or": lambda: bool(left or right),
    }
    return operations[operator]()


def _eval_literal(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    return expression.value


def _eval_reference(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    if expression.global_binding:
        return self.global_env[expression.name]
    if expression.name in env:
        return env[expression.name]
    return _Builtin(expression.name)


def _eval_list_value(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    return [self._eval(item, env) for item in expression.items]


def _eval_tuple_value(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    return tuple(self._eval(item, env) for item in expression.items)


def _eval_map_value(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    return {
        self._eval(key, env): self._eval(value, env) for key, value in expression.items
    }


def _eval_field(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    value = self._eval(expression.value, env)
    return self._field(value, expression.name)


def _eval_call_expression(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    callee = self._eval(expression.callee, env)
    positional_values = []
    named = {}
    positional_references = []
    named_references = {}
    for item in expression.arguments:
        value = self._eval(item.value, env)
        if item.name is None:
            positional_values.append(value)
            positional_references.append(self.provenance.last)
        else:
            named[item.name] = value
            named_references[item.name] = self.provenance.last
    positional = tuple(positional_values)
    references = CallReferences(tuple(positional_references), named_references)
    expected_term = expression.expected_term
    proof_context = ()
    if expression.proof_bindings:
        from prism.language.developer import reify_runtime_value
        from prism.language.kernel import substitute

        proof_context = tuple(
            (
                name,
                type_,
                reify_runtime_value(
                    positional[0]
                    if isinstance(callee, _Builtin)
                    and callee.name == "verify"
                    and position == 0
                    else self._eval(binding, env),
                    type_.name,
                ),
            )
            for position, (name, binding, type_) in enumerate(expression.proof_bindings)
        )
        for _, _, value in reversed(proof_context):
            expected_term = substitute(expected_term, value)
    if expression.proof_bindings:
        references.named.update(
            {
                f"proof-context:{index}": reference
                for index, (_, reference) in enumerate(self.provenance.evaluations[-1])
            }
        )
    return self._call(
        callee,
        positional,
        named,
        env,
        expression.result_type,
        expected_term,
        proof_context=proof_context,
        references=references,
    )


def _eval_conditional(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    branch = (
        expression.when_true
        if self._eval(expression.condition, env)
        else expression.when_false
    )
    return self._eval(branch, env)


def _eval_index(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    return self._eval(expression.value, env)[self._eval(expression.index, env)]


def _eval_try(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    value = self._eval(expression.value, env)
    if isinstance(value, Err):
        raise _Propagate(value.error)
    if isinstance(value, Ok):
        return value.value
    raise ValueError("runtime `try` received a non-Result value")


def _eval_reasoning_invocation(
    self: _Engine, expression: Any, env: dict[str, Any]
) -> Any:
    callee = self._eval(expression.callee, env)
    if not isinstance(callee, _ReasoningFactory):
        raise ValueError("reasoning invocation did not resolve to reasoning")
    positional = tuple(
        self._eval(argument.value, env)
        for argument in expression.arguments
        if argument.name is None
    )
    named = {
        argument.name: self._eval(argument.value, env)
        for argument in expression.arguments
        if argument.name is not None
    }
    captured = self._bind_arguments(callee.definition.parameters, positional, named)
    if (
        expression.contract is None
        or expression.contract.identity != callee.definition.identity
    ):
        raise ValueError(
            "reasoning invocation is missing its checked declaration identity"
        )
    return ReasoningInvocationValue(
        callee.definition, captured, expression.contract.specialization
    )


def _eval_solve(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    reasoning = (
        self._eval(expression.reasoning, env)
        if expression.reasoning is not None
        else None
    )
    workflow = self._eval(expression.workflow, env)
    return self._solve_reasoning(reasoning, workflow)


def _eval_execute(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    reasoning = (
        self._eval(expression.reasoning, env)
        if expression.reasoning is not None
        else None
    )
    workflow = self._eval(expression.workflow, env)
    value = self._solve_reasoning(reasoning, workflow)
    result = ExecutionValue(value, tuple(event.metadata for event in self.trace))
    self.provenance.record(
        result,
        "computed",
        "execution result",
        (self.provenance.last,),
        children={"result": self.provenance.last},
    )
    return result


def _eval_unary(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    value = self._eval(expression.operand, env)
    return {"not": lambda: not value, "-": lambda: -value, "+": lambda: +value}[
        expression.operator
    ]()


def _eval_binary(self: _Engine, expression: Any, env: dict[str, Any]) -> Any:
    left = self._eval(expression.left, env)
    right = self._eval(expression.right, env)
    return _binary(expression.operator, left, right)


_EVAL_HANDLERS = (
    (Literal, _eval_literal),
    (Reference, _eval_reference),
    (ListValue, _eval_list_value),
    (TupleValue, _eval_tuple_value),
    (MapValue, _eval_map_value),
    (Field, _eval_field),
    (CallExpression, _eval_call_expression),
    (Conditional, _eval_conditional),
    (Index, _eval_index),
    (Try, _eval_try),
    (ReasoningInvocation, _eval_reasoning_invocation),
    (Solve, _eval_solve),
    (Execute, _eval_execute),
    (MaterialInference, _eval_material_inference),
    (Unary, _eval_unary),
    (Binary, _eval_binary),
)
