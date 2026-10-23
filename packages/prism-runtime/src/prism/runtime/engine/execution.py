# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Execution state, preflight validation, and program entry point."""

from __future__ import annotations

import json
from typing import Any, Mapping
from uuid import uuid4

from prism.language.core import (
    Ok,
)
from prism.language.effects import (
    CallExpression,
    EffectHandler,
    ExecutableProgram,
    FunctionDefinition,
    RecordDefinition,
    Reference,
    ValueBinding,
)
from prism.language.kernel import (
    Kernel,
    serialize_module,
)
from prism.language.workflows import (
    Agent,
    ExecutionScope,
    ReasoningDefinition,
    RelationDefinition,
    WorkflowDefinition,
)
from prism.language.workflows import (
    Tool as IRTool,
)
from prism.runtime.replay import EffectRecorder
from prism.runtime.results import RunOutput, TraceEvent

from . import (
    builtins,
    calls,
    effects,
    expressions,
    host_values,
    nodes,
    reasoning,
    sources,
    workflows,
)
from .provenance import ProvenanceTracker, ValueEnvironment
from .values import (
    CapabilityValue,
    ToolValue,
    _AgentCallable,
    _Callable,
    _ReasoningFactory,
    _RecordFactory,
    _RelationFactory,
    _value_status,
    _WorkflowFactory,
)


def run(
    program: ExecutableProgram,
    *,
    handler: EffectHandler,
    kernel: Kernel | None = None,
    resource_resolver: Any | None = None,
    effect_recorder: EffectRecorder | None = None,
    knowledge_broker: Any | None = None,
    entry_arguments: Mapping[str, Any] | None = None,
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
        entry_arguments,
    )
    engine.preflight()
    return engine.execute()


class _Engine:
    """Shared execution state with methods organized by runtime responsibility.

    Explicit bindings below keep recursive evaluation on the same engine while
    letting each implementation live beside its related operations.
    """

    def __init__(
        self,
        program,
        handler,
        kernel,
        resolver,
        recorder,
        broker,
        entry_arguments,
    ) -> None:
        self.program = program
        self.handler = handler
        self.kernel = kernel
        self.resource_resolver = resolver
        self.effect_recorder = recorder
        self.knowledge_broker = broker
        self.entry_arguments = entry_arguments
        self.trace: list[TraceEvent] = []
        self.call_counter = 0
        self.run_id = str(uuid4())
        self.occurrence_counter = 0
        self.workflow_counter = 0
        self._workflow_invocation_stack: list[str] = []
        self.global_env = ValueEnvironment()
        self.provenance = ProvenanceTracker(self.effect_recorder.store)
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
            self.provenance.record(result, "computed", "program without entry")
        else:
            callable_value = self.global_env[entry]
            definition = callable_value.definition
            arguments = self._entry_arguments(definition)
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
            provenance=self.provenance.snapshot(),
            metadata={
                "run_id": self.run_id,
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
        self._install_callables()
        self._install_bindings()

    def _install_callables(self) -> None:
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

    def _install_bindings(self) -> None:
        for declaration in self.program.declarations:
            if isinstance(declaration, ValueBinding):
                self._execute_statement(declaration, self.global_env)
            elif isinstance(declaration, IRTool):
                self.global_env[declaration.name] = ToolValue(
                    declaration.name,
                    self._eval(declaration.callable, self.global_env),
                )

    _entry_arguments = host_values._entry_arguments
    _is_capability = staticmethod(host_values._is_capability)
    _entry_argument = host_values._entry_argument
    _host_value = host_values._host_value
    _resolve_alias = host_values._resolve_alias
    _host_variant = host_values._host_variant
    _invalid_host_value = staticmethod(host_values._invalid_host_value)

    _invoke_function = calls._invoke_function
    _execute_statements = expressions._execute_statements
    _execute_statement = expressions._execute_statement
    _eval = expressions._eval
    _field = expressions._field
    _call = calls._call
    _bind_arguments = calls._bind_arguments

    _solve_reasoning = workflows._solve_reasoning
    _execute_workflow = workflows._execute_workflow
    _execute_reasoning_switch = workflows._execute_reasoning_switch
    _execute_composition = workflows._execute_composition

    _execute_workflow_node = nodes._execute_workflow_node

    _reasoning_configuration_bindings = reasoning._reasoning_configuration_bindings
    _materialize_reasoning = reasoning._materialize_reasoning

    _call_builtin = builtins._call_builtin
    _checked_module_hash = builtins._checked_module_hash

    _invoke_effect = effects._invoke_effect
    _effect_metadata = effects._effect_metadata
    _json_schema = effects._json_schema
    _validate_effect_result = effects._validate_effect_result
    _protected_types = effects._protected_types

    _query_source = sources._query_source


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
