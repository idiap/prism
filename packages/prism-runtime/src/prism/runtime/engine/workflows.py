# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workflow composition, iteration, and guarded exits."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from prism.language.core import (
    Err,
    Ok,
    RefinementPolicyValue,
)
from prism.language.workflows import (
    Choice,
    ExecutionScope,
    ExecutionScopeKind,
    NodeOccurrence,
    Parallel,
    Repeat,
    Sequence,
)
from prism.runtime.results import TraceEvent

from .components import _component_parameter_names
from .composition import (
    _choice_matches,
    _composition_nodes,
    _composition_terminals,
    _ir_name,
)
from .provenance import CallReferences, ValueEnvironment
from .values import (
    ReasoningInvocationValue,
    ReasoningStoppedValue,
    WorkflowValue,
    _Propagate,
    _ReasoningExitSignal,
    _value_status,
)

if TYPE_CHECKING:
    from .execution import _Engine


def _solve_reasoning(
    self: _Engine,
    reasoning: ReasoningInvocationValue | None,
    workflow: Any,
) -> Any:
    if not isinstance(workflow, WorkflowValue):
        raise ValueError("runtime resolution received a non-workflow value")
    if reasoning is None:
        result, _ = self._execute_workflow(workflow)
        return result
    materialized = workflow.invocation
    if (
        materialized is None
        or materialized.definition.identity != reasoning.definition.identity
    ):
        raise ValueError(
            f"workflow `{workflow.definition.name}` does not materialize reasoning `{reasoning.definition.name}`"
        )
    if materialized.specialization != reasoning.specialization:
        raise ValueError("reasoning invocation has a different type specialization")
    if not _logical_values_equal(dict(materialized.captured), dict(reasoning.captured)):
        raise ValueError("reasoning invocation has different logical arguments")
    self.trace.append(TraceEvent("reasoning-started", reasoning.definition.name))
    result, _ = self._execute_workflow(workflow)
    self.trace.append(
        TraceEvent(
            "reasoning-resolved",
            reasoning.definition.name,
            status=_value_status(result),
        )
    )
    return result


def _execute_workflow(self: _Engine, workflow: Any) -> tuple[Any, dict[str, Any]]:
    if not isinstance(workflow, WorkflowValue):
        raise ValueError("runtime resolution received a non-workflow value")

    definition = workflow.definition
    self.workflow_counter += 1
    invocation_id = f"{self.run_id}/workflow:{self.workflow_counter}"
    parent_invocation = (
        self._workflow_invocation_stack[-1] if self._workflow_invocation_stack else None
    )
    workflow_scope = ExecutionScope(ExecutionScopeKind.WORKFLOW, definition.name)
    self.trace.append(
        TraceEvent(
            "workflow-call",
            definition.name,
            metadata={
                "effects": definition.effects,
                "invocation_id": invocation_id,
                "parent_invocation_id": parent_invocation,
                "run_id": self.run_id,
            },
        )
    )
    self._scope_stack.append(workflow_scope)
    self._workflow_definition_stack.append(definition)
    self._workflow_invocation_stack.append(invocation_id)
    environment = ValueEnvironment(self.global_env, workflow.captured)
    outputs: dict[str, Any] = {}
    result: Any = None
    try:
        self._execute_composition(
            definition.composition,
            environment,
            outputs,
            definition.name,
        )
        alias = definition.result_alias
        if alias is None:
            terminals = _composition_terminals(definition.composition)
            if len(terminals) != 1:
                raise ValueError(
                    f"workflow `{definition.name}` has no unique terminal output"
                )
            alias = terminals[0]
        result = outputs[alias]
        self.provenance.last = environment.references.get(alias)
        if definition.failure_type.name != "Never":
            result = Ok(result)
            self.provenance.record(
                result,
                "computed",
                "workflow result",
                (self.provenance.last,),
                children={"value": self.provenance.last},
            )
    except _ReasoningExitSignal as signal:
        result = _workflow_exit_result(self, workflow, signal, environment)
    except _Propagate as signal:
        result = Err(signal.error)
        self.provenance.record(
            result, "computed", "workflow failure", (self.provenance.last,)
        )
    finally:
        self._scope_stack.pop()
        self._workflow_definition_stack.pop()
        self._workflow_invocation_stack.pop()
    return result, outputs


