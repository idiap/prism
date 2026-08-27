# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Pure structural helpers shared by developer checking phases."""

from __future__ import annotations

import re
from typing import Any, Mapping

from prism.language.core import (
    CallableContract,
    CoreType,
)

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
from ..type_syntax import _find_top_level, parse_type


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


def _proposition_type(expression: Expression) -> CoreType:
    return CoreType(_render_expression(expression))


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


def _proposition_arguments(proposition: str) -> tuple[str, ...]:
    """Return canonical top-level arguments from a dependent proposition name."""

    opening = proposition.find("(")
    if opening < 1 or not proposition.endswith(")"):
        return ()
    payload = proposition[opening + 1 : -1]
    arguments: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    for index, character in enumerate(payload):
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
        elif character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif character == "," and depth == 0:
            arguments.append(payload[start:index].strip())
            start = index + 1
    arguments.append(payload[start:].strip())
    return tuple(argument for argument in arguments if argument)


def _dependent_assurance_binding(
    type_: CoreType,
) -> tuple[str, CoreType, CoreType] | None:
    """Return the named value binder from a dependent assurance type."""

    if type_.name not in {"Validated", "Verified"} or len(type_.arguments) != 2:
        return None
    binding, proposition = type_.arguments
    if binding.arguments or binding.is_function:
        return None
    colon = _find_top_level(binding.name, ":")
    if colon < 1:
        return None
    name = binding.name[:colon].strip()
    value_type_text = binding.name[colon + 1 :].strip()
    if not name or not value_type_text:
        return None
    return name, parse_type(value_type_text), proposition


def _dependent_proposition_matches(
    expected: CoreType,
    actual: CoreType,
    binder: str,
) -> bool:
    """Match a proposition whose named value position is existentially bound."""

    expected_opening = expected.name.find("(")
    actual_opening = actual.name.find("(")
    if expected_opening < 1 or actual_opening < 1:
        return False
    if expected.name[:expected_opening] != actual.name[:actual_opening]:
        return False
    expected_arguments = _proposition_arguments(expected.name)
    actual_arguments = _proposition_arguments(actual.name)
    if len(expected_arguments) != len(actual_arguments):
        return False
    return any(argument == binder for argument in expected_arguments) and all(
        expected_argument == binder or expected_argument == actual_argument
        for expected_argument, actual_argument in zip(
            expected_arguments,
            actual_arguments,
            strict=True,
        )
    )


def _is_proposition(type_: CoreType) -> bool:
    return type_.name == "Prop" or type_.name.startswith("forall ") or "(" in type_.name


def _substitute(type_: CoreType, substitutions: Mapping[str, CoreType]) -> CoreType:
    dependent = _dependent_assurance_binding(type_)
    if dependent is not None:
        binder, value_type, proposition = dependent
        substituted_value = _substitute(value_type, substitutions)
        return CoreType(
            type_.name,
            (
                CoreType(f"{binder}: {substituted_value.render()}"),
                _substitute(proposition, substitutions),
            ),
        )
    if type_.name in substitutions and not type_.arguments and not type_.is_function:
        return substitutions[type_.name]
    if "(" in type_.name and not type_.arguments and not type_.is_function:
        proposition = type_.name
        for name, replacement in substitutions.items():
            if replacement.arguments or replacement.is_function:
                continue
            proposition = re.sub(
                rf"\b{re.escape(name)}(?=\s*\()",
                replacement.name,
                proposition,
            )
        return CoreType(proposition)
    if type_.is_function:
        return CoreType(
            type_.name,
            parameters=tuple(
                (name, _substitute(item, substitutions))
                for name, item in type_.parameters
            ),
            result=_substitute(type_.result, substitutions) if type_.result else None,
            effects=type_.effects,
        )
    return CoreType(
        type_.name, tuple(_substitute(item, substitutions) for item in type_.arguments)
    )


def _expand_aliases(
    type_: CoreType,
    aliases: Mapping[str, CoreType],
    type_parameters: Mapping[str, tuple[str, ...]],
    seen: frozenset[str] = frozenset(),
) -> CoreType:
    dependent = _dependent_assurance_binding(type_)
    if dependent is not None:
        binder, value_type, proposition = dependent
        expanded_value = _expand_aliases(value_type, aliases, type_parameters, seen)
        binding_text = type_.arguments[0].name
        colon = _find_top_level(binding_text, ":")
        value_text = binding_text[colon + 1 :]
        spacing = value_text[: len(value_text) - len(value_text.lstrip())]
        return CoreType(
            type_.name,
            (
                CoreType(f"{binder}:{spacing}{expanded_value.render()}"),
                _expand_aliases(proposition, aliases, type_parameters, seen),
            ),
        )
    if "(" in type_.name and not type_.arguments and not type_.is_function:
        base, arguments = type_.name.split("(", 1)
        alias = aliases.get(base)
        if alias is not None and not alias.arguments and not alias.is_function:
            return CoreType(f"{alias.name}({arguments}")
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
    if type_.is_function:
        return CoreType(
            type_.name,
            parameters=tuple(
                (name, _expand_aliases(item, aliases, type_parameters, seen))
                for name, item in type_.parameters
            ),
            result=(
                _expand_aliases(type_.result, aliases, type_parameters, seen)
                if type_.result is not None
                else None
            ),
            effects=type_.effects,
        )
    return CoreType(
        type_.name,
        tuple(
            _expand_aliases(item, aliases, type_parameters, seen)
            for item in type_.arguments
        ),
    )


def _unique_types(types: list[CoreType]) -> tuple[CoreType, ...]:
    result: list[CoreType] = []
    for type_ in types:
        if type_ not in result:
            result.append(type_)
    return tuple(result)


def _binding_value_dependencies(
    expression: Any,
    candidates: set[str],
    *,
    namespace: str | None = None,
) -> tuple[str, ...]:
    """Return top-level values required to evaluate an imported binding."""

    result: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, NodeOccurrence) and value.relation:
            relation_name = value.relation
            if relation_name in candidates:
                result.add(relation_name)
            elif namespace and "." not in relation_name:
                qualified = f"{namespace}.{relation_name}"
                if qualified in candidates:
                    result.add(qualified)
        if isinstance(value, NameExpr):
            if value.name in candidates:
                result.add(value.name)
                return
            qualified = (
                f"{namespace}.{value.name}"
                if namespace and "." not in value.name
                else None
            )
            if qualified in candidates:
                result.add(qualified)
                return
        if not hasattr(value, "__dataclass_fields__"):
            return
        for name in value.__dataclass_fields__:
            item = getattr(value, name)
            if isinstance(item, tuple):
                for child in item:
                    walk(getattr(child, "value", child))
            elif hasattr(item, "__dataclass_fields__"):
                walk(item)

    walk(expression)
    return tuple(sorted(result))
