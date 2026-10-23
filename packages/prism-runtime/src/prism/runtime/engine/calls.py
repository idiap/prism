# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Function invocation, argument binding, and callable dispatch."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Mapping

from prism.language.core import (
    CoreType,
    Err,
    RecordValue,
)
from prism.language.effects import (
    FunctionDefinition,
)
from prism.language.kernel import (
    Term,
)
from prism.runtime.results import TraceEvent

from .agents import _call_agent
from .provenance import CallReferences, ValueEnvironment
from .reasoning import _reasoning_configuration_names
from .values import (
    ClaimValue,
    ToolValue,
    WorkflowValue,
    _AgentCallable,
    _Builtin,
    _Callable,
    _ConfiguredReasoning,
    _Propagate,
    _ReasoningFactory,
    _RecordFactory,
    _ReturnSignal,
    _WorkflowFactory,
)

if TYPE_CHECKING:
    from .execution import _Engine


def _invoke_function(
    self: _Engine,
    definition: FunctionDefinition,
    arguments: tuple[Any, ...],
    named: Mapping[str, Any],
) -> Any:
    values = self._bind_arguments(definition.parameters, arguments, named)
    if definition.result_type.name == "Prop":
        subjects = ", ".join(f"{name}={value!r}" for name, value in values.items())
        value = ClaimValue(
            f"{definition.name}({subjects})",
            definition.identity or definition.name,
            tuple(values.values()),
        )
        reference = self.provenance.record(
            value,
            "computed",
            "claim application",
            values.references.values(),
            children={
                f"argument:{index}": reference
                for index, reference in enumerate(values.references.values())
            },
        )
        if self.provenance.current_call is not None:
            self.provenance.current_call.function_result = reference
        return value
    env = ValueEnvironment(self.global_env, values)
    self.trace.append(
        TraceEvent(
            "function-call",
            definition.name,
            metadata={"effects": definition.effects},
        )
    )
    result: Any = None
    result_reference = None
    try:
        self._execute_statements(definition.body, env)
    except _ReturnSignal as signal:
        result = signal.value
        result_reference = self.provenance.last
    except _Propagate as signal:
        result = Err(signal.error)
        result_reference = self.provenance.record(
            result, "computed", "function failure", (self.provenance.last,)
        )
    self.provenance.last = result_reference or self.provenance.record(
        result, "computed", "implicit Unit"
    )
    if self.provenance.current_call is not None:
        self.provenance.current_call.function_result = self.provenance.last
    return result


def _call(
    self: _Engine,
    callee,
    positional,
    named,
    env,
    result_type=None,
    expected_term=None,
    *,
    proof_context=(),
    references=None,
):
    if references is None:
        references = CallReferences(
            tuple(
                self.provenance.record(value, "external_unknown", "internal argument")
                for value in positional
            ),
            {
                name: getattr(env, "references", {}).get(name)
                or self.provenance.record(
                    value, "external_unknown", f"internal argument:{name}"
                )
                for name, value in named.items()
            },
        )
    self.provenance.calls.append(references)
    try:
        value = _dispatch_call(
            self,
            callee,
            positional,
            named,
            env,
            result_type,
            expected_term,
            proof_context=proof_context,
        )
        _call_result_reference(self, callee, value, references)
        references.implementation = callee
        self.provenance.last_invocation = (positional, named, references)
        return value
    finally:
        self.provenance.calls.pop()


def _call_result_reference(self, callee, value, references):
    if (
        isinstance(callee, _Callable | ToolValue)
        and references.function_result is not None
    ):
        self.provenance.last = references.function_result
        return
    if references.result_reference is not None:
        self.provenance.last = references.result_reference
        return
    name = callee.name if isinstance(callee, _Builtin) else type(callee).__name__
    children = _builtin_result_children(self, name, value, references)
    if isinstance(callee, _RecordFactory):
        children = references.named
    self.provenance.record(
        value,
        "computed",
        name,
        (*references.inputs, references.function_result),
        children=children,
    )