def _execute_reasoning_switch(
    self: _Engine,
    switches: Any,
    signal: _ReasoningExitSignal,
    environment: Mapping[str, Any],
) -> Any:
    target_name = (signal.target or "").rsplit(".", 1)[-1]
    target = switches.get(target_name) if isinstance(switches, Mapping) else None
    if target is None:
        raise ValueError(f"reasoning switch `{target_name}` has no materialized target")
    parameter_names = _component_parameter_names(target)
    required_names = parameter_names[1:]
    missing = [name for name in required_names if name not in environment]
    if missing:
        raise ValueError(
            f"reasoning switch `{target_name}` is missing inputs: " + ", ".join(missing)
        )
    target_result = self._call(
        target,
        (signal.value,),
        {name: environment[name] for name in required_names},
        environment,
        references=CallReferences(
            (environment.references[signal.occurrence],),
            {
                name: environment.references[name]
                for name in required_names
                if name in environment.references
            },
        )
        if isinstance(environment, ValueEnvironment)
        else None,
    )
    if isinstance(target_result, WorkflowValue):
        target_result, _ = self._execute_workflow(target_result)
    return target_result


def _execute_composition(
    self: _Engine,
    composition: Any,
    environment: dict[str, Any],
    outputs: dict[str, Any],
    workflow_id: str,
) -> None:
    if isinstance(composition, NodeOccurrence):
        self._execute_workflow_node(composition, environment, outputs, workflow_id)
    elif isinstance(composition, Sequence):
        for child in composition.children:
            self._execute_composition(child, environment, outputs, workflow_id)
    elif isinstance(composition, Parallel):
        _execute_parallel(self, composition, environment, outputs, workflow_id)
    elif isinstance(composition, Choice):
        _execute_choice(self, composition, environment, outputs, workflow_id)
    elif isinstance(composition, Repeat):
        _execute_repeat(self, composition, environment, outputs, workflow_id)
    else:
        raise TypeError(
            f"unsupported workflow composition `{type(composition).__name__}`"
        )


def _execute_parallel(
    self: _Engine,
    composition: Any,
    environment: dict[str, Any],
    outputs: dict[str, Any],
    workflow_id: str,
) -> None:
    branch_values: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for child in composition.children:
        branch_environment = ValueEnvironment(environment)
        branch_outputs = dict(outputs)
        self._execute_composition(
            child, branch_environment, branch_outputs, workflow_id
        )
        branch_values.append((branch_environment, branch_outputs))
    for branch_environment, branch_outputs in branch_values:
        environment.update(
            {
                name: value
                for name, value in branch_environment.items()
                if name not in self.global_env
            }
        )
        if isinstance(environment, ValueEnvironment):
            environment.references.update(getattr(branch_environment, "references", {}))
        outputs.update(branch_outputs)
    return


def _execute_choice(
    self: _Engine,
    composition: Any,
    environment: dict[str, Any],
    outputs: dict[str, Any],
    workflow_id: str,
) -> None:
    self._execute_workflow_node(composition.router, environment, outputs, workflow_id)
    router_alias = (
        composition.router.alias
        or _ir_name(composition.router.component).rsplit(".", 1)[-1]
    )
    router_value = outputs[router_alias]
    arm = next(
        (
            candidate
            for candidate in composition.arms
            if _choice_matches(candidate.pattern, router_value)
        ),
        None,
    )
    if arm is None:
        raise ValueError(
            f"workflow choice has no case for `{type(router_value).__name__}`"
        )
    control = (
        environment.references[router_alias]
        if isinstance(environment, ValueEnvironment)
        else None
    )
    if control is not None:
        self.provenance.controls.append(control)
    try:
        for child in arm.children:
            self._execute_composition(child, environment, outputs, workflow_id)
    finally:
        if control is not None:
            self.provenance.controls.pop()
    return


