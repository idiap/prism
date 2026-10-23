# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Runtime callable names and type contracts."""

from __future__ import annotations

from typing import Any

from prism.language.core import (
    CoreType,
)

from .values import (
    _AgentCallable,
    _Builtin,
    _Callable,
    _ConfiguredReasoning,
    _WorkflowFactory,
)


def _component_parameter_names(component: Any) -> tuple[str, ...]:
    if isinstance(component, _Callable):
        return tuple(name for name, _ in component.definition.parameters)
    if isinstance(component, _WorkflowFactory):
        return tuple(name for name, _ in component.definition.parameters)
    if isinstance(component, _AgentCallable):
        return tuple(name for name, _ in component.definition.parameters)
    if isinstance(component, _ConfiguredReasoning):
        parameters = (
            component.invocation_type.parameters
            if component.invocation_type is not None
            and component.invocation_type.is_function
            else component.definition.parameters
        )
        return tuple(name or "" for name, _ in parameters)
    raise TypeError(
        f"runtime workflow component `{type(component).__name__}` is not callable"
    )


def _component_result_type(component: Any) -> CoreType | None:
    if isinstance(component, _Callable | _AgentCallable):
        return component.definition.result_type
    if isinstance(component, _ConfiguredReasoning):
        return component.invocation_type.result if component.invocation_type else None
    if isinstance(component, _WorkflowFactory):
        return CoreType(
            "Workflow",
            (component.definition.result_type, component.definition.failure_type),
        )
    return None


def _component_contract_type(component: Any) -> CoreType | None:
    if isinstance(component, _ConfiguredReasoning):
        return component.invocation_type
    if isinstance(component, _Callable | _AgentCallable):
        return CoreType(
            "Function",
            parameters=component.definition.parameters,
            result=component.definition.result_type,
            effects=component.definition.effects,
        )
    if isinstance(component, _WorkflowFactory):
        return CoreType(
            "Function",
            parameters=component.definition.parameters,
            result=CoreType(
                "Workflow",
                (
                    component.definition.result_type,
                    component.definition.failure_type,
                    *(CoreType(effect) for effect in component.definition.effects),
                ),
            ),
        )
    return None


def _component_behavior(component: Any) -> tuple[CoreType, tuple[str, ...]]:
    if isinstance(component, _WorkflowFactory):
        return component.definition.failure_type, component.definition.effects
    if isinstance(component, _ConfiguredReasoning):
        result = _component_result_type(component)
        if result is not None and result.name == "Workflow":
            return result.arguments[1], tuple(
                item.name for item in result.arguments[2:]
            )
    if isinstance(component, _Callable | _AgentCallable):
        result = component.definition.result_type
        failure = (
            result.arguments[1]
            if result.name == "Result" and len(result.arguments) == 2
            else CoreType("Never")
        )
        return failure, component.definition.effects
    return CoreType("Never"), ()


def _runtime_callable_name(component: Any) -> str:
    if isinstance(component, _Callable):
        return component.definition.name
    if isinstance(component, _WorkflowFactory):
        return component.definition.name
    if isinstance(component, _Builtin):
        return component.name
    return type(component).__name__
