# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workflow and abstract-reasoning checking."""

from __future__ import annotations

from prism.language.core import (
    BindingScope,
    CoreType,
)
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
from ..diagnostics import SourceSpan
from ..syntax.ast import (
    AgentDecl,
    Exact,
    Expression,
    FunctionDecl,
    TheoremDecl,
    ToolDecl,
    WorkflowDecl,
)
from .base import _CheckerPhase
from .composition import _CompositionCheckingMixin
from .helpers import (
    _agent_call_effects,
    _expression_name,
)
from .reasoning import _ReasoningCheckingMixin


class _WorkflowCheckingMixin(
    _ReasoningCheckingMixin, _CompositionCheckingMixin, _CheckerPhase
):
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
