# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Executable workflow composition, convergence, and occurrence checking."""

from __future__ import annotations

from typing import Any

from prism.language.core import (
    BindingScope,
    CoreType,
)
from prism.language.core import Parameter as CoreParameter

from ..syntax.ast import (
    CallExpr,
    ChoiceComposition,
    NodeOccurrence,
    ParallelComposition,
    RepeatComposition,
    SequenceComposition,
)
from .base import _CheckerPhase
from .helpers import (
    _expression_name,
    _unique_types,
)


class _CompositionCheckingMixin(_CheckerPhase):
    def _check_workflow_composition(
        self,
        composition: Any,
        environment: dict[str, CoreType],
        occurrences: dict[str, CoreType],
    ) -> tuple[
        dict[str, CoreType], tuple[str, ...], tuple[CoreType, ...], tuple[str, ...]
    ]:
        if getattr(composition, "relation", None) is not None:
            self.fail(
                "`by Relation` belongs to an abstract reasoning edge; executable "
                "workflow edges receive relation builders through materialization",
                composition.span,
                "type-workflow-abstract-relation",
            )
        if isinstance(composition, NodeOccurrence):
            return self._check_workflow_node(composition, environment, occurrences)
        if isinstance(composition, SequenceComposition):
            return self._check_workflow_sequence(composition, environment, occurrences)
        if isinstance(composition, ParallelComposition):
            return self._check_workflow_parallel(composition, environment, occurrences)
        if isinstance(composition, ChoiceComposition):
            return self._check_workflow_choice(composition, environment, occurrences)
        if isinstance(composition, RepeatComposition):
            return self._check_workflow_repeat(composition, environment, occurrences)
        self.fail(
            "unsupported workflow composition",
            composition.span,
            "type-workflow-composition",
        )

    def _check_workflow_node(
        self,
        node: NodeOccurrence,
        environment: dict[str, CoreType],
        occurrences: dict[str, CoreType],
    ) -> tuple[
        dict[str, CoreType], tuple[str, ...], tuple[CoreType, ...], tuple[str, ...]
    ]:
        component_name = _expression_name(
            node.component.callee
            if isinstance(node.component, CallExpr)
            else node.component
        )
        contract = self.callables.get(component_name)
        component_scope = BindingScope(
            {
                name: binding
                for name, binding in self.scope.snapshot().items()
                if name not in environment
            }
        )
        for name, type_ in environment.items():
            self._bind_local(component_scope, name, type_, node.span)
        component_type, reference_effects = self._infer(
            node.component, component_scope, None
        )
        failures: list[CoreType] = []
        effects = list(reference_effects)
        parameters, result = self._workflow_component_contract(
            node, component_name, contract, component_type, effects, failures
        )
        self._check_workflow_inputs(parameters, component_name, environment, node)
        if result.name == "Result" and len(result.arguments) == 2:
            result, failure = result.arguments
            if failure.name != "Never":
                failures.append(failure)
        alias = node.alias or component_name.rsplit(".", 1)[-1]
        if alias in occurrences or alias in environment:
            carried = (
                self.repeat_rebindable[-1].get(alias)
                if self.repeat_rebindable
                else None
            )
            if carried is None:
                self.fail(
                    f"duplicate workflow occurrence `{alias}`",
                    node.span,
                    "type-workflow-duplicate-occurrence",
                )
            self._expect(
                carried,
                result,
                node.span,
                f"repeat loop-carried output `{alias}`",
            )
        occurrences[alias] = result
        updated = dict(environment)
        updated[alias] = result
        return (
            updated,
            tuple(dict.fromkeys(effects)),
            _unique_types(failures),
            (alias,),
        )

    def _check_workflow_sequence(self, composition, environment, occurrences):
        current = dict(environment)
        effects: list[str] = []
        failures: list[CoreType] = []
        last_terminals: tuple[str, ...] = ()
        for child in composition.children:
            current, child_effects, child_failures, last_terminals = (
                self._check_workflow_composition(child, current, occurrences)
            )
            effects.extend(child_effects)
            failures.extend(child_failures)
        return (
            current,
            tuple(dict.fromkeys(effects)),
            _unique_types(failures),
            last_terminals,
        )

    def _check_workflow_parallel(self, composition, environment, occurrences):
        joined = dict(environment)
        effects: list[str] = []
        failures: list[CoreType] = []
        parallel_terminals: list[str] = []
        base_occurrences = dict(occurrences)
        for child in composition.children:
            branch_occurrences = dict(base_occurrences)
            branch, child_effects, child_failures, child_terminals = (
                self._check_workflow_composition(
                    child, dict(environment), branch_occurrences
                )
            )
            for name, type_ in branch.items():
                if name in environment:
                    continue
                if name in joined:
                    self.fail(
                        f"parallel branches produce conflicting occurrence `{name}`",
                        composition.span,
                        "type-workflow-parallel-conflict",
                    )
                joined[name] = type_
            for name, type_ in branch_occurrences.items():
                if name not in base_occurrences:
                    occurrences[name] = type_
            effects.extend(child_effects)
            failures.extend(child_failures)
            parallel_terminals.extend(child_terminals)
        return (
            joined,
            tuple(dict.fromkeys(effects)),
            _unique_types(failures),
            tuple(parallel_terminals),
        )

    def _check_workflow_choice(self, composition, environment, occurrences):
        routed, router_effects, router_failures, _ = self._check_workflow_node(
            composition.router, environment, occurrences
        )
        router_alias = (
            composition.router.alias
            or _expression_name(composition.router.component).rsplit(".", 1)[-1]
        )
        router_type = self.aliases.get(routed[router_alias].name, routed[router_alias])
        variants = self.variants.get(router_type.name)
        if variants is None:
            self.fail(
                "choice router must produce a closed sum type",
                composition.router.span,
                "type-workflow-choice-router",
            )
        self._check_choice_patterns(composition, variants)
        base_occurrences = dict(occurrences)
        branch_outputs: list[dict[str, CoreType]] = []
        branch_occurrences_list: list[dict[str, CoreType]] = []
        choice_terminals: tuple[str, ...] = ()
        all_effects = list(router_effects)
        all_failures = list(router_failures)
        for arm in composition.arms:
            branch = dict(routed)
            branch_occurrences = dict(base_occurrences)
            branch_terminals: tuple[str, ...] = ()
            for child in arm.children:
                branch, child_effects, child_failures, branch_terminals = (
                    self._check_workflow_composition(child, branch, branch_occurrences)
                )
                all_effects.extend(child_effects)
                all_failures.extend(child_failures)
            produced = {
                name: type_ for name, type_ in branch.items() if name not in routed
            }
            branch_outputs.append(produced)
            branch_occurrences_list.append(branch_occurrences)
            if not choice_terminals:
                choice_terminals = branch_terminals
        shared_outputs = self._check_choice_convergence(composition, branch_outputs)
        converged = dict(routed)
        converged.update(shared_outputs)
        for branch_occurrences in branch_occurrences_list:
            for name, type_ in branch_occurrences.items():
                if name in occurrences or name not in converged:
                    continue
                occurrences[name] = type_
        return (
            converged,
            tuple(dict.fromkeys(all_effects)),
            _unique_types(all_failures),
            choice_terminals,
        )

    def _check_workflow_repeat(self, composition, environment, occurrences):
        policy_scope = BindingScope(
            {
                name: binding
                for name, binding in self.scope.snapshot().items()
                if name not in environment
            }
        )
        for name, type_ in environment.items():
            self._bind_local(policy_scope, name, type_, composition.span)
        policy_type, policy_effects = self._infer(
            composition.policy, policy_scope, None
        )
        if policy_effects:
            self.fail(
                "repeat policy expressions must be pure",
                composition.span,
                "type-workflow-repeat-policy",
            )
        if policy_type.name != "RefinementPolicy":
            self.fail(
                "repeat policy expression must have RefinementPolicy type",
                composition.span,
                "type-workflow-repeat-policy",
            )
        current = dict(environment)
        effects: list[str] = []
        failures: list[CoreType] = []
        repeat_terminals: tuple[str, ...] = ()
        self.repeat_rebindable.append(dict(environment))
        try:
            for child in composition.children:
                current, child_effects, child_failures, repeat_terminals = (
                    self._check_workflow_composition(child, current, occurrences)
                )
                effects.extend(child_effects)
                failures.extend(child_failures)
        finally:
            self.repeat_rebindable.pop()
        self._check_repeat_until(
            composition.until,
            current,
            composition.span,
            owner="workflow",
        )
        return (
            current,
            tuple(dict.fromkeys(effects)),
            _unique_types(failures),
            repeat_terminals,
        )

    def _check_choice_patterns(self, composition, variants) -> None:
        patterns = tuple(
            arm.pattern.split("(", 1)[0].strip() for arm in composition.arms
        )
        concrete = tuple(pattern for pattern in patterns if pattern != "_")
        if len(set(concrete)) != len(concrete):
            self.fail(
                "choice contains duplicate constructor cases",
                composition.span,
                "type-workflow-choice-duplicate",
            )
        unknown = set(concrete) - set(variants)
        if unknown:
            self.fail(
                "choice has unknown cases: " + ", ".join(sorted(unknown)),
                composition.span,
                "type-workflow-choice-case",
            )
        missing = set(variants) - set(concrete)
        if missing and "_" not in patterns:
            self.fail(
                "choice is not exhaustive; missing cases: "
                + ", ".join(sorted(missing)),
                composition.span,
                "type-workflow-choice-exhaustive",
            )

    def _check_choice_convergence(
        self, composition, branch_outputs
    ) -> dict[str, CoreType]:
        # Names present in only some arms are branch-local intermediates. Only
        # the common, type-compatible outputs are visible after the choice.
        shared = set.intersection(*(set(produced) for produced in branch_outputs))
        if not shared and any(branch_outputs):
            self.fail(
                "choice arms must converge to shared occurrence outputs",
                composition.span,
                "type-workflow-choice-convergence",
            )
        for produced in branch_outputs[1:]:
            for name in shared:
                self._expect(
                    branch_outputs[0][name],
                    produced[name],
                    composition.span,
                    f"choice output `{name}`",
                )
        return {
            name: type_ for name, type_ in branch_outputs[0].items() if name in shared
        }

    def _workflow_component_contract(
        self, node, component_name, contract, component_type, effects, failures
    ):
        if contract is not None:
            if isinstance(node.component, CallExpr):
                parameters = ()
                result = component_type
                if contract.kind == "workflow":
                    if result.name != "Workflow" or len(result.arguments) < 2:
                        self.fail(
                            f"workflow invocation `{component_name}` has an invalid type",
                            node.span,
                            "type-workflow-component",
                        )
                    success, failure, *effect_types = result.arguments
                    result = success
                    effects.extend(item.name for item in effect_types)
                    if failure.name != "Never":
                        failures.append(failure)
            else:
                parameters = contract.parameters
                result = contract.result
                effects.extend(contract.effects)
                if contract.kind == "workflow":
                    failure = contract.failure or CoreType("Never")
                    if failure.name != "Never":
                        failures.append(failure)
        else:
            return self._workflow_value_contract(
                node, component_name, component_type, effects
            )
        return parameters, result

    def _check_workflow_inputs(
        self, parameters, component_name, environment, node
    ) -> None:
        for parameter in parameters:
            if not parameter.name:
                self.fail(
                    f"workflow component `{component_name}` has an unnamed input port",
                    node.span,
                    "type-workflow-port-name",
                )
            if parameter.name not in environment:
                self.fail(
                    f"workflow component `{component_name}` requires unavailable input `{parameter.name}`",
                    node.span,
                    "type-workflow-missing-input",
                )
            self._expect(
                parameter.type,
                environment[parameter.name],
                node.span,
                f"workflow input `{parameter.name}`",
            )

    def _workflow_value_contract(self, node, component_name, component_type, effects):
        invocation = component_type
        if invocation.name == "Tool" and len(invocation.arguments) == 1:
            invocation = self.aliases.get(
                invocation.arguments[0].name, invocation.arguments[0]
            )
        if not invocation.is_function:
            self.fail(
                f"workflow component `{component_name}` is not callable",
                node.span,
                "type-workflow-component",
            )
        parameters = tuple(
            CoreParameter(name or "", type_) for name, type_ in invocation.parameters
        )
        result = invocation.result or CoreType("Unit")
        effects.extend(invocation.effects)
        return parameters, result
