# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workflow and abstract-reasoning checking."""

from __future__ import annotations

from typing import Any

from prism.language.core import (
    BindingScope,
    CallableContract,
    CoreType,
)
from prism.language.core import Parameter as CoreParameter
from prism.language.kernel import PROP as KERNEL_PROP
from prism.language.kernel import Declaration as KernelDeclaration
from prism.language.kernel import (
    KernelError,
    check_declaration,
)
from prism.language.kernel import Lam as KernelLam
from prism.language.kernel import Pi as KernelPi
from prism.language.kernel import Term as KernelTerm
from prism.language.kernel import check as kernel_check
from prism.language.verification import ProofGoal

from ..core_elaboration import (
    CoreLocal,
    elaborate_proof_expression,
    elaborate_type_text,
)
from ..diagnostics import PrismTypeError, SourceSpan
from ..syntax.ast import (
    AgentDecl,
    CallExpr,
    ChoiceComposition,
    Exact,
    Expression,
    FunctionDecl,
    LiteralExpr,
    NodeOccurrence,
    ParallelComposition,
    ReasoningDecl,
    RepeatComposition,
    SequenceComposition,
    TheoremDecl,
    ToolDecl,
    WorkflowDecl,
)
from .base import _CheckerPhase
from .helpers import (
    _agent_call_effects,
    _composition_aliases,
    _contains_type_name,
    _expression_name,
    _expression_values,
    _substitute,
    _unique_types,
)


