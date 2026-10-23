# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Pure structural helpers shared by developer checking phases."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from prism.language.core import (
    CallableContract,
    CoreType,
)
from prism.language.core import substitute_type as _substitute

from ..syntax.ast import (
    BinaryExpr,
    CallExpr,
    ChoiceComposition,
    ConditionalExpr,
    Expression,
    FieldExpr,
    IndexExpr,
    LiteralExpr,
    NameExpr,
    NodeOccurrence,
    ParallelComposition,
    RepeatComposition,
    SequenceComposition,
)
from .dependencies import _binding_value_dependencies as _binding_value_dependencies


def _expression_name(expression: Expression) -> str:
    if isinstance(expression, NameExpr):
        return expression.name
    if isinstance(expression, FieldExpr):
        return f"{_expression_name(expression.value)}.{expression.field}"
    return "<expression>"


def _expression_references(expression: Expression) -> tuple[str, ...]:
    found: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, NameExpr):
            found.append(value.name)
            return
        fields = getattr(value, "__dataclass_fields__", None)
        if fields is not None:
            for field_name in fields:
                if field_name == "span":
                    continue
                visit(getattr(value, field_name))
        elif isinstance(value, tuple | list):
            for item in value:
                visit(item)

    visit(expression)
    return tuple(dict.fromkeys(found))


def _expression_values(expression: Expression) -> tuple[Expression, ...]:
    found: list[Expression] = []

    def visit(value: Any) -> None:
        if isinstance(value, Expression):
            found.append(value)
        fields = getattr(value, "__dataclass_fields__", None)
        if fields is not None:
            for field_name in fields:
                if field_name != "span":
                    visit(getattr(value, field_name))
        elif isinstance(value, tuple | list):
            for item in value:
                visit(item)

    visit(expression)
    return tuple(found)


def _agent_call_effects(
    value: Any, callables: Mapping[str, CallableContract]
) -> set[str]:
    effects: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, CallExpr):
            contract = callables.get(_expression_name(item.callee))
            if contract is not None and contract.kind == "agent":
                effects.update(contract.effects)
        fields = getattr(item, "__dataclass_fields__", None)
        if fields is not None:
            for field_name in fields:
                if field_name != "span":
                    visit(getattr(item, field_name))
        elif isinstance(item, tuple | list):
            for child in item:
                visit(child)

    visit(value)
    return effects


def _contains_type_name(type_: CoreType, names: set[str]) -> bool:
    if type_.name in names:
        return True
    return any(_contains_type_name(item, names) for item in type_.arguments) or any(
        _contains_type_name(item, names) for _, item in type_.parameters
    )


def _composition_aliases(
    composition: Any, *, terminal_only: bool = False
) -> tuple[str, ...]:
    if isinstance(composition, NodeOccurrence):
        return (composition.alias,) if composition.alias else ()
    if isinstance(composition, SequenceComposition | RepeatComposition):
        children = composition.children[-1:] if terminal_only else composition.children
        return tuple(
            alias
            for child in children
            for alias in _composition_aliases(child, terminal_only=terminal_only)
        )
    if isinstance(composition, ParallelComposition):
        return tuple(
            alias
            for child in composition.children
            for alias in _composition_aliases(child, terminal_only=terminal_only)
        )
    if isinstance(composition, ChoiceComposition):
        values = list(_composition_aliases(composition.router))
        for arm in composition.arms:
            children = arm.children[-1:] if terminal_only else arm.children
            for child in children:
                values.extend(_composition_aliases(child, terminal_only=terminal_only))
        return tuple(dict.fromkeys(values))
    return ()


def _composition_nodes(composition: Any) -> tuple[NodeOccurrence, ...]:
    if isinstance(composition, NodeOccurrence):
        return (composition,)
    if isinstance(
        composition, SequenceComposition | ParallelComposition | RepeatComposition
    ):
        return tuple(
            node for child in composition.children for node in _composition_nodes(child)
        )
    if isinstance(composition, ChoiceComposition):
        return (
            composition.router,
            *tuple(
                node
                for arm in composition.arms
                for child in arm.children
                for node in _composition_nodes(child)
            ),
        )
    return ()


def _implementation_shape(
    type_: CoreType,
) -> tuple[CoreType | None, CoreType | None, tuple[str, ...]]:
    if not type_.is_function:
        return None, None, ()
    result = type_.result or CoreType("Unit")
    effects = list(type_.effects)
    failure: CoreType | None = None
    if result.name == "Workflow" and len(result.arguments) >= 2:
        success, failure = result.arguments[:2]
        effects.extend(item.name for item in result.arguments[2:])
        return success, failure, tuple(dict.fromkeys(effects))
    if result.name == "Result" and len(result.arguments) == 2:
        return result.arguments[0], result.arguments[1], tuple(effects)
    return result, failure, tuple(effects)


def _failure_union(failures: list[CoreType]) -> CoreType:
    unique = _unique_types([item for item in failures if item.name != "Never"])
    if not unique:
        return CoreType("Never")
    if len(unique) == 1:
        return unique[0]
    return CoreType("FailureUnion", unique)


