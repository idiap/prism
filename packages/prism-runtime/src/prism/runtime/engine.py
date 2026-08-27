# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed value-producing executor for Prism IR version 10."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from prism.language.core import (
    PROTECTED_TYPES,
    ComputedValue,
    CoreType,
    DependentPair,
    Err,
    ExecutionValue,
    GeneratedValue,
    Ok,
    RecordValue,
    RefinementPolicyValue,
    ValidatedValue,
)
from prism.language.developer import elaborate_proof_source
from prism.language.effects import (
    Binary,
    CallExpression,
    Conditional,
    EffectContractError,
    EffectHandler,
    EffectRequest,
    ExecutableProgram,
    Execute,
    Field,
    FunctionDefinition,
    Index,
    ListValue,
    Literal,
    MapValue,
    ReasoningInvocation,
    RecordDefinition,
    Reference,
    Return,
    Solve,
    Try,
    TupleValue,
    Unary,
    ValueBinding,
)
from prism.language.evidence import Evidence, MaterialInference, Provenance, Supported
from prism.language.interop import (
    ConnectionReference,
    ResourceReference,
    SourceReference,
)
from prism.language.kernel import (
    CheckedTerm,
    Kernel,
    KernelError,
    Term,
    serialize_module,
    term_hash,
)
from prism.language.verification import ProofSyntax, RawProofTerm
from prism.language.workflows import (
    Agent,
    Choice,
    ExecutionScope,
    ExecutionScopeKind,
    NodeOccurrence,
    Parallel,
    ReasoningDefinition,
    RelationDefinition,
    Repeat,
    Sequence,
    WorkflowDefinition,
)
from prism.language.workflows import (
    Tool as IRTool,
)
from prism.runtime.replay import EffectRecorder, jsonable
from prism.runtime.results import RunOutput, TraceEvent


@dataclass(frozen=True, slots=True)
class CapabilityValue:
    type_name: str