class _WorkflowCheckingMixin(_CheckerPhase):
    def _check_callable(self, declaration: FunctionDecl) -> None:
        contract = self.callables[declaration.name]
        if declaration.is_proposition_declaration:
            return
        parameter_names = {item.name for item in contract.parameters}
        local = BindingScope(
            {
                name: binding
                for name, binding in self.scope.snapshot().items()
                if name not in parameter_names
            }
        )
        for parameter in contract.parameters:
            self._bind_local(local, parameter.name, parameter.type, declaration.span)
        required_effects, returned = self._check_statements(
            declaration.body,
            local,
            contract.result,
            declaration.name,
        )
        self._require_effects(
            declaration.effects, required_effects, declaration.name, declaration.span
        )
        self._require_capabilities(
            declaration.parameters,
            tuple(
                effect
                for effect in declaration.effects
                if effect not in _agent_call_effects(declaration.body, self.callables)
            ),
            declaration.name,
            local_names=set(declaration.type_parameters),
        )
        if not returned:
            self.fail(
                f"`{declaration.name}` has no return statement",
                declaration.span,
                "type-missing-return",
            )

    def _check_tool(self, declaration: ToolDecl) -> None:
        tool_type = self.scope.resolve(declaration.name).type
        contract_type = self.aliases.get(
            tool_type.arguments[0].name, tool_type.arguments[0]
        )
        if not contract_type.is_function:
            self.fail(
                f"tool `{declaration.name}` must name a callable contract",
                declaration.span,
                "type-tool-callable-contract",
            )
        wrapped_name = _expression_name(declaration.callable)
        wrapped_contract = self.callables.get(wrapped_name)
        if wrapped_contract is None or wrapped_contract.kind not in {"def", "workflow"}:
            self.fail(
                f"tool `{declaration.name}` may wrap only a def or workflow",
                declaration.span,
                "type-tool-source",
            )
        wrapped_type, _ = self._infer(declaration.callable, self.scope, None)
        if wrapped_type.name == "Workflow" and wrapped_type.arguments:
            # A workflow declaration is represented as a constructor returning
            # Workflow; its source callable contract is what a tool preserves.
            wrapped_type = wrapped_contract.type
        if not wrapped_type.is_function or len(contract_type.parameters) != len(
            wrapped_type.parameters
        ):
            self.fail(
                f"tool `{declaration.name}` does not match {contract_type.render()}",
                declaration.span,
                "type-tool-callable",
            )
        for (_, expected), (_, actual) in zip(
            contract_type.parameters, wrapped_type.parameters, strict=True
        ):
            self._expect(
                expected,
                actual,
                declaration.span,
                f"tool `{declaration.name}` input",
            )
        self._expect(
            contract_type.result or CoreType("Unit"),
            wrapped_type.result or CoreType("Unit"),
            declaration.span,
            f"tool `{declaration.name}` output",
        )
        if contract_type.effects != wrapped_type.effects:
            self.fail(
                f"tool `{declaration.name}` must preserve effects {contract_type.effects}",
                declaration.span,
                "type-tool-effects",
            )

    def _check_agent(self, declaration: AgentDecl) -> None:
        expected_kinds = {"tools": "Tools", "skills": "Skills", "hooks": "Hooks"}
        local = BindingScope(self.scope.snapshot())
        for capability in declaration.capabilities:
            annotation = (
                self._type(capability.annotation) if capability.annotation else None
            )
            expected_name = expected_kinds[capability.name]
            if annotation is None or annotation.name != expected_name:
                self.fail(
                    f"agent `{declaration.name}` capability `{capability.name}` must use `{expected_name}[...]`",
                    capability.span,
                    "type-agent-capability",
                )
            inferred, _ = self._infer(
                capability.value,
                local,
                self.callables[declaration.name].result,
                annotation,
            )
            self._expect(
                annotation,
                inferred,
                capability.span,
                f"agent `{declaration.name}` capability `{capability.name}`",
            )
            self._bind_local(
                local, capability.name, annotation, capability.span, capability.value
            )

    def _check_workflow(self, declaration: WorkflowDecl) -> None:
        if declaration.name == "main":
            self.fail(
                "the application entry is `def main`; `workflow main` is not valid",
                declaration.span,
                "type-workflow-main",
            )
        contract = self.callables[declaration.name]
        environment = {item.name: item.type for item in contract.parameters}
        occurrences: dict[str, CoreType] = {}
        environment, required_effects, failures, terminals = (
            self._check_workflow_composition(
                declaration.composition,
                environment,
                occurrences,
            )
        )
        selected = declaration.result_alias
        if selected is None:
            if len(terminals) != 1:
                self.fail(
                    f"workflow `{declaration.name}` has multiple terminal occurrences; select one with `return alias`",
                    declaration.span,
                    "type-workflow-terminal",
                )
            selected = terminals[0]
        if selected not in occurrences:
            self.fail(
                f"workflow `{declaration.name}` returns unknown occurrence `{selected}`",
                declaration.span,
                "type-workflow-return",
            )
        self._expect(
            contract.result,
            occurrences[selected],
            declaration.span,
            f"workflow `{declaration.name}` terminal output",
        )
        declared_failure = contract.failure or CoreType("Never")
        for failure in failures:
            if not self._failure_includes(declared_failure, failure):
                self.fail(
                    f"workflow `{declaration.name}` must include failure `{failure.render()}` in `fails {declared_failure.render()}`",
                    declaration.span,
                    "type-workflow-failure",
                )
        self._require_effects(
            declaration.effects,
            required_effects,
            declaration.name,
            declaration.span,
        )
        self._require_capabilities(
            declaration.parameters,
            tuple(
                effect
                for effect in declaration.effects
                if effect
                not in _agent_call_effects(declaration.composition, self.callables)
            ),
            declaration.name,
            local_names=set(declaration.type_parameters),
        )
        self.workflow_outputs[declaration.name] = dict(occurrences)

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
        if isinstance(composition, ParallelComposition):
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
        if isinstance(composition, ChoiceComposition):
            routed, router_effects, router_failures, _ = self._check_workflow_node(
                composition.router, environment, occurrences
            )
            router_alias = (
                composition.router.alias
                or _expression_name(composition.router.component).rsplit(".", 1)[-1]
            )
            router_type = self.aliases.get(
                routed[router_alias].name, routed[router_alias]
            )
            variants = self.variants.get(router_type.name)
            if variants is None:
                self.fail(
                    "choice router must produce a closed sum type",
                    composition.router.span,
                    "type-workflow-choice-router",
                )
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
                        self._check_workflow_composition(
                            child, branch, branch_occurrences
                        )
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
            expected_names = set(branch_outputs[0])
            for produced in branch_outputs[1:]:
                if set(produced) != expected_names:
                    self.fail(
                        "choice arms must converge to the same occurrence outputs",
                        composition.span,
                        "type-workflow-choice-convergence",
                    )
                for name in expected_names:
                    self._expect(
                        branch_outputs[0][name],
                        produced[name],
                        composition.span,
                        f"choice output `{name}`",
                    )
            converged = dict(routed)
            converged.update(branch_outputs[0])
            for branch_occurrences in branch_occurrences_list:
                for name, type_ in branch_occurrences.items():
                    if name in occurrences:
                        continue
                    occurrences[name] = type_
            return (
                converged,
                tuple(dict.fromkeys(all_effects)),
                _unique_types(all_failures),
                choice_terminals,
            )
        if isinstance(composition, RepeatComposition):
            policy_type, policy_effects = self._infer(
                composition.policy, self.scope, None
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
        self.fail(
            "unsupported workflow composition",
            composition.span,
            "type-workflow-composition",
        )

    def _check_repeat_until(
        self,
        until: Expression | None,
        environment: dict[str, CoreType],
        span: SourceSpan,
        *,
        owner: str,
    ) -> None:
        if until is None:
            return
        terminal_scope = BindingScope(
            {
                name: binding
                for name, binding in self.scope.snapshot().items()
                if name not in environment
            }
        )
        for name, type_ in environment.items():
            self._bind_local(terminal_scope, name, type_, span)
        terminal_type, terminal_effects = self._infer(
            until,
            terminal_scope,
            None,
            CoreType("Bool"),
        )
        if terminal_effects:
            self.fail(
                f"{owner} repeat terminal expressions must be pure",
                until.span,
                f"type-{owner}-repeat-until",
            )
        self._expect(
            CoreType("Bool"),
            terminal_type,
            until.span,
            "repeat terminal condition",
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
                CoreParameter(name or "", type_)
                for name, type_ in invocation.parameters
            )
            result = invocation.result or CoreType("Unit")
            effects.extend(invocation.effects)
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

    def _failure_includes(self, declared: CoreType, actual: CoreType) -> bool:
        declared = self.aliases.get(declared.name, declared)
        actual = self.aliases.get(actual.name, actual)
        if declared.is_assignable_from(actual):
            return True
        if actual.name in self.variants.get(declared.name, ()):
            return True
        return actual.name in {
            item.strip() for item in declared.name.split("|") if item.strip()
        }

    def _check_reasoning(self, declaration: ReasoningDecl) -> None:
        if declaration.name == "main":
            self.fail(
                "reasoning declarations are templates; the application entry is `def main`",
                declaration.span,
                "type-reasoning-main",
            )
        contract = self.callables[declaration.name]
        forbidden = {
            "Model",
            "Connection",
            "ModelGenerate",
            "ToolCall",
            "ContextDisclose",
            "DataRead",
            "FileRead",
            "ClockRead",
            "MCPCall",
            "NetworkRequest",
            "ProcessRun",
            "PythonCall",
        }
        for parameter in contract.parameters:
            if _contains_type_name(parameter.type, forbidden):
                self.fail(
                    f"reasoning input `{parameter.name}` cannot carry operational type "
                    f"`{parameter.type.render()}`",
                    declaration.span,
                    "type-reasoning-operational-input",
                )
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
        if isinstance(composition, RepeatComposition):
            policy, policy_effects = self._infer(composition.policy, self.scope, None)
            if policy_effects:
                self.fail(
                    "reasoning repeat policy expressions must be pure",
                    composition.span,
                    "type-reasoning-repeat-policy",
                )
            if policy.name != "RefinementPolicy":
                self.fail(
                    "reasoning repeat requires a statically bounded RefinementPolicy",
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
            return current, prior
        if isinstance(composition, ParallelComposition):
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
        if isinstance(composition, ChoiceComposition):
            routed, _ = self._check_reasoning_node(
                composition.router,
                environment,
                occurrences,
                methods,
                has_prior=has_prior,
                local_type_names=local_type_names,
            )
            for arm in composition.arms:
                branch = dict(routed)
                for child in arm.children:
                    branch, _ = self._check_reasoning_composition(
                        child,
                        branch,
                        occurrences,
                        methods,
                        has_prior=True,
                        local_type_names=local_type_names,
                    )
            return routed, True
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
        if len(node.component.arguments) != 1:
            self.fail(
                f"reasoning method `{name}` requires one explicit logical input; "
                "group multiple inputs in a tuple or record",
                node.span,
                "type-reasoning-method-arity",
            )
        if any(
            isinstance(value, LiteralExpr) and isinstance(value.value, str)
            for value in _expression_values(node.component)
        ):
            self.fail(
                "reasoning declarations cannot contain prompts, paths, commands, or backend strings",
                node.span,
                "type-reasoning-operational-literal",
            )
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
        if alias is None or not alias.is_function:
            self.fail(
                f"`{name}` is not a function-type reasoning method alias",
                node.span,
                "type-reasoning-occurrence-contract",
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
        result = method_type.result or CoreType("Unit")
        self.expression_types[id(node.component.callee)] = method_type
        self.expression_types[id(node.component)] = result
        if node.relation is not None:
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
        alias = node.alias
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
        occurrences[alias] = result
        methods[alias] = method_type
        updated = dict(environment)
        updated[alias] = result
        return updated, True

    def _resolve_relation(self, name: str, span: SourceSpan) -> CallableContract:
        contract = self.callables.get(name)
        if contract is None or contract.kind != "relation":
            self.fail(
                f"`{name}` does not resolve to an imported relation declaration",
                span,
                "type-reasoning-relation-contract",
            )
        return contract

    def _check_theorem(self, declaration: TheoremDecl) -> None:
        parameter_names = {item.name for item in declaration.parameters}
        local = BindingScope(
            {
                name: binding
                for name, binding in self.scope.snapshot().items()
                if name not in parameter_names
            }
        )
        premise_names: set[str] = set()
        core_locals: tuple[CoreLocal, ...] = ()
        parameter_terms: list[tuple[str, KernelTerm]] = []
        for parameter in declaration.parameters:
            type_ = self._type(
                parameter.type, {item.name for item in declaration.parameters}
            )
            self._bind_local(local, parameter.name, type_, parameter.span)
            if type_.name == "Proof" and type_.arguments:
                premise_names.add(parameter.name)
                core_type = self._elaborate_kernel_type(
                    parameter.type,
                    core_locals,
                )
            else:
                try:
                    core_type = self._elaborate_kernel_type(
                        parameter.type,
                        core_locals,
                    )
                except (KernelError, ValueError) as exc:
                    self.fail(
                        f"theorem parameter `{parameter.name}` is not a native proof type: {exc}",
                        parameter.span,
                        "type-theorem-kernel-parameter",
                    )
            parameter_terms.append((parameter.name, core_type))
            core_locals = (*core_locals, CoreLocal(parameter.name, core_type))
        for premise in declaration.premises:
            if premise not in premise_names:
                self.fail(
                    f"theorem premise `{premise}` is not a Proof parameter",
                    declaration.span,
                    "type-theorem-premise",
                )
        exacts = [item for item in declaration.body if isinstance(item, Exact)]
        if len(exacts) != 1 or len(declaration.body) != 1:
            self.fail(
                "theorem bodies require one `exact expression`",
                declaration.span,
                "type-theorem-exact",
            )
        try:
            conclusion = elaborate_type_text(
                declaration.conclusion, self.kernel_environment, core_locals
            )
            kernel_check(
                self.kernel_environment,
                self._kernel_context(core_locals),
                conclusion,
                KERNEL_PROP,
            )
            proof = elaborate_proof_expression(
                exacts[0].proof,
                conclusion,
                self.kernel_environment,
                core_locals,
            )
            kernel_check(
                self.kernel_environment,
                self._kernel_context(core_locals),
                proof,
                conclusion,
            )
            theorem_type = conclusion
            theorem_value = proof
            for name, parameter_type in reversed(parameter_terms):
                theorem_type = KernelPi(name, parameter_type, theorem_type)
                theorem_value = KernelLam(name, parameter_type, theorem_value)
            self.kernel_environment = check_declaration(
                self.kernel_environment,
                KernelDeclaration(
                    declaration.name,
                    theorem_type,
                    theorem_value,
                    "theorem",
                    transparent=False,
                ),
            )
            self.kernel_declarations.append(
                self.kernel_environment.get(declaration.name)
            )
            self.expression_terms[id(exacts[0].proof)] = proof
        except (KernelError, ValueError) as exc:
            self.fail(str(exc), declaration.span, "type-theorem-mismatch")
        self.proof_goals.append(
            ProofGoal(
                conclusion,
                self._kernel_context(core_locals),
                declaration.name,
            )
        )