def _render_expression(expression: Expression) -> str:
    if isinstance(expression, NameExpr):
        return expression.name
    if isinstance(expression, LiteralExpr):
        return repr(expression.value)
    if isinstance(expression, FieldExpr):
        return f"{_render_expression(expression.value)}.{expression.field}"
    if isinstance(expression, CallExpr):
        args = ", ".join(
            (
                f"{arg.name} = {_render_expression(arg.value)}"
                if arg.name
                else _render_expression(arg.value)
            )
            for arg in expression.arguments
        )
        type_arguments = (
            "[" + ", ".join(item.text for item in expression.type_arguments) + "]"
            if expression.type_arguments
            else ""
        )
        return f"{_render_expression(expression.callee)}{type_arguments}({args})"
    if isinstance(expression, BinaryExpr):
        return (
            f"({_render_expression(expression.left)} {expression.operator} "
            f"{_render_expression(expression.right)})"
        )
    if isinstance(expression, ConditionalExpr):
        return (
            f"({_render_expression(expression.when_true)} if "
            f"{_render_expression(expression.condition)} else "
            f"{_render_expression(expression.when_false)})"
        )
    if isinstance(expression, IndexExpr):
        return (
            f"{_render_expression(expression.value)}"
            f"[{_render_expression(expression.index)}]"
        )
    return type(expression).__name__


def _dependent_assurance_binding(
    type_: CoreType,
) -> tuple[str, CoreType, CoreType] | None:
    if (
        type_.name not in {"Validated", "Verified", "Validator"}
        or len(type_.arguments) != 2
    ):
        return None
    binding, proposition = type_.arguments
    if binding.binder is None:
        return None
    return binding.binder, binding.arguments[0], proposition


def _dependent_proposition_matches(
    expected: CoreType,
    actual: CoreType,
    binder: str,
) -> bool:
    """Instantiate the existential binder consistently throughout its claim."""
    if expected.proposition is None or actual.proposition is None:
        return expected == actual
    bindings = {}

    def matches(left, right):
        if left.kind == "reference" and left.symbol == binder:
            previous = bindings.setdefault(binder, right)
            return previous == right
        return (
            left.kind == right.kind
            and left.symbol == right.symbol
            and left.argument_names == right.argument_names
            and left.type_arguments == right.type_arguments
            and len(left.children) == len(right.children)
            and all(
                matches(a, b)
                for a, b in zip(left.children, right.children, strict=True)
            )
        )

    return matches(expected.proposition, actual.proposition)


def _is_proposition(type_: CoreType) -> bool:
    return type_.name == "Prop" or type_.proposition is not None


def _expand_aliases(
    type_: CoreType,
    aliases: Mapping[str, CoreType],
    type_parameters: Mapping[str, tuple[str, ...]],
    seen: frozenset[str] = frozenset(),
) -> CoreType:
    if type_.name in aliases and type_.name not in seen:
        parameters = type_parameters.get(type_.name, ())
        if len(parameters) == len(type_.arguments):
            expanded = _substitute(
                aliases[type_.name],
                dict(zip(parameters, type_.arguments, strict=True)),
            )
            return _expand_aliases(
                expanded,
                aliases,
                type_parameters,
                seen | {type_.name},
            )
    return replace(
        type_,
        arguments=tuple(
            _expand_aliases(item, aliases, type_parameters, seen)
            for item in type_.arguments
        ),
        parameters=tuple(
            (name, _expand_aliases(item, aliases, type_parameters, seen))
            for name, item in type_.parameters
        ),
        result=_expand_aliases(type_.result, aliases, type_parameters, seen)
        if type_.result
        else None,
    )


def _unique_types(types: list[CoreType]) -> tuple[CoreType, ...]:
    result: list[CoreType] = []
    for type_ in types:
        if type_ not in result:
            result.append(type_)
    return tuple(result)


def _substitute_indices(type_: CoreType, bindings) -> CoreType:
    """Substitute resolved value bindings without touching similarly named symbols."""
    return replace(
        type_,
        proposition=type_.proposition.substitute(bindings)
        if type_.proposition
        else None,
        arguments=tuple(
            _substitute_indices(item, bindings) for item in type_.arguments
        ),
        parameters=tuple(
            (name, _substitute_indices(item, bindings))
            for name, item in type_.parameters
        ),
        result=_substitute_indices(type_.result, bindings) if type_.result else None,
    )


def _index_symbols(type_: CoreType) -> set[str]:
    def symbols(index):
        return ({index.symbol} if index.kind == "reference" else set()).union(
            *(symbols(child) for child in index.children)
        )

    result = symbols(type_.proposition) if type_.proposition else set()
    for item in (*type_.arguments, *(value for _, value in type_.parameters)):
        result.update(_index_symbols(item))
    if type_.result:
        result.update(_index_symbols(type_.result))
    return result
