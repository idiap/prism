# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workflow occurrence execution and relation tracing."""

from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from prism.language.core import (
    Err,
    Ok,
)
from prism.language.effects import (
    CallExpression,
)
from prism.language.workflows import (
    ExecutionScope,
    ExecutionScopeKind,
    NodeOccurrence,
)
from prism.runtime.results import OccurrenceOutcome, TraceEvent

from .components import (
    _component_behavior,
    _component_contract_type,
    _component_parameter_names,
    _component_result_type,
)
from .composition import _disposition_matches, _ir_name
from .materializers import check_input_adapter, check_materializer
from .occurrences import check_requirements
from .outcomes import observed_values
from .provenance import CallReferences, ValueEnvironment
from .relations import _trace_relation
from .values import (
    WorkflowValue,
    _Propagate,
    _ReasoningExitSignal,
    _value_status,
)

if TYPE_CHECKING:
    from .execution import _Engine


def _execute_workflow_node(
    self: _Engine,
    node: NodeOccurrence,
    environment: dict[str, Any],
    outputs: dict[str, Any],
    workflow_id: str,
) -> None:
    component_name = _ir_name(node.component)
    alias = node.alias or component_name.rsplit(".", 1)[-1]
    occurrence_id = f"{workflow_id}.{alias}"
    self.occurrence_counter += 1
    instance_id = f"{self.run_id}/occurrence:{self.occurrence_counter}"
    node_scope = ExecutionScope(ExecutionScopeKind.WORKFLOW, occurrence_id)
    node_metadata = dict(
        workflow_id=workflow_id,
        component=component_name,
        occurrence_instance_id=instance_id,
        source_occurrence_id=node.contract.identity,
        invocation_id=self._workflow_invocation_stack[-1],
        run_id=self.run_id,
        declared_contract=asdict(node.contract),
    )
    node_trace_index = len(self.trace)
    self.trace.append(
        TraceEvent(
            "workflow-node",
            alias,
            metadata=node_metadata,
            outcome=OccurrenceOutcome(),
        )
    )
    self._scope_stack.append(node_scope)
    self._workflow_node_stack.append((workflow_id, alias, node_scope))
    result: Any = None
    try:
        component, input_adapter, component_reference, component_invocation = (
            _prepare_node(
                self, node, environment, node_metadata, workflow_id, component_name
            )
        )
        check_materializer(self, node, component)
        check_input_adapter(self, node, input_adapter)
        result, reasoning_input, input_reference = _invoke_node(
            self, node, component, input_adapter, alias, environment
        )
        if isinstance(node.component, CallExpression):
            self.provenance.last = component_reference
            reasoning_input, input_reference = _ordinary_node_input(
                self, component_invocation
            )
            check_requirements(
                self, node.contract.input_requirements, reasoning_input, input_reference
            )
            self.provenance.last = component_reference
        if isinstance(result, WorkflowValue):
            result, _ = self._execute_workflow(result)
        assert self.provenance.last is not None
        result_reference = self.provenance.select(
            self.provenance.last, self.provenance.controls
        )
        self.trace[node_trace_index] = TraceEvent(
            "workflow-node",
            alias,
            status=_value_status(result),
            outcome=OccurrenceOutcome(
                execution="failed" if isinstance(result, Err) else "completed",
                observed=observed_values(self.provenance, result, result_reference),
            ),
            metadata={
                **node_metadata,
                "result": result,
                "output_reference": result_reference,
                "input_reference": input_reference,
            },
        )
        if isinstance(result, Err):
            raise _Propagate(result.error)
        if isinstance(result, Ok):
            result = result.value
            result_reference = self.provenance.project(
                result_reference, "value", result
            )
        check_requirements(self, node.contract.requirements, result, result_reference)
        _trace_relation(
            self,
            node,
            alias,
            reasoning_input,
            result,
            environment,
            source_reference=input_reference,
            target_reference=result_reference,
            occurrence_instance_id=instance_id,
        )
        event = self.trace[node_trace_index]
        assert event.outcome is not None
        self.trace[node_trace_index] = replace(
            event, outcome=replace(event.outcome, contract="satisfied")
        )
        outputs[alias] = result
        environment[alias] = result
        if isinstance(environment, ValueEnvironment) and result_reference is not None:
            environment.references[alias] = result_reference
        self.provenance.last = result_reference
        _check_guarded_exits(self, alias, result)
    except (_Propagate, ValueError, TypeError) as exc:
        event = self.trace[node_trace_index]
        outcome = event.outcome or OccurrenceOutcome()
        self.trace[node_trace_index] = replace(
            event,
            status="rejected",
            metadata={**event.metadata, "error": str(exc)},
            outcome=replace(
                outcome,
                execution="failed"
                if outcome.execution == "running"
                else outcome.execution,
                contract="rejected",
            ),
        )
        raise
    except _ReasoningExitSignal:
        raise
    finally:
        self._workflow_node_stack.pop()
        self._scope_stack.pop()


def _prepare_node(self, node, environment, metadata, workflow_id, component_name):
    component = self._eval(node.component, environment)
    reference = self.provenance.last
    invocation = self.provenance.last_invocation
    adapter = (
        self._eval(node.input_adapter, environment)
        if node.input_adapter is not None
        else None
    )
    implementation = (
        invocation[2].implementation
        if isinstance(node.component, CallExpression) and invocation is not None
        else component
    )
    metadata.update(
        _node_metadata(self, node, implementation, adapter, workflow_id, component_name)
    )
    return component, adapter, reference, invocation