def _execute_repeat(
    self: _Engine,
    composition: Any,
    environment: dict[str, Any],
    outputs: dict[str, Any],
    workflow_id: str,
) -> None:
    policy = self._eval(composition.policy, environment)
    policy_reference = self.provenance.last
    if not isinstance(policy, RefinementPolicyValue):
        raise ValueError("repeat policy is not a RefinementPolicy")
    for _ in range(policy.max_attempts):
        for child in composition.children:
            _execute_repeat_child(self, child, environment, outputs, workflow_id)
        terminal_reference = None
        terminal_value = False
        if composition.until is not None:
            terminal_value = self._eval(composition.until, environment)
            if not isinstance(terminal_value, bool):
                raise ValueError("repeat terminal condition must evaluate to Bool")
            terminal_reference = self.provenance.last
        _retain_repeat_control(
            self, composition, environment, (policy_reference, terminal_reference)
        )
        if terminal_value:
            break
    return


def _retain_repeat_control(self, composition, environment, references):
    if not isinstance(environment, ValueEnvironment):
        return
    for node in _composition_nodes(composition):
        alias = node.alias or _ir_name(node.component).rsplit(".", 1)[-1]
        if alias in environment.references:
            environment.references[alias] = self.provenance.select(
                environment.references[alias], references
            )


def _execute_repeat_child(
    self: _Engine,
    child: Any,
    environment: dict[str, Any],
    outputs: dict[str, Any],
    workflow_id: str,
) -> None:
    try:
        self._execute_composition(child, environment, outputs, workflow_id)
    except _ReasoningExitSignal as signal:
        if signal.action != "switch":
            raise
        switched = self._execute_reasoning_switch(
            environment.get("switches", {}), signal, environment
        )
        if isinstance(switched, Err):
            raise _Propagate(switched.error)
        if isinstance(switched, Ok):
            switched = switched.value
            self.provenance.project(self.provenance.last, "value", switched)
        outputs[signal.occurrence] = switched
        environment[signal.occurrence] = switched
        if (
            isinstance(environment, ValueEnvironment)
            and self.provenance.last is not None
        ):
            environment.references[signal.occurrence] = self.provenance.last


def _workflow_exit_result(
    self: _Engine,
    workflow: WorkflowValue,
    signal: _ReasoningExitSignal,
    environment: Mapping[str, Any],
) -> Any:
    definition = workflow.definition
    if signal.action == "accept":
        result = signal.value
        self.provenance.last = getattr(environment, "references", {}).get(
            signal.occurrence
        )
        if definition.failure_type.name != "Never":
            result = Ok(result)
            self.provenance.record(
                result,
                "computed",
                "workflow exit",
                (self.provenance.last,),
                children={"value": self.provenance.last},
            )
    elif signal.action == "stop":
        result = Err(
            ReasoningStoppedValue(
                definition.abstract_name or definition.name,
                signal.occurrence,
                signal.selector,
            )
        )
    else:
        result = self._execute_reasoning_switch(
            workflow.captured.get("switches", {}), signal, environment
        )
        if definition.failure_type.name != "Never" and not isinstance(result, Ok | Err):
            result = Ok(result)
            self.provenance.record(
                result,
                "computed",
                "workflow exit",
                (self.provenance.last,),
                children={"value": self.provenance.last},
            )
    if signal.action == "stop":
        self.provenance.record(
            result, "computed", "workflow stopped", (self.provenance.last,)
        )
    return result


def _logical_values_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return left.keys() == right.keys() and all(
            _logical_values_equal(value, right[name]) for name, value in left.items()
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _logical_values_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right
