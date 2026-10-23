# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Total reasoning configuration and its occurrence, relation, and switch bindings."""

from __future__ import annotations

from dataclasses import replace

from prism.language.core import (
    CallableContract,
    CoreType,
)
from prism.language.core.declarations import ReasoningInvocationContract
from prism.language.core.indices import ValueIndex

from ...syntax.ast import (
    CallExpr,
    ReasoningDecl,
)
from ..base import _CheckerPhase
from ..helpers import (
    _composition_aliases,
    _composition_nodes,
    _failure_union,
    _implementation_shape,
    _substitute,
    _substitute_indices,
)


class _ReasoningConfiguration:
    """Check named topology bindings and collect the configured callable's types.

    Occurrence aliases, related-edge aliases, and switch targets form the
    configuration schema. Concrete workflow parameters not supplied by the
    abstract topology become parameters of the resulting callable.
    """

    def __init__(
        self,
        checker: _CheckerPhase,
        reasoning_name: str,
        contract: CallableContract,
        declaration: ReasoningDecl,
        expression: CallExpr,
        argument_types: list[tuple[str | None, CoreType]],
    ) -> None:
        self.checker = checker
        self.reasoning_name = reasoning_name
        substitutions = self._configuration_specialization(
            contract, expression, argument_types
        )
        self.specialization = tuple(
            substitutions[name] for name in contract.type_parameters
        )
        self.contract = replace(
            contract,
            parameters=tuple(
                replace(parameter, type=_substitute(parameter.type, substitutions))
                for parameter in contract.parameters
            ),
            result=_substitute(contract.result, substitutions),
        )
        self.type_substitutions = substitutions
        self.declaration = declaration
        self.expression = expression
        self.argument_types = argument_types

    def _configuration_specialization(self, contract, expression, arguments):
        substitutions = {
            name: self.checker._type(argument)
            for name, argument in zip(
                contract.type_parameters, expression.type_arguments, strict=False
            )
        }
        if not expression.type_arguments and contract.type_parameters:
            methods = self.checker.reasoning_methods.get(self.reasoning_name, {})
            for name, implementation in arguments:
                method = methods.get(name)
                success, _, _ = _implementation_shape(implementation)
                if method is None or success is None or not implementation.parameters:
                    continue
                self.checker._unify(
                    method.parameters[0][1],
                    implementation.parameters[0][1],
                    substitutions,
                    expression.span,
                    "reasoning specialization input",
                )
                self.checker._unify(
                    method.result,
                    success,
                    substitutions,
                    expression.span,
                    "reasoning specialization result",
                )
        missing = set(contract.type_parameters) - substitutions.keys()
        if missing:
            self.checker.fail(
                f"cannot infer reasoning specialization: {', '.join(sorted(missing))}",
                expression.span,
                "type-reasoning-specialization",
            )
        return substitutions

    def check(self) -> tuple[CoreType, tuple[str, ...]]:
        self._check_bindings()

        self.by_name = {
            name: type_ for name, type_ in self.argument_types if name is not None
        }
        occurrence_names = tuple(
            self.checker.reasoning_methods.get(self.reasoning_name, {})
        )
        self.method_contracts = {
            name: _substitute(type_, self.type_substitutions)
            for name, type_ in self.checker.reasoning_methods.get(
                self.reasoning_name, {}
            ).items()
        }
        self.abstract_inputs = {
            item.name: item.type for item in self.contract.parameters
        }
        self.external_inputs: dict[str, CoreType] = {}
        self.occurrence_outputs: dict[str, CoreType] = {
            name: _substitute(type_, self.type_substitutions)
            for name, type_ in self.checker.reasoning_outputs[
                self.reasoning_name
            ].items()
        }
        self.failures: list[CoreType] = []
        self.implementation_effects: list[str] = []

        self.selected = self.declaration.result_alias
        if self.selected is None:
            terminals = _composition_aliases(
                self.declaration.composition, terminal_only=True
            )
            self.selected = terminals[0] if len(terminals) == 1 else None

        for occurrence in occurrence_names:
            self._check_occurrence(occurrence)

        for node in _composition_nodes(self.declaration.composition):
            if not node.alias or not node.relation:
                continue
            self._check_relation(node)

        switch_names = {
            exit_.target.rsplit(".", 1)[-1]
            for exit_ in self.declaration.exits
            if exit_.action == "switch" and exit_.target
        }
        for switch_name in switch_names:
            self._check_switch(switch_name)

        if any(exit_.action == "stop" for exit_ in self.declaration.exits):
            self.failures.append(
                CoreType("ReasoningStopped", (CoreType(self.reasoning_name),))
            )
        failure = _failure_union(self.failures)
        effects = tuple(dict.fromkeys(self.implementation_effects))
        workflow_type = CoreType(
            "Workflow",
            (
                self.contract.result,
                failure,
                *(CoreType(item) for item in effects),
            ),
            invocation=ReasoningInvocationContract(
                self.checker.scope.resolve(self.reasoning_name).identity,
                self.contract.parameters,
                self.specialization,
            ),
        )
        invocation_parameters = (
            *((item.name, item.type) for item in self.contract.parameters),
            *(
                (name, type_)
                for name, type_ in self.external_inputs.items()
                if name not in self.abstract_inputs
            ),
        )
        return (
            CoreType(
                "Function",
                parameters=invocation_parameters,
                result=workflow_type,
            ),
            (),
        )

    def _check_bindings(self):
        if any(name is None for name, _ in self.argument_types):
            self.checker.fail(
                f"reasoning configuration `{self.reasoning_name}` requires named bindings",
                self.expression.span,
                "type-reasoning-configuration-binding",
            )
        expected_order = self.checker._reasoning_configuration_names(
            self.reasoning_name, self.declaration
        )
        if len(set(expected_order)) != len(expected_order):
            duplicates = sorted(
                name for name in set(expected_order) if expected_order.count(name) > 1
            )
            self.checker.fail(
                f"reasoning `{self.reasoning_name}` has ambiguous configuration slots: "
                + ", ".join(duplicates),
                self.declaration.span,
                "type-reasoning-configuration-ambiguous",
            )
        expected = set(expected_order)
        supplied = {name for name, _ in self.argument_types if name is not None}
        if supplied != expected:
            missing = [name for name in expected_order if name not in supplied]
            extra = sorted(supplied - expected)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("extra " + ", ".join(extra))
            self.checker.fail(
                f"reasoning configuration `{self.reasoning_name}` is not total: "
                + "; ".join(details),
                self.expression.span,
                "type-reasoning-configuration-total",
            )

    def _check_adapter_inputs(self, adapter_type, adapter_name, adapter_substitutions):
        for parameter_name, parameter_type in adapter_type.parameters[1:]:
            if parameter_name is None:
                self.checker.fail(
                    f"additional inputs for adapter `{adapter_name}` must be named",
                    self.expression.span,
                    "type-reasoning-configuration-input-adapter",
                )
            inferred_parameter = _substitute(parameter_type, adapter_substitutions)
            provided = self.abstract_inputs.get(parameter_name)
            if provided is not None:
                self.checker._expect(
                    provided,
                    inferred_parameter,
                    self.expression.span,
                    f"input adapter parameter `{parameter_name}` of `{adapter_name}`",
                )
                continue
            previous = self.external_inputs.get(parameter_name)
            if previous is None:
                self.external_inputs[parameter_name] = inferred_parameter
            else:
                self.checker._expect(
                    previous,
                    inferred_parameter,
                    self.expression.span,
                    f"shared input adapter parameter `{parameter_name}`",
                )

    def _check_materializer_inputs(self, value_type, occurrence, substitutions):
        for parameter_name, parameter_type in value_type.parameters[1:]:
            if parameter_name is None:
                self.checker.fail(
                    f"additional materializer inputs for `{occurrence}` must be named",
                    self.expression.span,
                    "type-reasoning-configuration-input",
                )
            inferred_parameter = _substitute(parameter_type, substitutions)
            provided = self.abstract_inputs.get(parameter_name)
            if provided is not None:
                self.checker._expect(
                    provided,
                    inferred_parameter,
                    self.expression.span,
                    f"materializer input `{parameter_name}` of `{occurrence}`",
                )
                continue
            previous = self.external_inputs.get(parameter_name)
            if previous is None:
                self.external_inputs[parameter_name] = inferred_parameter
            else:
                self.checker._expect(
                    previous,
                    inferred_parameter,
                    self.expression.span,
                    f"shared materializer input `{parameter_name}`",
                )

    def _check_switch_inputs(self, target_type, switch_name):
        for parameter_name, parameter_type in target_type.parameters[1:]:
            if parameter_name is None:
                self.checker.fail(
                    f"additional inputs for switch `{switch_name}` must be named",
                    self.expression.span,
                    "type-reasoning-configuration-switch",
                )
            provided = self.abstract_inputs.get(parameter_name)
            if provided is not None:
                self.checker._expect(
                    provided,
                    parameter_type,
                    self.expression.span,
                    f"switch input `{parameter_name}` of `{switch_name}`",
                )
                continue
            previous = self.external_inputs.get(parameter_name)
            if previous is None:
                self.external_inputs[parameter_name] = parameter_type
            else:
                self.checker._expect(
                    previous,
                    parameter_type,
                    self.expression.span,
                    f"shared switch input `{parameter_name}`",
                )

    def _check_occurrence(self, occurrence):
        value_type = self.by_name[occurrence]
        success, failure, row = _implementation_shape(value_type)
        if success is None:
            self.checker.fail(
                f"occurrence binding `{occurrence}` is not a callable or workflow",
                self.expression.span,
                "type-reasoning-configuration-callable",
            )

        method_type = self.method_contracts.get(occurrence)
        if method_type is None or len(method_type.parameters) != 1:
            self.checker.fail(
                f"occurrence `{occurrence}` has no specialized method contract",
                self.expression.span,
                "type-reasoning-configuration-contract",
            )
        node = next(
            item
            for item in _composition_nodes(self.declaration.composition)
            if item.alias == occurrence
        )
        if self.checker._reasoning_node_requires_input_adapter(
            node, self.checker.reasoning_methods.get(self.reasoning_name, {})
        ):
            self._check_input_adapter(occurrence, node, method_type)
        if not value_type.parameters:
            self.checker.fail(
                f"occurrence binding `{occurrence}` must accept the method's "
                "logical input as its first parameter",
                self.expression.span,
                "type-reasoning-configuration-input",
            )
        substitutions: dict[str, CoreType] = {}
        self.checker._unify(
            value_type.parameters[0][1],
            method_type.parameters[0][1],
            substitutions,
            self.expression.span,
            f"occurrence binding `{occurrence}` input",
        )
        self._check_materializer_inputs(value_type, occurrence, substitutions)

        success = _substitute(success, substitutions)
        failure = _substitute(failure, substitutions) if failure else None
        expected_success = method_type.result or CoreType("Unit")
        self.checker._expect(
            expected_success,
            success,
            self.expression.span,
            f"occurrence binding `{occurrence}` result",
        )
        self.occurrence_outputs[occurrence] = expected_success

        if occurrence == self.selected:
            self.checker._expect(
                self.contract.result,
                expected_success,
                self.expression.span,
                f"reasoning occurrence `{occurrence}` output",
            )
        self._check_dispositions(occurrence, expected_success)
        if failure is not None and failure.name != "Never":
            self.failures.append(failure)
        self.implementation_effects.extend(row)

    def _check_input_adapter(self, occurrence, node, method_type):
        adapter_name = f"{occurrence}_input"
        adapter_type = self.by_name[adapter_name]
        if not adapter_type.is_function or not adapter_type.parameters:
            self.checker.fail(
                f"input adapter `{adapter_name}` must be a callable whose first "
                "parameter accepts the topology input",
                self.expression.span,
                "type-reasoning-configuration-input-adapter",
            )
        if adapter_type.effects:
            self.checker.fail(
                f"input adapter `{adapter_name}` must be pure",
                self.expression.span,
                "type-reasoning-configuration-input-adapter",
            )
        if not isinstance(node.component, CallExpr):
            self.checker.fail(
                f"input adapter `{adapter_name}` requires a called occurrence",
                self.expression.span,
                "type-reasoning-configuration-input-adapter",
            )
        logical_input = node.component.arguments[0].value
        topology_input = _substitute(
            self.checker.expression_types[id(logical_input)], self.type_substitutions
        )
        adapter_substitutions: dict[str, CoreType] = {}
        self.checker._unify(
            adapter_type.parameters[0][1],
            topology_input,
            adapter_substitutions,
            self.expression.span,
            f"input adapter `{adapter_name}` topology input",
        )
        self._check_adapter_inputs(adapter_type, adapter_name, adapter_substitutions)
        adapter_result = _substitute(
            adapter_type.result or CoreType("Unit"), adapter_substitutions
        )
        self.checker._expect(
            method_type.parameters[0][1],
            adapter_result,
            self.expression.span,
            f"input adapter `{adapter_name}` result",
        )

    def _check_dispositions(self, occurrence, expected_success):
        for guarded_exit in (
            item for item in self.declaration.exits if item.occurrence == occurrence
        ):
            selectors = self.checker._disposition_selectors(expected_success)
            if guarded_exit.selector not in selectors:
                available_selectors = (
                    f"; available dispositions: {', '.join(sorted(selectors))}"
                    if selectors
                    else ""
                )
                self.checker.fail(
                    f"configured occurrence `{occurrence}` returns "
                    f"`{expected_success.render()}`, which has no disposition "
                    f"`{guarded_exit.selector}`{available_selectors}",
                    self.expression.span,
                    "type-reasoning-configuration-disposition",
                )

    def _check_relation(self, node):
        field_name = f"{node.alias}_by"
        relation_type = self.by_name[field_name]
        if not relation_type.is_function or len(relation_type.parameters) != 2:
            self.checker.fail(
                f"`{field_name}` must be a pure two-input relation builder",
                self.expression.span,
                "type-reasoning-configuration-relation",
            )
        if relation_type.effects:
            self.checker.fail(
                f"relation builder `{field_name}` must be pure",
                self.expression.span,
                "type-reasoning-configuration-relation",
            )
        method_type = self.method_contracts.get(node.alias) or _substitute(
            self.checker.expression_types[id(node.component.callee)],
            self.type_substitutions,
        )
        source_type = method_type.parameters[0][1]
        target_type = method_type.result or CoreType("Unit")
        relation_contract = self.checker._resolve_relation(node.relation, node.span)
        contract_substitutions: dict[str, CoreType] = {}
        self.checker._unify(
            relation_contract.parameters[0].type,
            source_type,
            contract_substitutions,
            self.expression.span,
            f"relation builder `{field_name}` source",
        )
        self.checker._unify(
            relation_contract.parameters[1].type,
            target_type,
            contract_substitutions,
            self.expression.span,
            f"relation builder `{field_name}` target",
        )
        expected_certificate = _substitute(
            relation_contract.result, contract_substitutions
        )
        builder_substitutions: dict[str, CoreType] = {}
        self.checker._unify(
            relation_type.parameters[0][1],
            source_type,
            builder_substitutions,
            self.expression.span,
            f"relation builder `{field_name}` source",
        )
        self.checker._unify(
            relation_type.parameters[1][1],
            target_type,
            builder_substitutions,
            self.expression.span,
            f"relation builder `{field_name}` target",
        )
        certificate, relation_failure, relation_effects = _implementation_shape(
            relation_type
        )
        if certificate is None:
            self.checker.fail(
                f"relation builder `{field_name}` must return a certificate",
                self.expression.span,
                "type-reasoning-configuration-relation",
            )
        if relation_effects:
            self.checker.fail(
                f"relation builder `{field_name}` must be pure",
                self.expression.span,
                "type-reasoning-configuration-relation",
            )
        bindings = {
            identity: ValueIndex(
                "reference", parameter.identity or parameter.name, label=parameter.name
            )
            for identity, parameter in zip(
                relation_type.parameter_bindings,
                relation_contract.parameters,
                strict=True,
            )
        }
        self.checker._expect(
            expected_certificate,
            _substitute_indices(
                _substitute(certificate, builder_substitutions), bindings
            ),
            self.expression.span,
            f"relation builder `{field_name}` certificate",
        )
        if relation_failure is not None and relation_failure.name != "Never":
            self.failures.append(_substitute(relation_failure, builder_substitutions))

    def _check_switch(self, switch_name):
        target_type = self.by_name[switch_name]
        success, failure, row = _implementation_shape(target_type)
        if success is None or not target_type.parameters:
            self.checker.fail(
                f"switch `{switch_name}` must accept the handoff as its first input",
                self.expression.span,
                "type-reasoning-configuration-switch",
            )
        handoff_types = {
            self.occurrence_outputs[exit_.occurrence]
            for exit_ in self.declaration.exits
            if exit_.action == "switch"
            and exit_.target
            and exit_.target.rsplit(".", 1)[-1] == switch_name
        }
        for handoff_type in handoff_types:
            self.checker._expect(
                target_type.parameters[0][1],
                handoff_type,
                self.expression.span,
                f"switch `{switch_name}` handoff",
            )
        self._check_switch_inputs(target_type, switch_name)
        self.checker._expect(
            self.contract.result,
            success,
            self.expression.span,
            f"switch `{switch_name}` output",
        )
        if failure is not None and failure.name != "Never":
            self.failures.append(failure)
        self.implementation_effects.extend(row)