def _node_metadata(
    self: _Engine,
    node: NodeOccurrence,
    component: Any,
    input_adapter: Any,
    workflow_id: str,
    component_name: str,
) -> dict[str, Any]:
    implementation_type = _component_contract_type(component)
    implementation_failure, implementation_effects = _component_behavior(component)
    input_adapter_type = _component_contract_type(input_adapter)
    current_workflow = (
        self._workflow_definition_stack[-1] if self._workflow_definition_stack else None
    )
    return {
        "implementation_hash": sha256(
            repr(
                (
                    getattr(component, "definition", component),
                    getattr(component, "bindings", None),
                )
            ).encode()
        ).hexdigest(),
        "source_hash": self.program.source_hash,
        "module_hashes": dict(self.program.module_hashes),
        "workflow_id": workflow_id,
        "component": component_name,
        **(
            {"reasoning": current_workflow.abstract_name}
            if node.method_type is not None
            and current_workflow is not None
            and current_workflow.abstract_name is not None
            else {}
        ),
        **(
            {
                "method_type": node.method_type.render(),
                "topology_input_type": node.topology_input_type.render(),
                "input_type": node.input_type.render(),
                "output_type": node.output_type.render(),
            }
            if node.method_type is not None
            and node.input_type is not None
            and node.output_type is not None
            and node.topology_input_type is not None
            else {}
        ),
        **(
            {"input_adapter_type": input_adapter_type.render()}
            if input_adapter_type is not None
            else {}
        ),
        **(
            {"implementation_type": implementation_type.render()}
            if implementation_type is not None
            else {}
        ),
        "failure_type": implementation_failure.render(),
        "effects": implementation_effects,
    }


def _invoke_node(
    self: _Engine,
    node: NodeOccurrence,
    component: Any,
    input_adapter: Any,
    alias: str,
    environment: dict[str, Any],
) -> tuple[Any, Any, str | None]:
    if isinstance(node.component, CallExpression):
        return component, None, None
    parameter_names = _component_parameter_names(component)
    topology_input = (
        self._eval(node.logical_input, environment)
        if node.logical_input is not None
        else None
    )
    reasoning_input = topology_input
    input_reference = self.provenance.last if node.logical_input is not None else None
    if node.logical_input is not None:
        assert input_reference is not None
    if input_adapter is not None:
        assert input_reference is not None
        adapter_parameter_names = _component_parameter_names(input_adapter)
        adapter_required_names = adapter_parameter_names[1:]
        adapter_missing = [
            name for name in adapter_required_names if name not in environment
        ]
        if adapter_missing:
            raise ValueError(
                f"input adapter for `{alias}` is missing inputs: "
                + ", ".join(adapter_missing)
            )
        adapter_named = {name: environment[name] for name in adapter_required_names}
        reasoning_input = self._call(
            input_adapter,
            (topology_input,),
            adapter_named,
            environment,
            _component_result_type(input_adapter),
            references=CallReferences(
                (input_reference,),
                {
                    name: environment.references[name]
                    for name in adapter_required_names
                    if isinstance(environment, ValueEnvironment)
                    and name in environment.references
                },
            ),
        )
        input_reference = self.provenance.last
        assert input_reference is not None
    required_names = (
        parameter_names[1:] if node.logical_input is not None else parameter_names
    )
    missing = [name for name in required_names if name not in environment]
    if missing:
        raise ValueError(
            f"workflow node `{alias}` is missing inputs: {', '.join(missing)}"
        )
    named = {name: environment[name] for name in required_names}
    if node.logical_input is not None:
        check_requirements(
            self, node.contract.input_requirements, reasoning_input, input_reference
        )
    result = self._call(
        component,
        (reasoning_input,) if node.logical_input is not None else (),
        named,
        environment,
        _component_result_type(component),
        references=CallReferences(
            (input_reference,) if input_reference is not None else (),
            {
                name: environment.references[name]
                for name in required_names
                if isinstance(environment, ValueEnvironment)
                and name in environment.references
            },
        ),
    )
    return result, reasoning_input, input_reference


def _check_guarded_exits(self: _Engine, alias: str, result: Any) -> None:
    if self._workflow_definition_stack:
        definition = self._workflow_definition_stack[-1]
        for guarded in definition.guarded_exits:
            if guarded.occurrence == alias and _disposition_matches(
                result, guarded.selector
            ):
                self.trace.append(
                    TraceEvent(
                        "reasoning-exit",
                        f"{alias}.{guarded.selector}",
                        status=guarded.action,
                        metadata={"target": guarded.target},
                    )
                )
                raise _ReasoningExitSignal(
                    guarded.action,
                    result,
                    alias,
                    guarded.selector,
                    guarded.target,
                )


def _ordinary_node_input(self, invocation):
    assert invocation is not None
    positional, named, references = invocation
    values = (*positional, *named.values())
    if len(values) == 1:
        return values[0], references.inputs[0]
    value = tuple(values) if values else None
    reference = self.provenance.record(
        value,
        "computed",
        "occurrence input",
        references.inputs,
        children={str(index): ref for index, ref in enumerate(references.inputs)},
    )
    return value, reference
