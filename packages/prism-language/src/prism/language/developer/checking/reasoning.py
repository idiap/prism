# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Abstract reasoning methods, topology, and guarded exits."""

from __future__ import annotations

from typing import Any

from prism.language.core import (
    BindingScope,
    CallableContract,
    CoreType,
)

from ..diagnostics import PrismTypeError, SourceSpan
from ..syntax.ast import (
    CallExpr,
    ChoiceComposition,
    NodeOccurrence,
    ParallelComposition,
    ReasoningDecl,
    RepeatComposition,
    SequenceComposition,
)
from .base import _CheckerPhase
from .helpers import (
    _composition_aliases,
    _expression_name,
    _expression_values,
    _substitute,
)
from .reasoning_purity import operational_dependency


class _ReasoningCheckingMixin(_CheckerPhase):
    def _check_reasoning(self, declaration: ReasoningDecl) -> None:
        if declaration.name == "main":
            self.fail(
                "reasoning declarations are templates; the application entry is `def main`",
                declaration.span,
                "type-reasoning-main",
            )
        contract = self.callables[declaration.name]
        for parameter in contract.parameters:
            if operational_dependency(self, parameter.type) is not None:
                self.fail(
                    f"reasoning input `{parameter.name}` cannot carry operational type "
                    f"`{parameter.type.render()}`",
                    declaration.span,
                    "type-reasoning-operational-input",
                )
        self._check_reasoning_value_type(contract.result, declaration.span)
        environment = {item.name: item.type for item in contract.parameters}
        occurrences: dict[str, CoreType] = {}
        methods: dict[str, CoreType] = {}
        self._check_reasoning_composition(
            declaration.composition,
            environment,
            occurrences,
            methods,
            has_prior=False,
            local_type_names=set(declaration.type_parameters),
        )
        selected = declaration.result_alias
        if selected is None:
            terminals = _composition_aliases(
                declaration.composition, terminal_only=True
            )
            if len(terminals) != 1:
                self.fail(
                    f"reasoning `{declaration.name}` has multiple terminal occurrences; "
                    "select one with `return alias`",
                    declaration.span,
                    "type-reasoning-terminal",
                )
            selected = terminals[0]
        if selected not in occurrences:
            self.fail(
                f"reasoning `{declaration.name}` returns unknown occurrence `{selected}`",
                declaration.span,
                "type-reasoning-return",
            )
        self._expect(
            contract.result,
            occurrences[selected],
            declaration.span,
            f"reasoning `{declaration.name}` result",
        )
        self._check_reasoning_exits(declaration, occurrences, contract)
        self.reasoning_outputs[declaration.name] = dict(occurrences)
        self.reasoning_methods[declaration.name] = dict(methods)

    def _check_reasoning_composition(
        self,
        composition: Any,
        environment: dict[str, CoreType],
        occurrences: dict[str, CoreType],
        methods: dict[str, CoreType],
        *,
        has_prior: bool,
        local_type_names: set[str],
    ) -> tuple[dict[str, CoreType], bool]:
        relation = getattr(composition, "relation", None)
        if relation is not None and not isinstance(composition, NodeOccurrence):
            self.fail(
                "`by Relation` is allowed only on a reasoning occurrence",
                composition.span,
                "type-reasoning-relation-composition",
            )
        if isinstance(composition, NodeOccurrence):
            return self._check_reasoning_node(
                composition,
                environment,
                occurrences,
                methods,
                has_prior=has_prior,
                local_type_names=local_type_names,
            )
        if isinstance(composition, SequenceComposition):
            return self._check_reasoning_sequence(
                composition,
                environment,
                occurrences,
                methods,
                has_prior,
                local_type_names,
            )
        if isinstance(composition, RepeatComposition):
            return self._check_reasoning_repeat(
                composition,
                environment,
                occurrences,
                methods,
                has_prior,
                local_type_names,
            )
        if isinstance(composition, ParallelComposition):
            return self._check_reasoning_parallel(
                composition,
                environment,
                occurrences,
                methods,
                has_prior,
                local_type_names,
            )
        if isinstance(composition, ChoiceComposition):
            return self._check_reasoning_choice(
                composition,
                environment,
                occurrences,
                methods,
                has_prior,
                local_type_names,
            )
        self.fail(
            "unsupported reasoning composition",
            composition.span,
            "type-reasoning-composition",
        )

    def _check_reasoning_node(
        self,
        node: NodeOccurrence,
        environment: dict[str, CoreType],
        occurrences: dict[str, CoreType],
        methods: dict[str, CoreType],
        *,
        has_prior: bool,
        local_type_names: set[str],
    ) -> tuple[dict[str, CoreType], bool]:
        if node.alias is None:
            self.fail(
                "reasoning occurrences require stable aliases",
                node.span,
                "type-reasoning-occurrence-alias",
            )
        if not isinstance(node.component, CallExpr):
            self.fail(
                "reasoning occurrences call an imported reasoning-method contract",
                node.span,
                "type-reasoning-occurrence-call",
            )
        name = _expression_name(node.component.callee)
        local = BindingScope(
            {
                binding_name: binding
                for binding_name, binding in self.scope.snapshot().items()
                if binding_name not in environment
            }
        )
        for binding_name, type_ in environment.items():
            self._bind_local(local, binding_name, type_, node.span)
        alias = self.aliases.get(name)
        abstract_method = alias is not None and alias.is_function
        method_type = (
            self._reasoning_method_type(node, name, alias, local, local_type_names)
            if abstract_method
            else self._structural_helper_type(node, name, local)
        )
        self._check_reasoning_value_type(method_type, node.span)
        result = method_type.result or CoreType("Unit")
        self.expression_types[id(node.component.callee)] = method_type
        self.expression_types[id(node.component)] = result
        if node.relation is not None:
            self._check_reasoning_relation(node, method_type, result)
        alias = node.alias
        self._check_reasoning_rebinding(node, alias, environment, occurrences, result)
        occurrences[alias] = result
        if abstract_method:
            methods[alias] = method_type
        updated = dict(environment)
        updated[alias] = result
        return updated, True

    def _structural_helper_type(self, node, name, local):
        helper = self.callables.get(name)
        if helper is None or helper.kind != "def":
            self.fail(
                f"`{name}` is not a function-type reasoning method alias or a pure structural helper",
                node.span,
                "type-reasoning-occurrence-contract",
            )
        self._check_reasoning_value_type(helper.type, node.span)
        result, effects = self._infer(node.component, local, None)
        self._check_reasoning_expression(node.component)
        if effects:
            self.fail(
                "structural helpers must be pure",
                node.span,
                "type-reasoning-structural-helper",
            )
        self._check_reasoning_value_type(result, node.span)
        if result.name == "Result" and result.arguments[1].name == "Never":
            result = result.arguments[0]
        self.structural_helpers[name] = node.span
        inputs = tuple(
            self.expression_types[id(argument.value)]
            for argument in node.component.arguments
        )
        input_type = (
            inputs[0]
            if len(inputs) == 1
            else CoreType("Tuple", inputs)
            if inputs
            else CoreType("Unit")
        )
        return CoreType("Function", parameters=((None, input_type),), result=result)

    def _resolve_relation(self, name: str, span: SourceSpan) -> CallableContract:
        contract = self.callables.get(name)
        if contract is None or contract.kind != "relation":
            self.fail(
                f"`{name}` does not resolve to an imported relation declaration",
                span,
                "type-reasoning-relation-contract",
            )
        return contract

    def _check_reasoning_exits(self, declaration, occurrences, contract) -> None:
        seen_guards: set[tuple[str, str]] = set()
        for exit_ in declaration.exits:
            if exit_.occurrence not in occurrences:
                self.fail(
                    f"guarded exit references unknown occurrence `{exit_.occurrence}`",
                    exit_.span,
                    "type-reasoning-exit-occurrence",
                )
            guard = (exit_.occurrence, exit_.selector)
            if guard in seen_guards:
                self.fail(
                    f"duplicate guarded exit `{exit_.occurrence}.{exit_.selector}`",
                    exit_.span,
                    "type-reasoning-exit-overlap",
                )
            seen_guards.add(guard)
            output_type = occurrences[exit_.occurrence]
            selectors = self._disposition_selectors(output_type)
            if exit_.selector not in selectors:
                available = sorted(selectors)
                detail = (
                    f"; available dispositions: {', '.join(available)}"
                    if available
                    else ""
                )
                self.fail(
                    f"`{output_type.render()}` has no disposition "
                    f"`{exit_.selector}`{detail}",
                    exit_.span,
                    "type-reasoning-exit-selector",
                )
            if exit_.action == "switch":
                target = self.callables.get(exit_.target or "")
                if target is None or target.kind != "reasoning":
                    self.fail(
                        f"switch target `{exit_.target}` is not an imported reasoning declaration",
                        exit_.span,
                        "type-reasoning-switch-target",
                    )
                substitutions: dict[str, CoreType] = {}
                self._unify(
                    target.result,
                    contract.result,
                    substitutions,
                    exit_.span,
                    "reasoning switch result",
                )

    def _check_reasoning_sequence(
        self,
        composition,
        environment,
        occurrences,
        methods,
        has_prior,
        local_type_names,
    ):
        current = dict(environment)
        prior = has_prior
        for child in composition.children:
            current, prior = self._check_reasoning_composition(
                child,
                current,
                occurrences,
                methods,
                has_prior=prior,
                local_type_names=local_type_names,
            )
        return current, prior

    def _check_reasoning_parallel(
        self,
        composition,
        environment,
        occurrences,
        methods,
        has_prior,
        local_type_names,
    ):
        joined = dict(environment)
        for child in composition.children:
            branch, _ = self._check_reasoning_composition(
                child,
                dict(environment),
                occurrences,
                methods,
                has_prior=has_prior,
                local_type_names=local_type_names,
            )
            for name, type_ in branch.items():
                if name in environment:
                    continue
                if name in joined:
                    self.fail(
                        f"parallel branches produce conflicting occurrence `{name}`",
                        composition.span,
                        "type-reasoning-parallel-conflict",
                    )
                joined[name] = type_
        return joined, True

    def _check_reasoning_choice(
        self,
        composition,
        environment,
        occurrences,
        methods,
        has_prior,
        local_type_names,
    ):
        routed, _ = self._check_reasoning_node(
            composition.router,
            environment,
            occurrences,
            methods,
            has_prior=has_prior,
            local_type_names=local_type_names,
        )
        router_type = routed[composition.router.alias]
        router_type = self.aliases.get(router_type.name, router_type)
        variants = self.variants.get(router_type.name)
        if variants is None:
            self.fail(
                "choice router must produce a closed sum type",
                composition.router.span,
                "type-reasoning-choice-router",
            )
        self._check_choice_patterns(composition, variants)
        base_occurrences = dict(occurrences)
        base_methods = dict(methods)
        branch_outputs = []
        completed = []
        for arm in composition.arms:
            branch = dict(routed)
            branch_occurrences = dict(base_occurrences)
            branch_methods = dict(base_methods)
            for child in arm.children:
                branch, _ = self._check_reasoning_composition(
                    child,
                    branch,
                    branch_occurrences,
                    branch_methods,
                    has_prior=True,
                    local_type_names=local_type_names,
                )
            branch_outputs.append(
                {name: type_ for name, type_ in branch.items() if name not in routed}
            )
            completed.append((branch_occurrences, branch_methods))
        shared_outputs = self._check_choice_convergence(composition, branch_outputs)
        for branch_occurrences, branch_methods in completed:
            occurrences.update(
                {
                    name: type_
                    for name, type_ in branch_occurrences.items()
                    if name in routed or name in shared_outputs
                }
            )
            for name, type_ in branch_methods.items():
                if name in methods:
                    self._expect(
                        methods[name],
                        type_,
                        composition.span,
                        f"choice method `{name}`",
                    )
                methods[name] = type_
        return {**routed, **shared_outputs}, True

    def _check_reasoning_repeat(
        self,
        composition,
        environment,
        occurrences,
        methods,
        has_prior,
        local_type_names,
    ):
        policy_scope = BindingScope(
            {
                name: binding
                for name, binding in self.scope.snapshot().items()
                if name not in environment
            }
        )
        for name, type_ in environment.items():
            self._bind_local(policy_scope, name, type_, composition.span)
        policy, policy_effects = self._infer(composition.policy, policy_scope, None)
        self._check_reasoning_expression(
            composition.policy, allowed_calls=("refinement_policy",)
        )
        if policy_effects:
            self.fail(
                "reasoning repeat policy expressions must be pure",
                composition.span,
                "type-reasoning-repeat-policy",
            )
        if policy.name != "RefinementPolicy":
            self.fail(
                "reasoning repeat requires a bounded RefinementPolicy",
                composition.span,
                "type-reasoning-repeat-policy",
            )
        current = dict(environment)
        prior = has_prior
        self.repeat_rebindable.append(dict(environment))
        try:
            for child in composition.children:
                current, prior = self._check_reasoning_composition(
                    child,
                    current,
                    occurrences,
                    methods,
                    has_prior=prior,
                    local_type_names=local_type_names,
                )
        finally:
            self.repeat_rebindable.pop()
        self._check_repeat_until(
            composition.until,
            current,
            composition.span,
            owner="reasoning",
        )
        if composition.until is not None:
            self._check_reasoning_expression(composition.until)
        return current, prior

    def _reasoning_method_type(
        self, node, name, alias, local, local_type_names
    ) -> CoreType:
        if len(node.component.arguments) != 1:
            self.fail(
                f"reasoning method `{name}` requires one explicit logical input; "
                "group multiple inputs in a tuple or record",
                node.span,
                "type-reasoning-method-arity",
            )
        declared_parameters = self.type_parameters.get(name, ())
        if len(node.component.type_arguments) > len(declared_parameters):
            self.fail(
                f"reasoning method `{name}` accepts at most "
                f"{len(declared_parameters)} type arguments, got "
                f"{len(node.component.type_arguments)}",
                node.span,
                "type-call-type-arguments",
            )
        substitutions = {
            parameter: self._type(argument, local_type_names)
            for parameter, argument in zip(
                declared_parameters,
                node.component.type_arguments,
                strict=False,
            )
        }
        if len(alias.parameters) != 1:
            self.fail(
                f"reasoning method alias `{name}` must have one logical input",
                node.span,
                "type-reasoning-method-arity",
            )
        logical_input = node.component.arguments[0].value
        actual_input, effects = self._infer(logical_input, local, None)
        self._check_reasoning_value_type(actual_input, logical_input.span)
        self._check_reasoning_expression(logical_input)
        if effects:
            self.fail(
                "abstract reasoning arguments must be effect-free",
                node.span,
                "type-reasoning-effect",
            )
        try:
            self._unify(
                alias.parameters[0][1],
                actual_input,
                substitutions,
                node.span,
                f"reasoning method `{name}` input",
            )
        except PrismTypeError:
            unresolved_from_topology = [
                parameter
                for parameter in declared_parameters
                if parameter not in substitutions
            ]
            if unresolved_from_topology:
                raise
        unresolved = [
            parameter
            for parameter in declared_parameters
            if parameter not in substitutions
        ]
        if unresolved:
            self.fail(
                f"reasoning method `{name}` requires explicit result type "
                f"arguments: {', '.join(unresolved)}",
                node.span,
                "type-reasoning-method-result-index",
            )
        method_type = _substitute(alias, substitutions)
        return method_type

    def _check_reasoning_value_type(self, type_, span):
        dependency = operational_dependency(self, type_)
        if dependency is not None:
            self.fail(
                f"abstract reasoning cannot depend on operational type `{dependency}`",
                span,
                "type-reasoning-operational-value",
            )

    def _check_reasoning_expression(self, value, allowed_calls=()):
        for expression in _expression_values(value):
            type_ = self.expression_types.get(id(expression))
            if type_ is not None:
                self._check_reasoning_value_type(type_, expression.span)
            name = _expression_name(expression)
            if (
                name in self.callables
                and name not in allowed_calls
                and type_ is not None
                and type_.is_function
            ):
                self.structural_helpers[name] = expression.span
            if isinstance(expression, CallExpr):
                called = _expression_name(expression.callee)
                if called in self.callables and called not in allowed_calls:
                    self.structural_helpers[called] = expression.span
                if called not in self.callables and called not in self.records:
                    self.fail(
                        "abstract structure requires statically resolved helpers",
                        expression.span,
                        "type-reasoning-structural-helper",
                    )

    def _check_reasoning_relation(self, node, method_type, result) -> None:
        relation = self._resolve_relation(node.relation, node.span)
        if len(relation.parameters) != 2:
            self.fail(
                f"relation `{node.relation}` must declare source and target endpoints",
                node.span,
                "type-relation-endpoints",
            )
        substitutions: dict[str, CoreType] = {}
        self._unify(
            relation.parameters[0].type,
            method_type.parameters[0][1],
            substitutions,
            node.span,
            "relation source",
        )
        self._unify(
            relation.parameters[1].type,
            result,
            substitutions,
            node.span,
            "relation target",
        )
        self.expression_types[id(node)] = _substitute(relation.type, substitutions)

    def _check_reasoning_rebinding(
        self, node, alias, environment, occurrences, result
    ) -> None:
        if alias in environment or alias in occurrences:
            carried = (
                self.repeat_rebindable[-1].get(alias)
                if self.repeat_rebindable
                else None
            )
            if carried is None:
                self.fail(
                    f"duplicate reasoning occurrence `{alias}`",
                    node.span,
                    "type-reasoning-duplicate-occurrence",
                )
            self._expect(
                carried,
                result,
                node.span,
                f"reasoning repeat loop-carried output `{alias}`",
            )