def _dispatch_call(
    self: _Engine,
    callee: Any,
    positional: tuple[Any, ...],
    named: Mapping[str, Any],
    env: Mapping[str, Any],
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
    *,
    proof_context=(),
) -> Any:
    if isinstance(callee, _RecordFactory):
        fields = {name: value for name, value in named.items()}
        return RecordValue(callee.definition.name, fields)
    if isinstance(callee, _AgentCallable):
        return _call_agent(
            self, callee, positional, named, env, result_type, expected_term
        )
    if isinstance(callee, ToolValue):
        return _dispatch_call(
            self,
            callee.callable,
            positional,
            named,
            env,
            result_type,
            expected_term,
        )
    if isinstance(callee, _Callable):
        return _invoke_callable(self, callee, positional, named, result_type)
    if isinstance(callee, _WorkflowFactory):
        values = self._bind_arguments(callee.definition.parameters, positional, named)
        return WorkflowValue(callee.definition, values)
    if isinstance(callee, _ConfiguredReasoning):
        return _invoke_configured_reasoning(
            self, callee, positional, named, result_type
        )
    if isinstance(callee, _ReasoningFactory):
        return _configure_reasoning(
            self, callee, positional, named, env, result_type, expected_term
        )
    if isinstance(callee, _Builtin):
        return self._call_builtin(
            callee.name,
            positional,
            named,
            result_type,
            expected_term,
            proof_context=proof_context,
        )
    raise TypeError(f"runtime value `{type(callee).__name__}` is not callable")


def _invoke_callable(self, callee, positional, named, result_type):
    value = self._invoke_function(callee.definition, positional, named)
    if (
        isinstance(value, ClaimValue)
        and result_type is not None
        and result_type.proposition is not None
    ):
        return replace(value, specialization=result_type.proposition.type_arguments)
    return value


def _invoke_configured_reasoning(self, callee, positional, named, result_type):
    invocation_parameters = (
        callee.invocation_type.parameters
        if callee.invocation_type is not None and callee.invocation_type.is_function
        else callee.definition.parameters
    )
    values = self._bind_arguments(
        invocation_parameters,
        positional,
        named,
    )
    configured_type = callee.invocation_type.result if callee.invocation_type else None
    workflow_type = result_type or configured_type
    if (
        workflow_type is not None
        and workflow_type.invocation is None
        and configured_type is not None
    ):
        workflow_type = replace(workflow_type, invocation=configured_type.invocation)
    return self._materialize_reasoning(
        callee.definition, callee.bindings, values, workflow_type
    )


def _bind_arguments(self: _Engine, parameters, positional, named) -> ValueEnvironment:
    values = ValueEnvironment()
    references = self.provenance.current_call
    for index, ((name, _), value) in enumerate(
        zip(parameters[: len(positional)], positional, strict=True)
    ):
        reference = (
            references.positional[index]
            if references is not None and index < len(references.positional)
            else self.provenance.record(value, "supplied", f"input:{name}")
        )
        values.bind(name, value, reference)
    for name, value in named.items():
        reference = references.named.get(name) if references is not None else None
        values.bind(
            name,
            value,
            reference or self.provenance.record(value, "supplied", f"input:{name}"),
        )
    return values


def _configure_reasoning(
    self: _Engine,
    callee: Any,
    positional: tuple[Any, ...],
    named: Mapping[str, Any],
    env: Mapping[str, Any],
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    configuration_names = _reasoning_configuration_names(callee.definition)
    if set(named) == set(configuration_names) and not positional:
        bindings = self._reasoning_configuration_bindings(
            callee.definition,
            named,
        )
        return _ConfiguredReasoning(
            callee.definition,
            bindings,
            result_type,
        )
    raise ValueError(
        f"reasoning `{callee.definition.name}` must be configured with "
        "its complete named occurrence and relation bindings before invocation"
    )


def _builtin_result_children(self, name, value, references):
    from prism.language.core import Ok

    inputs = references.positional
    if name in {"Ok", "Err"} and inputs:
        return {"value" if name == "Ok" else "error": inputs[0]}
    if name == "verify" and inputs:
        return {"value": inputs[0], "proof": inputs[1]}
    if name == "accept_support" and isinstance(value, Ok):
        assessment = inputs[0]
        children = {
            "assessment": assessment,
            **dict(self.provenance.values[assessment].children),
        }
        supported = self.provenance.record(
            value.value,
            "computed",
            "accepted support",
            references.inputs,
            children=children,
        )
        return {"value": supported}
    if name == "material_policy":
        return dict(references.named)
    if name == "validate" and isinstance(value, Ok):
        validated = self.provenance.record(
            value.value,
            "computed",
            "validation",
            (*references.inputs, references.function_result),
            children={"value": inputs[0]},
        )
        return {"value": validated}
    return None