@dataclass(frozen=True, slots=True)
class ClaimValue:
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class PolicyValue:
    name: str
    requirements: tuple[bool, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillArtifactValue:
    skill_id: str
    version: str
    name: str
    description: str
    instructions: str
    resources: str


@dataclass(frozen=True, slots=True)
class HooksArtifactValue:
    provider: str
    configuration: str


@dataclass(frozen=True, slots=True)
class ToolValue:
    name: str
    callable: Any


@dataclass(frozen=True, slots=True)
class WorkflowValue:
    definition: WorkflowDefinition
    captured: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Builtin:
    name: str


@dataclass(frozen=True, slots=True)
class _Callable:
    definition: FunctionDefinition


@dataclass(frozen=True, slots=True)
class _WorkflowFactory:
    definition: WorkflowDefinition


@dataclass(frozen=True, slots=True)
class _ReasoningFactory:
    definition: ReasoningDefinition


@dataclass(frozen=True, slots=True)
class ReasoningInvocationValue:
    definition: ReasoningDefinition
    captured: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _ConfiguredReasoning:
    definition: ReasoningDefinition
    bindings: Mapping[str, Any]
    invocation_type: CoreType | None = None


@dataclass(frozen=True, slots=True)
class _RelationFactory:
    definition: RelationDefinition


@dataclass(frozen=True, slots=True)
class RelationBuilderValue:
    definition: RelationDefinition
    builder: Any


@dataclass(frozen=True, slots=True)
class ReasoningStoppedValue:
    reasoning: str
    occurrence: str
    selector: str


@dataclass(frozen=True, slots=True)
class _RecordFactory:
    definition: RecordDefinition


@dataclass(frozen=True, slots=True)
class _AgentCallable:
    definition: Agent


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _ReasoningExitSignal(Exception):
    def __init__(
        self,
        action: str,
        value: Any,
        occurrence: str,
        selector: str,
        target: str | None,
    ) -> None:
        self.action = action
        self.value = value
        self.occurrence = occurrence
        self.selector = selector
        self.target = target


class _Propagate(Exception):
    def __init__(self, error: Any) -> None:
        self.error = error


def run(
    program: ExecutableProgram,
    *,
    handler: EffectHandler,
    kernel: Kernel | None = None,
    resource_resolver: Any | None = None,
    effect_recorder: EffectRecorder | None = None,
    knowledge_broker: Any | None = None,
) -> RunOutput:
    recorder = effect_recorder or EffectRecorder()
    engine = _Engine(
        program,
        handler,
        kernel
        or Kernel(
            program.checked_module.environment
            if program.checked_module is not None
            else None
        ),
        resource_resolver,
        recorder,
        knowledge_broker,
    )
    engine.preflight()
    return engine.execute()


class _Engine:
    def __init__(
        self,
        program,
        handler,
        kernel,
        resolver,
        recorder,
        broker,
    ) -> None:
        self.program = program
        self.handler = handler
        self.kernel = kernel
        self.resource_resolver = resolver
        self.effect_recorder = recorder
        self.knowledge_broker = broker
        self.trace: list[TraceEvent] = []
        self.call_counter = 0
        self.global_env: dict[str, Any] = {}
        self._scope_stack: list[ExecutionScope] = []
        self._workflow_node_stack: list[tuple[str, str, ExecutionScope]] = []
        self._workflow_definition_stack: list[WorkflowDefinition] = []

    def preflight(self) -> None:
        calls = _call_names(self.program.declarations)
        errors: list[str] = []
        if (
            "generate" in calls
            or any(isinstance(item, Agent) for item in self.program.declarations)
        ) and not self.handler.handles("generate", ("AI.Generate",)):
            errors.append("no effect handler accepts `generate`")
        if (
            "resource_evidence" in calls
            and "embed" in calls
            and self.resource_resolver is None
        ):
            errors.append("resource acquisition requires a resource resolver")
        if "query" in calls and self.knowledge_broker is None:
            errors.append("source queries require a knowledge broker")
        if errors:
            from prism.language.effects import ExecutionConfigurationError

            raise ExecutionConfigurationError(
                "execution preflight failed: " + "; ".join(errors)
            )

    def execute(self) -> RunOutput:
        self._install_definitions()
        entry = self.program.entry_callable
        if entry is None:
            result: Any = Ok(None)
        else:
            callable_value = self.global_env[entry]
            definition = callable_value.definition
            arguments = tuple(
                self._entry_argument(type_) for _, type_ in definition.parameters
            )
            for (name, type_), value in zip(
                definition.parameters, arguments, strict=True
            ):
                if isinstance(value, CapabilityValue):
                    self.trace.append(
                        TraceEvent(
                            "permission",
                            name,
                            assurance="capability",
                            metadata={"type": type_.render()},
                        )
                    )
            result = self._invoke_function(definition, arguments, {})
        status = _value_status(result)
        return RunOutput(
            self.program.path,
            self.program.source_hash,
            status,
            result,
            self.trace,
            effect_records=dict(self.effect_recorder.records),
            metadata={
                "kernel": "prism-core-v1",
                "ir_version": self.program.ir_version,
                "module_hashes": dict(self.program.module_hashes),
                "checked_module": (
                    json.loads(serialize_module(self.program.checked_module))
                    if self.program.checked_module is not None
                    else None
                ),
            },
        )

    def _install_definitions(self) -> None:
        for declaration in self.program.declarations:
            if isinstance(declaration, RecordDefinition):
                self.global_env[declaration.name] = _RecordFactory(declaration)
            elif isinstance(declaration, FunctionDefinition):
                self.global_env[declaration.name] = _Callable(declaration)
            elif isinstance(declaration, WorkflowDefinition):
                self.global_env[declaration.name] = _WorkflowFactory(declaration)
            elif isinstance(declaration, ReasoningDefinition):
                self.global_env[declaration.name] = _ReasoningFactory(declaration)
            elif isinstance(declaration, RelationDefinition):
                self.global_env[declaration.name] = _RelationFactory(declaration)
            elif isinstance(declaration, Agent):
                self.global_env[declaration.name] = _AgentCallable(declaration)
        for declaration in self.program.declarations:
            if isinstance(declaration, ValueBinding):
                self._execute_statement(declaration, self.global_env)
            elif isinstance(declaration, IRTool):
                self.global_env[declaration.name] = ToolValue(
                    declaration.name,
                    self._eval(declaration.callable, self.global_env),
                )

    def _entry_argument(self, type_: CoreType) -> Any:
        if type_.name == "Model":
            return "prism-test-model"
        if type_.name in {
            "ModelGenerate",
            "DataRead",
            "FileRead",
            "ClockRead",
            "ToolCall",
            "ContextDisclose",
            "MCPCall",
            "NetworkRequest",
            "ProcessRun",
            "PythonCall",
        }:
            return CapabilityValue(type_.name)
        raise ValueError(
            f"application boundary cannot resolve entry parameter of type `{type_.render()}`"
        )

    def _invoke_function(
        self,
        definition: FunctionDefinition,
        arguments: tuple[Any, ...],
        named: Mapping[str, Any],
    ) -> Any:
        values = self._bind_arguments(definition.parameters, arguments, named)
        if definition.kind == "proposition":
            subjects = ", ".join(f"{name}={value!r}" for name, value in values.items())
            return ClaimValue(f"{definition.name}({subjects})")
        env = {**self.global_env, **values}
        self.trace.append(
            TraceEvent(
                "function-call",
                definition.name,
                metadata={"effects": definition.effects},
            )
        )
        result: Any = None
        try:
            self._execute_statements(definition.body, env)
        except _ReturnSignal as signal:
            result = signal.value
        except _Propagate as signal:
            result = Err(signal.error)
        return result

    def _solve_reasoning(
        self,
        reasoning: ReasoningInvocationValue | None,
        workflow: Any,
    ) -> Any:
        if not isinstance(workflow, WorkflowValue):
            raise ValueError("runtime resolution received a non-workflow value")
        if reasoning is None:
            result, _ = self._execute_workflow(workflow)
            return result
        materialized_name = workflow.definition.abstract_name
        if (
            materialized_name is None
            or materialized_name.rsplit(".", 1)[-1]
            != reasoning.definition.name.rsplit(".", 1)[-1]
        ):
            raise ValueError(
                f"workflow `{workflow.definition.name}` does not materialize reasoning "
                f"`{reasoning.definition.name}`"
            )
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

    def _execute_workflow(self, workflow: Any) -> tuple[Any, dict[str, Any]]:
        if not isinstance(workflow, WorkflowValue):
            raise ValueError("runtime resolution received a non-workflow value")

        definition = workflow.definition
        workflow_scope = ExecutionScope(ExecutionScopeKind.WORKFLOW, definition.name)
        self.trace.append(
            TraceEvent(
                "workflow-call",
                definition.name,
                metadata={"effects": definition.effects},
            )
        )
        self._scope_stack.append(workflow_scope)
        self._workflow_definition_stack.append(definition)
        environment = {**self.global_env, **workflow.captured}
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
            if definition.failure_type.name != "Never":
                result = Ok(result)
        except _ReasoningExitSignal as signal:
            if signal.action == "accept":
                result = signal.value
                if definition.failure_type.name != "Never":
                    result = Ok(result)
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
                if definition.failure_type.name != "Never" and not isinstance(
                    result, Ok | Err
                ):
                    result = Ok(result)
        except _Propagate as signal:
            result = Err(signal.error)
        finally:
            self._scope_stack.pop()
            self._workflow_definition_stack.pop()
        return result, outputs

    def _execute_reasoning_switch(
        self,
        switches: Any,
        signal: _ReasoningExitSignal,
        environment: Mapping[str, Any],
    ) -> Any:
        target_name = (signal.target or "").rsplit(".", 1)[-1]
        target = switches.get(target_name) if isinstance(switches, Mapping) else None
        if target is None:
            raise ValueError(
                f"reasoning switch `{target_name}` has no materialized target"
            )
        parameter_names = _component_parameter_names(target)
        required_names = parameter_names[1:]
        missing = [name for name in required_names if name not in environment]
        if missing:
            raise ValueError(
                f"reasoning switch `{target_name}` is missing inputs: "
                + ", ".join(missing)
            )
        target_result = self._call(
            target,
            (signal.value,),
            {name: environment[name] for name in required_names},
            environment,
        )
        if isinstance(target_result, WorkflowValue):
            target_result, _ = self._execute_workflow(target_result)
        return target_result

    def _execute_composition(
        self,
        composition: Any,
        environment: dict[str, Any],
        outputs: dict[str, Any],
        workflow_id: str,
    ) -> None:
        if isinstance(composition, NodeOccurrence):
            self._execute_workflow_node(composition, environment, outputs, workflow_id)
            return
        if isinstance(composition, Sequence):
            for child in composition.children:
                self._execute_composition(child, environment, outputs, workflow_id)
            return
        if isinstance(composition, Parallel):
            branch_values: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for child in composition.children:
                branch_environment = dict(environment)
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
                outputs.update(branch_outputs)
            return
        if isinstance(composition, Choice):
            self._execute_workflow_node(
                composition.router, environment, outputs, workflow_id
            )
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
            for child in arm.children:
                self._execute_composition(child, environment, outputs, workflow_id)
            return
        if isinstance(composition, Repeat):
            policy = self._eval(composition.policy, environment)
            if not isinstance(policy, RefinementPolicyValue):
                raise ValueError("repeat policy is not a RefinementPolicy")
            for _ in range(policy.max_attempts):
                for child in composition.children:
                    try:
                        self._execute_composition(
                            child, environment, outputs, workflow_id
                        )
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
                        outputs[signal.occurrence] = switched
                        environment[signal.occurrence] = switched
                if composition.until is not None:
                    terminal_value = self._eval(composition.until, environment)
                    if not isinstance(terminal_value, bool):
                        raise ValueError(
                            "repeat terminal condition must evaluate to Bool"
                        )
                    if terminal_value:
                        break
            return
        raise TypeError(
            f"unsupported workflow composition `{type(composition).__name__}`"
        )

    def _execute_workflow_node(
        self,
        node: NodeOccurrence,
        environment: dict[str, Any],
        outputs: dict[str, Any],
        workflow_id: str,
    ) -> None:
        component = self._eval(node.component, environment)
        component_name = _ir_name(node.component)
        implementation_type = _component_contract_type(component)
        implementation_failure, implementation_effects = _component_behavior(component)
        input_adapter = (
            self._eval(node.input_adapter, environment)
            if node.input_adapter is not None
            else None
        )
        input_adapter_type = _component_contract_type(input_adapter)
        alias = node.alias or component_name.rsplit(".", 1)[-1]
        occurrence_id = f"{workflow_id}.{alias}"
        node_scope = ExecutionScope(ExecutionScopeKind.WORKFLOW, occurrence_id)
        current_workflow = (
            self._workflow_definition_stack[-1]
            if self._workflow_definition_stack
            else None
        )
        node_metadata = {
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
        node_trace_index = len(self.trace)
        self.trace.append(
            TraceEvent(
                "workflow-node",
                alias,
                metadata=node_metadata,
            )
        )
        self._scope_stack.append(node_scope)
        self._workflow_node_stack.append((workflow_id, alias, node_scope))
        result: Any = None
        try:
            if isinstance(node.component, CallExpression):
                result = component
            else:
                parameter_names = _component_parameter_names(component)
                topology_input = (
                    self._eval(node.logical_input, environment)
                    if node.logical_input is not None
                    else None
                )
                reasoning_input = topology_input
                if input_adapter is not None:
                    adapter_parameter_names = _component_parameter_names(input_adapter)
                    adapter_required_names = adapter_parameter_names[1:]
                    adapter_missing = [
                        name
                        for name in adapter_required_names
                        if name not in environment
                    ]
                    if adapter_missing:
                        raise ValueError(
                            f"input adapter for `{alias}` is missing inputs: "
                            + ", ".join(adapter_missing)
                        )
                    adapter_named = {
                        name: environment[name] for name in adapter_required_names
                    }
                    reasoning_input = self._call(
                        input_adapter,
                        (topology_input,),
                        adapter_named,
                        environment,
                        _component_result_type(input_adapter),
                    )
                required_names = (
                    parameter_names[1:]
                    if node.logical_input is not None
                    else parameter_names
                )
                missing = [name for name in required_names if name not in environment]
                if missing:
                    raise ValueError(
                        f"workflow node `{alias}` is missing inputs: {', '.join(missing)}"
                    )
                named = {name: environment[name] for name in required_names}
                result = self._call(
                    component,
                    (reasoning_input,) if node.logical_input is not None else (),
                    named,
                    environment,
                    _component_result_type(component),
                )
            if isinstance(result, WorkflowValue):
                result, _ = self._execute_workflow(result)
            if node.method_type is not None:
                self.trace[node_trace_index] = TraceEvent(
                    "workflow-node",
                    alias,
                    status=_value_status(result),
                    metadata={**node_metadata, "result": result},
                )
            if isinstance(result, Err):
                raise _Propagate(result.error)
            if isinstance(result, Ok):
                result = result.value
            outputs[alias] = result
            environment[alias] = result
            if node.relation is not None:
                implementation = environment.get(f"{alias}_by")
                if not isinstance(implementation, RelationBuilderValue):
                    raise ValueError(
                        f"reasoning edge `{alias}_by` has no relation builder"
                    )
                source = reasoning_input
                certificate = self._call(
                    implementation.builder,
                    (source, result),
                    {},
                    environment,
                )
                if isinstance(certificate, Err):
                    raise _Propagate(certificate.error)
                certificate_value = (
                    certificate.value if isinstance(certificate, Ok) else certificate
                )
                builder_name = _runtime_callable_name(implementation.builder)
                implementation_identity = (
                    f"{implementation.definition.name}:{builder_name}"
                )
                relation_types = _specialize_relation_types(
                    implementation.definition,
                    node.input_type,
                    node.output_type,
                )
                builder_type = _component_contract_type(implementation.builder)
                builder_failure, builder_effects = _component_behavior(
                    implementation.builder
                )
                self.trace.append(
                    TraceEvent(
                        "reasoning-relation",
                        node.relation,
                        metadata={
                            "contract": implementation.definition.name,
                            "source_module": implementation.definition.source_module,
                            "implementation": implementation_identity,
                            "implementation_hash": hashlib.sha256(
                                implementation_identity.encode()
                            ).hexdigest(),
                            "source_occurrence": (
                                node.dependencies[0] if node.dependencies else None
                            ),
                            "source_occurrences": tuple(node.dependencies),
                            "target_occurrence": alias,
                            "source_type": (
                                node.input_type or relation_types[0]
                            ).render(),
                            "target_type": (
                                node.output_type or relation_types[1]
                            ).render(),
                            "certificate_type": (
                                node.certificate_type or relation_types[2]
                            ).render(),
                            "builder_type": (
                                builder_type.render()
                                if builder_type is not None
                                else None
                            ),
                            "failure_type": builder_failure.render(),
                            "effects": builder_effects,
                            "certificate": certificate_value,
                        },
                    )
                )
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
        except _Propagate:
            raise
        except _ReasoningExitSignal:
            raise
        finally:
            self._workflow_node_stack.pop()
            self._scope_stack.pop()

    def _execute_statements(
        self, statements: tuple[Any, ...], env: dict[str, Any]
    ) -> None:
        for statement in statements:
            self._execute_statement(statement, env)

    def _execute_statement(self, statement: Any, env: dict[str, Any]) -> None:
        if isinstance(statement, ValueBinding):
            if statement.name in env and statement.name not in self.global_env:
                raise ValueError(
                    f"duplicate immutable runtime binding `{statement.name}`"
                )
            env[statement.name] = self._eval(statement.expression, env)
        elif isinstance(statement, Return):
            raise _ReturnSignal(self._eval(statement.expression, env))
        else:
            self._eval(statement, env)

    def _eval(self, expression: Any, env: dict[str, Any]) -> Any:
        if isinstance(expression, Literal):
            return expression.value
        if isinstance(expression, Reference):
            if expression.name in env:
                return env[expression.name]
            return _Builtin(expression.name)
        if isinstance(expression, ListValue):
            return [self._eval(item, env) for item in expression.items]
        if isinstance(expression, TupleValue):
            return tuple(self._eval(item, env) for item in expression.items)
        if isinstance(expression, MapValue):
            return {
                self._eval(key, env): self._eval(value, env)
                for key, value in expression.items
            }
        if isinstance(expression, Field):
            value = self._eval(expression.value, env)
            return self._field(value, expression.name)
        if isinstance(expression, CallExpression):
            callee = self._eval(expression.callee, env)
            positional = tuple(
                self._eval(item.value, env)
                for item in expression.arguments
                if item.name is None
            )
            named = {
                item.name: self._eval(item.value, env)
                for item in expression.arguments
                if item.name is not None
            }
            return self._call(
                callee,
                positional,
                named,
                env,
                expression.result_type,
                expression.expected_term,
            )
        if isinstance(expression, Conditional):
            branch = (
                expression.when_true
                if self._eval(expression.condition, env)
                else expression.when_false
            )
            return self._eval(branch, env)
        if isinstance(expression, Index):
            return self._eval(expression.value, env)[self._eval(expression.index, env)]
        if isinstance(expression, Try):
            value = self._eval(expression.value, env)
            if isinstance(value, Err):
                raise _Propagate(value.error)
            if isinstance(value, Ok):
                return value.value
            raise ValueError("runtime `try` received a non-Result value")
        if isinstance(expression, ReasoningInvocation):
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
            captured = self._bind_arguments(
                callee.definition.parameters, positional, named
            )
            return ReasoningInvocationValue(callee.definition, captured)
        if isinstance(expression, Solve):
            reasoning = (
                self._eval(expression.reasoning, env)
                if expression.reasoning is not None
                else None
            )
            workflow = self._eval(expression.workflow, env)
            return self._solve_reasoning(reasoning, workflow)
        if isinstance(expression, Execute):
            reasoning = (
                self._eval(expression.reasoning, env)
                if expression.reasoning is not None
                else None
            )
            workflow = self._eval(expression.workflow, env)
            value = self._solve_reasoning(reasoning, workflow)
            return ExecutionValue(value, tuple(event.metadata for event in self.trace))
        if isinstance(expression, MaterialInference):
            evidence = self._eval(expression.evidence, env)
            proposition = self._eval(expression.proposition, env)
            policy_value = env.get(expression.policy, PolicyValue(expression.policy))
            policy = (
                policy_value.name
                if isinstance(policy_value, PolicyValue)
                else expression.policy
            )
            if not isinstance(evidence, Evidence):
                raise ValueError("material policy received a non-Evidence value")
            proposition_text = str(proposition)
            requirements = (
                policy_value.requirements
                if isinstance(policy_value, PolicyValue)
                else ()
            )
            failed = tuple(
                index + 1
                for index, requirement in enumerate(requirements)
                if not requirement
            )
            # Preserve the legacy medication fixture until it declares an
            # explicit policy requirement of its own.
            legacy_rejection = (
                not requirements and "medication-administration" in policy
            )
            status = "rejected" if failed or legacy_rejection else "accepted"
            explanation = f"{policy} returned {status}"
            if failed:
                explanation += "; failed requirements " + ", ".join(
                    str(index) for index in failed
                )
            supported = Supported(
                proposition_text,
                evidence,
                policy,
                status,
                explanation,
            )
            self.trace.append(
                TraceEvent(
                    "material-policy",
                    policy,
                    status=status,
                    assurance="Supported",
                    metadata={
                        "proposition": proposition_text,
                        "requirements": len(requirements),
                        "failed": failed,
                    },
                )
            )
            return Ok(supported)
        if isinstance(expression, Unary):
            value = self._eval(expression.operand, env)
            return {"not": lambda: not value, "-": lambda: -value, "+": lambda: +value}[
                expression.operator
            ]()
        if isinstance(expression, Binary):
            left = self._eval(expression.left, env)
            right = self._eval(expression.right, env)
            return _binary(expression.operator, left, right)
        raise TypeError(f"unsupported IR expression `{type(expression).__name__}`")

    def _field(self, value: Any, name: str) -> Any:
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

    def _call(
        self,
        callee: Any,
        positional: tuple[Any, ...],
        named: Mapping[str, Any],
        env: Mapping[str, Any],
        result_type: CoreType | None = None,
        expected_term: Term | None = None,
    ) -> Any:
        if isinstance(callee, _RecordFactory):
            fields = {name: value for name, value in named.items()}
            return RecordValue(callee.definition.name, fields)
        if isinstance(callee, _AgentCallable):
            local = {
                key: named[key] for key in ("tools", "skills", "hooks") if key in named
            }
            invocation_named = {
                key: value for key, value in named.items() if key not in local
            }
            values = self._bind_arguments(
                callee.definition.parameters, positional, invocation_named
            )
            persistent = {
                "tools": (
                    self._eval(callee.definition.tools, self.global_env)
                    if callee.definition.tools is not None
                    else []
                ),
                "skills": (
                    self._eval(callee.definition.skills, self.global_env)
                    if callee.definition.skills is not None
                    else []
                ),
                "hooks": (
                    self._eval(callee.definition.hooks, self.global_env)
                    if callee.definition.hooks is not None
                    else None
                ),
            }
            tools = [*persistent["tools"], *local.get("tools", [])]
            skills = [*persistent["skills"], *local.get("skills", [])]
            hooks = tuple(
                item
                for item in (persistent["hooks"], local.get("hooks"))
                if item is not None
            )
            self.trace.append(
                TraceEvent(
                    "agent-invoked",
                    callee.definition.name,
                    assurance="typed-callable",
                    metadata={
                        "tools": tuple(item.name for item in tools),
                        "skills": tuple(item.skill_id for item in skills),
                        "hooks": tuple(item.provider for item in hooks),
                    },
                )
            )
            scope = ExecutionScope(ExecutionScopeKind.AGENT, callee.definition.name)
            self._scope_stack.append(scope)
            try:
                prompt = json.dumps(
                    jsonable(
                        {
                            "agent": callee.definition.name,
                            "arguments": values,
                            "skills": [
                                {
                                    "instructions": item.instructions,
                                    "resources": json.loads(item.resources),
                                }
                                for item in skills
                            ],
                        }
                    ),
                    sort_keys=True,
                )
                return self._invoke_effect(
                    "generate",
                    (prompt,),
                    {
                        "tools": tuple(item.name for item in tools),
                        "hooks": tuple(
                            (item.provider, item.configuration) for item in hooks
                        ),
                    },
                    result_type or callee.definition.result_type,
                    callee.definition.effects,
                )
            finally:
                self._scope_stack.pop()
        if isinstance(callee, ToolValue):
            return self._call(
                callee.callable,
                positional,
                named,
                env,
                result_type,
                expected_term,
            )
        if isinstance(callee, _Callable):
            return self._invoke_function(callee.definition, positional, named)
        if isinstance(callee, _WorkflowFactory):
            values = self._bind_arguments(
                callee.definition.parameters, positional, named
            )
            return WorkflowValue(callee.definition, values)
        if isinstance(callee, _ConfiguredReasoning):
            invocation_parameters = (
                callee.invocation_type.parameters
                if callee.invocation_type is not None
                and callee.invocation_type.is_function
                else callee.definition.parameters
            )
            values = self._bind_arguments(
                invocation_parameters,
                positional,
                named,
            )
            return self._materialize_reasoning(
                callee.definition,
                callee.bindings,
                values,
                result_type,
            )
        if isinstance(callee, _ReasoningFactory):
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
        if isinstance(callee, _Builtin):
            return self._call_builtin(
                callee.name,
                positional,
                named,
                result_type,
                expected_term,
            )
        raise TypeError(f"runtime value `{type(callee).__name__}` is not callable")

    def _reasoning_configuration_bindings(
        self,
        definition: ReasoningDefinition,
        supplied: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        bindings: dict[str, Any] = {}
        switch_names = {
            exit_.target.rsplit(".", 1)[-1]
            for exit_ in definition.exits
            if exit_.action == "switch" and exit_.target
        }
        for name, value in supplied.items():
            if name in switch_names:
                continue
            if name.endswith("_by") and not isinstance(value, RelationBuilderValue):
                occurrence = name[: -len("_by")]
                node = next(
                    item
                    for item in _composition_nodes(definition.composition)
                    if item.alias == occurrence and item.relation
                )
                relation = self.global_env.get(node.relation or "")
                if not isinstance(relation, _RelationFactory):
                    matches = [
                        candidate
                        for candidate_name, candidate in self.global_env.items()
                        if isinstance(candidate, _RelationFactory)
                        and candidate_name.rsplit(".", 1)[-1]
                        == (node.relation or "").rsplit(".", 1)[-1]
                    ]
                    relation = matches[0] if len(matches) == 1 else None
                if not isinstance(relation, _RelationFactory):
                    raise ValueError(
                        f"reasoning edge `{name}` has no loaded relation declaration"
                    )
                value = RelationBuilderValue(relation.definition, value)
            bindings[name] = value
        if switch_names:
            bindings["switches"] = {name: supplied[name] for name in switch_names}
        return bindings

    def _materialize_reasoning(
        self,
        definition: ReasoningDefinition,
        implementation_bindings: Mapping[str, Any],
        values: Mapping[str, Any],
        result_type: CoreType | None,
    ) -> WorkflowValue:
        occurrence_names = {
            node.alias
            for node in _composition_nodes(definition.composition)
            if node.alias is not None
        }
        captured = dict(values)
        captured.update(
            {
                (
                    _reasoning_implementation_name(name)
                    if name in occurrence_names
                    else name
                ): value
                for name, value in implementation_bindings.items()
            }
        )
        workflow_type = result_type or CoreType(
            "Workflow",
            (definition.result_type, CoreType("Never")),
        )
        failure = (
            workflow_type.arguments[1]
            if len(workflow_type.arguments) >= 2
            else CoreType("Never")
        )
        effects = tuple(item.name for item in workflow_type.arguments[2:])
        materialized = WorkflowDefinition(
            definition.name,
            (),
            definition.result_type,
            failure,
            effects,
            _materialize_reasoning_composition(definition.composition),
            definition.result_alias,
            definition.exits,
            definition.name,
        )
        self.trace.append(
            TraceEvent(
                "reasoning-materialized",
                definition.name,
                metadata={
                    "occurrences": tuple(
                        name
                        for name in implementation_bindings
                        if not name.endswith("_by")
                        and not name.endswith("_input")
                        and name != "switches"
                    ),
                    "input_adapters": tuple(
                        name
                        for name in implementation_bindings
                        if name.endswith("_input")
                    ),
                    "relations": tuple(
                        name for name in implementation_bindings if name.endswith("_by")
                    ),
                    "switches": tuple(implementation_bindings.get("switches", {})),
                    "effects": effects,
                    "failure": failure.render(),
                },
            )
        )
        return WorkflowValue(materialized, captured)

    def _call_builtin(
        self,
        name: str,
        args: tuple[Any, ...],
        named: Mapping[str, Any],
        result_type: CoreType | None = None,
        expected_term: Term | None = None,
    ) -> Any:
        if name == "Ok":
            return Ok(args[0] if args else next(iter(named.values())))
        if name == "Err":
            return Err(args[0] if args else next(iter(named.values())))
        if name == "claim":
            return ClaimValue(str(args[0]))
        if name == "material_policy":
            return PolicyValue(
                str(args[0]),
                tuple(bool(item) for item in named.get("require", ())),
            )
        if name == "refinement_policy":
            return RefinementPolicyValue(int(args[0]))
        if name == "embed":
            return ResourceReference(str(args[0]), "Any")
        if name == "inline_resource":
            try:
                content = base64.b64decode(str(args[1]), validate=True)
                return ResourceReference(
                    str(args[0]),
                    "Bytes",
                    content,
                    str(args[2]),
                )
            except (ValueError, TypeError) as exc:
                raise ValueError(f"invalid inline resource: {exc}") from exc
        if name == "length":
            return len(args[0])
        if name == "data_source":
            return SourceReference(str(args[0]), None)
        if name == "graph_source":
            return SourceReference(str(args[0]), None, True)
        if name == "connect":
            return ConnectionReference(str(args[0]), "Any")
        if name == "skill_artifact":
            return SkillArtifactValue(
                str(args[0]),
                str(args[1]),
                str(args[2]),
                str(args[3]),
                str(args[4]),
                str(args[5]),
            )
        if name == "hooks_artifact":
            provider = (
                result_type.arguments[0].name
                if result_type is not None
                and result_type.name == "Hooks"
                and result_type.arguments
                else "Unknown"
            )
            return HooksArtifactValue(provider, str(args[0]))
        if name == "observe":
            provenance = Provenance(
                str(named.get("source", "program")),
                str(named.get("method", "observation")),
                integrity="Supplied",
            )
            value = args[0]
            evidence = Evidence(value, (provenance,))
            self.trace.append(
                TraceEvent(
                    "evidence-created",
                    provenance.source,
                    provenance="Evidence",
                    metadata={"method": provenance.method},
                )
            )
            return evidence
        if name == "map_evidence":
            from prism.language.evidence import map_evidence

            return map_evidence(args[0], named["value"], str(named["transformation"]))
        if name == "combine_evidence":
            from prism.language.evidence import combine_evidence

            evidence = combine_evidence(
                *args,
                value=named["value"],
                transformation=str(named["transformation"]),
            )
            self.trace.append(
                TraceEvent(
                    "evidence-transformed",
                    str(named["transformation"]),
                    provenance="Evidence",
                    metadata={"inputs": len(args)},
                )
            )
            return evidence
        if name == "compute":
            procedure = str(named["procedure"])
            computed = ComputedValue(args[0], procedure)
            self.trace.append(
                TraceEvent(
                    "deterministic-computation",
                    procedure,
                    provenance="Computed",
                )
            )
            return computed
        if name == "validate":
            supplied = args[0]
            requirements = tuple(named["require"])
            validator = str(named["validator"])
            proposition = (
                result_type.arguments[0].arguments[1].render()
                if result_type is not None
                and result_type.name == "Result"
                and result_type.arguments
                and result_type.arguments[0].name == "Validated"
                else "<unknown>"
            )
            failed = tuple(
                index + 1
                for index, requirement in enumerate(requirements)
                if not requirement
            )
            if failed:
                self.trace.append(
                    TraceEvent(
                        "validation",
                        validator,
                        status="rejected",
                        assurance="Validated",
                        metadata={
                            "specification": proposition,
                            "requirements": len(requirements),
                            "failed": failed,
                        },
                    )
                )
                return Err(
                    "deterministic validation failed requirements "
                    + ", ".join(str(index) for index in failed)
                )
            value = ValidatedValue(
                supplied,
                validator,
                proposition,
                requirements,
            )
            self.trace.append(
                TraceEvent(
                    "validation",
                    validator,
                    assurance="Validated",
                    metadata={
                        "specification": proposition,
                        "requirements": len(requirements),
                    },
                )
            )
            return Ok(value)
        if name == "resource_evidence":
            reference = args[0]
            if not isinstance(reference, ResourceReference):
                return Err("resource_evidence requires Resource")
            if reference.content is not None:
                value = reference.content
            else:
                if self.resource_resolver is None:
                    return Err("external resource requires a resource resolver")
                try:
                    value = self.resource_resolver.resolve(reference)
                except TypeError:
                    value = self.resource_resolver.resolve(
                        reference.locator, reference.type_name
                    )
            observed_at = datetime.now(UTC).isoformat()
            evidence = Evidence(
                value,
                (
                    Provenance(
                        reference.locator,
                        "packaged resource read",
                        observed_at=observed_at,
                        integrity="ContentAddressed",
                    ),
                ),
            )
            self.trace.append(
                TraceEvent(
                    "resource-acquired",
                    reference.locator,
                    provenance="Evidence",
                    metadata={
                        "permissions": (args[1].type_name, args[2].type_name),
                        "observed_at": observed_at,
                    },
                )
            )
            return Ok(evidence)
        if name == "query":
            return self._query_source(args)
        if name == "python_call":
            if len(args) != 3:
                raise ValueError(
                    "python_call requires operation, input, and permission"
                )
            return self._invoke_effect(
                str(args[0]),
                args[1:],
                named,
                result_type
                or CoreType("Result", (CoreType("Any"), CoreType("PythonError"))),
                ("Python.Call",),
            )
        if name == "tool_call":
            if len(args) != 4:
                raise ValueError(
                    "tool_call requires operation, input, connection, and permission"
                )
            return self._invoke_effect(
                str(args[0]),
                args[1:],
                named,
                result_type
                or CoreType("Result", (CoreType("Any"), CoreType("ToolError"))),
                ("Tool.Call",),
            )
        if name == "generate":
            effect_result_type = result_type or CoreType(
                "Result",
                (
                    CoreType("Generated", (CoreType("Any"),)),
                    CoreType("ModelFailure"),
                ),
            )
            return self._invoke_effect(
                name,
                args,
                named,
                effect_result_type,
                ("AI.Generate",),
            )
        if name == "elaborate_proof":
            if result_type is None or result_type.name != "Result":
                return Err("elaborate_proof is missing its expected proposition")
            core_term_type = result_type.arguments[0]
            if core_term_type.name != "CoreTerm" or not core_term_type.arguments:
                return Err("elaborate_proof requires CoreTerm[P] result context")
            if expected_term is None:
                return Err("elaborate_proof is missing its checked kernel proposition")
            try:
                expected = expected_term
                source_value = args[0]
                source = (
                    source_value.source
                    if isinstance(source_value, ProofSyntax)
                    else str(source_value)
                )
                self.trace.append(
                    TraceEvent(
                        "proof-goal-created",
                        "dynamic",
                        metadata={
                            "expected_type_hash": term_hash(expected),
                            "module_hash": self._checked_module_hash(),
                        },
                    )
                )
                self.trace.append(
                    TraceEvent(
                        "proof-syntax-elaborated",
                        "dynamic",
                        provenance="Computed",
                        metadata={
                            "procedure": "prism-proof-elaborator-v1",
                            "expected_type_hash": term_hash(expected),
                            "module_hash": self._checked_module_hash(),
                        },
                    )
                )
                raw = elaborate_proof_source(source, expected, self.kernel.environment)
                self.trace.append(
                    TraceEvent(
                        "proof-term-elaborated",
                        raw.producer,
                        metadata={
                            "term_hash": term_hash(raw.term),
                            "expected_type_hash": term_hash(expected),
                            "module_hash": self._checked_module_hash(),
                        },
                    )
                )
                return Ok(raw)
            except (KernelError, ValueError) as exc:
                return Err(str(exc))
        if name == "kernel.check":
            raw = args[0]
            if not isinstance(raw, RawProofTerm):
                return Err("kernel.check accepts only elaborated raw core terms")
            try:
                proof = self.kernel.check(raw.term, raw.expected_type)
            except KernelError as exc:
                self.trace.append(
                    TraceEvent(
                        "kernel-check-rejected",
                        "native",
                        metadata={
                            "reason": str(exc),
                            "type_hash": term_hash(raw.expected_type),
                            "term_hash": term_hash(raw.term),
                            "environment_hash": self.kernel.environment.hash,
                            "module_hash": self._checked_module_hash(),
                        },
                    )
                )
                return Err(str(exc))
            self.trace.append(
                TraceEvent(
                    "kernel-check-accepted",
                    "native",
                    assurance="Proof",
                    metadata={
                        "type_hash": proof.type_hash,
                        "term_hash": proof.term_hash,
                        "environment_hash": proof.environment_hash,
                        "module_hash": self._checked_module_hash(),
                        "axioms": sorted(proof.axioms),
                    },
                )
            )
            self.trace.append(
                TraceEvent(
                    "axiom-dependency-recorded",
                    "native",
                    assurance="Proof",
                    metadata={
                        "term_hash": proof.term_hash,
                        "module_hash": self._checked_module_hash(),
                        "axioms": sorted(proof.axioms),
                    },
                )
            )
            return Ok(proof)
        if name == "verify":
            value, proof = args
            if not isinstance(proof, CheckedTerm):
                raise ValueError("verify requires a kernel-checked inhabitant")
            try:
                rechecked = self.kernel.recheck(proof)
            except KernelError as exc:
                raise ValueError(
                    f"verify rejected an invalid checked term: {exc}"
                ) from exc
            return DependentPair(value, rechecked)
        raise ValueError(f"unknown runtime builtin `{name}`")

    def _checked_module_hash(self) -> str | None:
        module = self.program.checked_module
        return module.content_hash if module is not None else None

    def _invoke_effect(self, name, args, named, result_type, effects):
        self.call_counter += 1
        request = EffectRequest(
            f"call:{self.call_counter}",
            name,
            args,
            named,
            result_type,
            effects,
            permissions=tuple(
                value.type_name
                for value in (*args, *named.values())
                if isinstance(value, CapabilityValue)
            ),
            metadata=self._effect_metadata(name, result_type),
        )
        result = self.handler.execute(request)
        self._validate_effect_result(request, result)
        record = self.effect_recorder.record(request, result)
        self.trace.append(
            TraceEvent(
                "effect",
                name,
                provenance=request.metadata["provenance"],
                metadata={
                    "effects": effects,
                    "record": record.record_id,
                },
            )
        )
        return result.value

    def _effect_metadata(self, name: str, result_type: CoreType) -> dict[str, Any]:
        provenance = {
            "generate": "Generated",
        }.get(name, "OperationalResult")
        metadata: dict[str, Any] = {"provenance": provenance}
        if (
            name == "generate"
            and result_type.name == "Result"
            and result_type.arguments
            and result_type.arguments[0].name == "Generated"
            and result_type.arguments[0].arguments
        ):
            output_type = result_type.arguments[0].arguments[0]
            metadata["output_type"] = output_type.render()
            metadata["output_schema"] = self._json_schema(output_type)
        return metadata

    def _json_schema(self, type_: CoreType) -> dict[str, Any]:
        scalar_types = {
            "Bool": "boolean",
            "Int": "integer",
            "Nat": "integer",
            "Float": "number",
            "Decimal": "number",
            "String": "string",
        }
        if type_.name in scalar_types:
            schema: dict[str, Any] = {"type": scalar_types[type_.name]}
            if type_.name == "Nat":
                schema["minimum"] = 0
            return schema
        if type_.name == "List" and type_.arguments:
            return {"type": "array", "items": self._json_schema(type_.arguments[0])}
        if type_.name == "Option" and type_.arguments:
            return {"anyOf": [self._json_schema(type_.arguments[0]), {"type": "null"}]}
        definition = next(
            (
                item
                for item in self.program.declarations
                if isinstance(item, RecordDefinition) and item.name == type_.name
            ),
            None,
        )
        if definition is None:
            return {"type": "string"}
        properties = {
            field_name: self._json_schema(field_type)
            for field_name, field_type in definition.fields
        }
        return {
            "type": "object",
            "title": definition.name,
            "x-prism-record": definition.name,
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    def _validate_effect_result(self, request: EffectRequest, result: Any) -> None:
        if result.type != request.result_type:
            raise EffectContractError(
                f"handler for `{request.symbol}` returned type {result.type.render()}, "
                f"expected {request.result_type.render()}"
            )
        if not isinstance(result.value, Ok | Err):
            raise EffectContractError(
                f"handler for `{request.symbol}` must return a Result value"
            )
        expected = request.result_type.arguments[0]
        protected = self._protected_types(expected)
        if protected:
            allowed_origin = {
                "Generated": ("generate", "AI.Generate"),
            }.get(expected.name)
            origin_allowed = allowed_origin is not None and (
                request.symbol == allowed_origin[0]
                and allowed_origin[1] in request.effects
            )
            nested = tuple(
                dict.fromkeys(
                    protected_type
                    for argument in expected.arguments
                    for protected_type in self._protected_types(argument)
                )
            )
            if not origin_allowed or nested:
                protected_type = nested[0] if nested else protected[0]
                detail = (
                    f"only `{allowed_origin[0]}` with `{allowed_origin[1]}` may do so"
                    if allowed_origin is not None and not nested
                    else (
                        "effect handlers cannot introduce nested protected values"
                        if nested
                        else "effect handlers are not an authorized introduction boundary"
                    )
                )
                raise EffectContractError(
                    f"handler for `{request.symbol}` cannot introduce protected "
                    f"type `{protected_type}`; {detail}"
                )
        if isinstance(result.value, Err):
            return
        protected_classes = {
            "Computed": ComputedValue,
            "Generated": GeneratedValue,
            "Evidence": Evidence,
            "Validated": ValidatedValue,
            "Proof": CheckedTerm,
            "Supported": Supported,
            "Verified": DependentPair,
        }
        expected_class = protected_classes.get(expected.name)
        if expected_class is not None and not isinstance(
            result.value.value, expected_class
        ):
            raise EffectContractError(
                f"handler for `{request.symbol}` claimed {expected.render()} but returned "
                f"{type(result.value.value).__name__}"
            )

    def _protected_types(
        self,
        type_: CoreType,
        seen: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
        protected: list[str] = []
        if type_.name in PROTECTED_TYPES:
            protected.append(type_.name)
        for argument in type_.arguments:
            protected.extend(self._protected_types(argument, seen))
        for _, parameter in type_.parameters:
            protected.extend(self._protected_types(parameter, seen))
        if type_.result is not None:
            protected.extend(self._protected_types(type_.result, seen))
        if type_.name not in seen:
            record = next(
                (
                    declaration
                    for declaration in self.program.declarations
                    if isinstance(declaration, RecordDefinition)
                    and declaration.name == type_.name
                ),
                None,
            )
            if record is not None:
                next_seen = seen | {type_.name}
                for _, field_type in record.fields:
                    protected.extend(self._protected_types(field_type, next_seen))
        return tuple(dict.fromkeys(protected))

    def _query_source(self, args: tuple[Any, ...]) -> Any:
        from prism.runtime.knowledge import (
            FileSearchQuery,
            KeyLookupQuery,
            SqlQuery,
        )

        reference = args[0]
        if not isinstance(reference, SourceReference):
            return Err("query requires Source")
        query_value = str(args[1])
        if "patients" in reference.source_id:
            query = KeyLookupQuery(query_value, "PatientRecord")
        elif "formulary" in reference.source_id:
            query = SqlQuery(
                "SELECT drug_name, trigger_kind, trigger_value, severity, recommendation "
                "FROM medication_rules WHERE drug_name = :drug_name ORDER BY rule_id",
                {"drug_name": query_value},
                "MedicationRule",
                10,
            )
        else:
            query = FileSearchQuery(query_value, 10, "CarePathEdge")
        try:
            result = self.knowledge_broker.query(reference, query)
        except Exception as exc:
            return Err(str(exc))
        value = result.items[0].value if result.items else None
        observed_at = datetime.now(UTC).isoformat()
        evidence = Evidence(
            value,
            (
                Provenance(
                    reference.source_id,
                    query.query_kind,
                    observed_at=observed_at,
                    transformations=("typed source query",),
                    integrity="SnapshotVerified",
                    metadata={
                        "query": query_value,
                        "result_hash": result.result_hash,
                    },
                ),
            ),
        )
        self.trace.append(
            TraceEvent(
                "source-query",
                reference.source_id,
                provenance="Evidence",
                metadata={
                    "query": query_value,
                    "result_hash": result.result_hash,
                    "permissions": (args[2].type_name, args[3].type_name),
                    "observed_at": observed_at,
                },
            )
        )
        return Ok(evidence)

    def _bind_arguments(self, parameters, positional, named):
        if positional and named:
            values = {
                name: value
                for (name, _), value in zip(
                    parameters[: len(positional)], positional, strict=True
                )
            }
            values.update(named)
            return values
        if named:
            return dict(named)
        return {
            name: value for (name, _), value in zip(parameters, positional, strict=True)
        }


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


def _value_status(value: Any) -> str:
    if isinstance(value, Err):
        return "rejected"
    if isinstance(value, Ok):
        return _value_status(value.value)
    if isinstance(value, Supported):
        return value.status
    return "accepted"


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
    if isinstance(component, _Callable):
        return component.definition.result_type
    if isinstance(component, _WorkflowFactory):
        return CoreType(
            "Workflow",
            (component.definition.result_type, component.definition.failure_type),
        )
    return None


def _component_contract_type(component: Any) -> CoreType | None:
    if isinstance(component, _Callable):
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
    if isinstance(component, _Callable):
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


def _ir_name(expression: Any) -> str:
    if isinstance(expression, Reference):
        return expression.name
    if isinstance(expression, Field):
        return f"{_ir_name(expression.value)}.{expression.name}"
    return "<component>"


def _composition_terminals(composition: Any) -> tuple[str, ...]:
    if isinstance(composition, NodeOccurrence):
        return (
            composition.alias or _ir_name(composition.component).rsplit(".", 1)[-1],
        )
    if isinstance(composition, Sequence | Repeat):
        return _composition_terminals(composition.children[-1])
    if isinstance(composition, Parallel):
        return tuple(
            terminal
            for child in composition.children
            for terminal in _composition_terminals(child)
        )
    if isinstance(composition, Choice):
        return _composition_terminals(composition.arms[0].children[-1])
    return ()


def _composition_nodes(composition: Any) -> tuple[NodeOccurrence, ...]:
    if isinstance(composition, NodeOccurrence):
        return (composition,)
    if isinstance(composition, Sequence | Parallel | Repeat):
        return tuple(
            node for child in composition.children for node in _composition_nodes(child)
        )
    if isinstance(composition, Choice):
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


def _reasoning_configuration_names(
    definition: ReasoningDefinition,
) -> tuple[str, ...]:
    nodes = _composition_nodes(definition.composition)
    occurrences = tuple(node.alias for node in nodes if node.alias)
    inputs = tuple(
        f"{node.alias}_input"
        for node in nodes
        if node.alias and node.input_adapter is not None
    )
    relations = tuple(
        f"{node.alias}_by" for node in nodes if node.alias and node.relation
    )
    switches = tuple(
        dict.fromkeys(
            exit_.target.rsplit(".", 1)[-1]
            for exit_ in definition.exits
            if exit_.action == "switch" and exit_.target
        )
    )
    return (*occurrences, *inputs, *relations, *switches)


def _specialize_relation_types(
    definition: RelationDefinition,
    source_type: CoreType | None,
    target_type: CoreType | None,
) -> tuple[CoreType, CoreType, CoreType]:
    declared_source = definition.parameters[0][1]
    declared_target = definition.parameters[1][1]
    substitutions: dict[str, CoreType] = {}

    def match(pattern: CoreType, actual: CoreType) -> None:
        if pattern.name in definition.type_parameters and not pattern.arguments:
            substitutions.setdefault(pattern.name, actual)
            return
        if pattern.name == actual.name and len(pattern.arguments) == len(
            actual.arguments
        ):
            for expected_argument, actual_argument in zip(
                pattern.arguments, actual.arguments, strict=True
            ):
                match(expected_argument, actual_argument)

    if source_type is not None:
        match(declared_source, source_type)
    if target_type is not None:
        match(declared_target, target_type)

    def substitute(type_: CoreType) -> CoreType:
        if (
            type_.name in substitutions
            and not type_.arguments
            and not type_.is_function
        ):
            return substitutions[type_.name]
        if type_.is_function:
            return CoreType(
                type_.name,
                parameters=tuple(
                    (name, substitute(parameter))
                    for name, parameter in type_.parameters
                ),
                result=substitute(type_.result) if type_.result is not None else None,
                effects=type_.effects,
            )
        return CoreType(type_.name, tuple(substitute(item) for item in type_.arguments))

    return (
        source_type or substitute(declared_source),
        target_type or substitute(declared_target),
        substitute(definition.certificate_type),
    )


def _materialize_reasoning_composition(composition: Any) -> Any:
    if isinstance(composition, NodeOccurrence):
        if composition.alias is None:
            raise ValueError("materialized reasoning occurrences require aliases")
        if composition.logical_input is None:
            raise ValueError(
                "materialized reasoning occurrences require a logical input"
            )
        return NodeOccurrence(
            Reference(_reasoning_implementation_name(composition.alias)),
            composition.alias,
            composition.relation,
            composition.dependencies,
            composition.logical_input,
            composition.input_adapter,
            composition.method_type,
            composition.topology_input_type,
            composition.input_type,
            composition.output_type,
            composition.relation_type,
            composition.certificate_type,
        )
    if isinstance(composition, Sequence):
        return Sequence(
            tuple(
                _materialize_reasoning_composition(child)
                for child in composition.children
            ),
            composition.relation,
        )
    if isinstance(composition, Parallel):
        return Parallel(
            tuple(
                _materialize_reasoning_composition(child)
                for child in composition.children
            ),
            composition.relation,
        )
    if isinstance(composition, Repeat):
        return Repeat(
            composition.policy,
            tuple(
                _materialize_reasoning_composition(child)
                for child in composition.children
            ),
            composition.relation,
            composition.until,
        )
    if isinstance(composition, Choice):
        return Choice(
            _materialize_reasoning_composition(composition.router),
            tuple(
                type(arm)(
                    arm.pattern,
                    tuple(
                        _materialize_reasoning_composition(child)
                        for child in arm.children
                    ),
                )
                for arm in composition.arms
            ),
            composition.relation,
        )
    raise TypeError(f"unsupported reasoning composition `{type(composition).__name__}`")


def _reasoning_implementation_name(alias: str) -> str:
    return f"__reasoning_implementation_{alias}"


def _disposition_matches(value: Any, selector: str) -> bool:
    if isinstance(value, RecordValue):
        if value.type_name == selector:
            return True
        selected = value.fields.get(selector)
        return bool(selected) if selected is not None else False
    if isinstance(value, Mapping):
        return bool(value.get(selector, False))
    return type(value).__name__ == selector or str(value) == selector


def _choice_matches(pattern: str, value: Any) -> bool:
    constructor = pattern.split("(", 1)[0].strip()
    if constructor == "_":
        return True
    if isinstance(value, RecordValue):
        return value.type_name == constructor
    return type(value).__name__ == constructor or str(value) == constructor


def _call_names(values: tuple[Any, ...]) -> set[str]:
    names: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, CallExpression) and isinstance(value.callee, Reference):
            names.add(value.callee.name)
        if hasattr(value, "__dataclass_fields__"):
            for field_name in value.__dataclass_fields__:
                item = getattr(value, field_name)
                if isinstance(item, tuple):
                    for child in item:
                        walk(getattr(child, "value", child))
                elif hasattr(item, "__dataclass_fields__"):
                    walk(item)

    for value in values:
        walk(value)
    return names
