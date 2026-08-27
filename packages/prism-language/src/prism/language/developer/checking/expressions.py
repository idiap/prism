# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Statement, expression, resolution, and call inference."""

from __future__ import annotations

from typing import Any, Mapping

from prism.language.core import (
    BindingError,
    BindingScope,
    CallableContract,
    CoreType,
    RecordContract,
)
from prism.language.core import Parameter as CoreParameter
from prism.language.effects import SUPPORTED_EFFECTS
from prism.language.evidence import (
    MaterialInferenceError,
    MaterialPolicyContract,
    check_material_inference,
)
from prism.language.kernel import PROP as KERNEL_PROP
from prism.language.kernel import Context as KernelContext
from prism.language.kernel import KernelError
from prism.language.kernel import check as kernel_check

from ..core_elaboration import CoreLocal
from ..diagnostics import SourceSpan
from ..syntax.ast import (
    BinaryExpr,
    Binding,
    CallExpr,
    ConditionalExpr,
    ExecuteExpr,
    Expression,
    ExpressionStatement,
    FieldExpr,
    IndexExpr,
    ListExpr,
    LiteralExpr,
    MapExpr,
    MaterialInferenceExpr,
    NameExpr,
    NodeOccurrence,
    ReasoningDecl,
    Return,
    SolveExpr,
    TryExpr,
    TupleExpr,
    TypeExpr,
    UnaryExpr,
)
from ..type_syntax import parse_type
from .base import _CheckerPhase
from .helpers import (
    _composition_aliases,
    _composition_nodes,
    _dependent_assurance_binding,
    _dependent_proposition_matches,
    _expand_aliases,
    _expression_name,
    _failure_union,
    _implementation_shape,
    _is_proposition,
    _proposition_arguments,
    _proposition_type,
    _render_expression,
    _substitute,
)


class _ExpressionCheckingMixin(_CheckerPhase):
    @staticmethod
    def _kernel_context(locals_: tuple[CoreLocal, ...]) -> KernelContext:
        context = KernelContext()
        for local in locals_:
            context = context.push(local.name, local.type)
        return context

    def _check_statements(
        self,
        statements: tuple[Any, ...],
        scope: BindingScope,
        expected_return: CoreType,
        owner: str,
    ) -> tuple[tuple[str, ...], bool]:
        effects: list[str] = []
        returned = False
        for statement in statements:
            if returned:
                self.fail(
                    "unreachable statement after return",
                    statement.span,
                    "type-unreachable",
                )
            if isinstance(statement, Binding):
                _, inferred_effects = self._check_binding(
                    statement, scope, expected_return
                )
                effects.extend(inferred_effects)
            elif isinstance(statement, Return):
                actual, inferred_effects = self._infer(
                    statement.value,
                    scope,
                    expected_return,
                    expected_return,
                )
                self._expect(expected_return, actual, statement.span, "return value")
                effects.extend(inferred_effects)
                returned = True
            elif isinstance(statement, ExpressionStatement):
                _, inferred_effects = self._infer(
                    statement.value, scope, expected_return
                )
                effects.extend(inferred_effects)
        return tuple(dict.fromkeys(effects)), returned

    def _check_binding(
        self,
        declaration: Binding,
        scope: BindingScope,
        enclosing_result: CoreType | None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        expected = (
            self._type(declaration.annotation) if declaration.annotation else None
        )
        inferred, effects = self._infer(
            declaration.value,
            scope,
            enclosing_result,
            expected,
        )
        if expected is not None:
            if inferred.name != "Any":
                self._expect(
                    expected,
                    inferred,
                    declaration.span,
                    f"binding `{declaration.name}`",
                )
            final = expected
        else:
            final = inferred
        self._bind_local(
            scope,
            declaration.name,
            final,
            declaration.span,
            declaration.value,
        )
        return final, effects

    def _infer(
        self,
        expression: Expression,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        if isinstance(expression, LiteralExpr):
            if expression.value is None:
                type_ = CoreType("Unit")
            elif isinstance(expression.value, bool):
                type_ = CoreType("Bool")
            elif isinstance(expression.value, int):
                type_ = (
                    CoreType("Nat")
                    if expression.value >= 0
                    and expected_type is not None
                    and expected_type.name == "Nat"
                    else CoreType("Int")
                )
            elif isinstance(expression.value, float):
                type_ = CoreType("Float")
            elif isinstance(expression.value, str):
                type_ = CoreType("String")
            elif isinstance(expression.value, bytes):
                type_ = CoreType("Bytes")
            else:
                type_ = CoreType("Any")
        elif isinstance(expression, NameExpr):
            try:
                type_ = scope.resolve(expression.name).type
            except BindingError:
                self.fail(
                    f"unknown name `{expression.name}`",
                    expression.span,
                    "type-unknown-name",
                )
        elif isinstance(expression, ListExpr):
            items = [
                self._infer(item, scope, enclosing_result) for item in expression.items
            ]
            item_types = [item_type for item_type, _ in items]
            effects.extend(
                effect for _, item_effects in items for effect in item_effects
            )
            if item_types and all(item.name == "Skill" for item in item_types):
                type_ = CoreType(
                    "Skills",
                    tuple(
                        item.arguments[0] if item.arguments else CoreType("Any")
                        for item in item_types
                    ),
                )
            elif item_types and all(item.name == "Tool" for item in item_types):
                type_ = CoreType(
                    "Tools",
                    tuple(
                        item.arguments[0] if item.arguments else CoreType("Any")
                        for item in item_types
                    ),
                )
            elif (
                not item_types
                and expected_type is not None
                and expected_type.name in {"Skills", "Tools"}
            ):
                type_ = expected_type
            else:
                type_ = CoreType(
                    "List", (item_types[0] if item_types else CoreType("Any"),)
                )
                for item in item_types[1:]:
                    self._expect(
                        type_.arguments[0], item, expression.span, "list element"
                    )
        elif isinstance(expression, TupleExpr):
            items = [
                self._infer(item, scope, enclosing_result) for item in expression.items
            ]
            effects.extend(
                effect for _, item_effects in items for effect in item_effects
            )
            type_ = CoreType(
                "Tuple",
                tuple(item_type for item_type, _ in items),
            )
        elif isinstance(expression, MapExpr):
            inferred_pairs = [
                (
                    self._infer(key, scope, enclosing_result),
                    self._infer(value, scope, enclosing_result),
                )
                for key, value in expression.items
            ]
            pairs = [
                (key_result[0], value_result[0])
                for key_result, value_result in inferred_pairs
            ]
            effects.extend(
                effect
                for key_result, value_result in inferred_pairs
                for item_effects in (key_result[1], value_result[1])
                for effect in item_effects
            )
            type_ = CoreType(
                "Map",
                (
                    (pairs[0][0], pairs[0][1])
                    if pairs
                    else (CoreType("Any"), CoreType("Any"))
                ),
            )
        elif isinstance(expression, FieldExpr):
            qualified = _expression_name(expression)
            if qualified in self.callables:
                type_ = self.callables[qualified].type
            else:
                owner, owner_effects = self._infer(
                    expression.value, scope, enclosing_result
                )
                effects.extend(owner_effects)
                type_ = self._field_type(owner, expression.field, expression.span)
        elif isinstance(expression, CallExpr):
            type_, call_effects = self._infer_call(
                expression,
                scope,
                enclosing_result,
                expected_type,
            )
            effects.extend(call_effects)
        elif isinstance(expression, TryExpr):
            value_type, inner_effects = self._infer(
                expression.value, scope, enclosing_result
            )
            effects.extend(inner_effects)
            if value_type.name != "Result" or len(value_type.arguments) != 2:
                self.fail(
                    "`try` requires a Result value", expression.span, "type-try-result"
                )
            if enclosing_result is None or enclosing_result.name != "Result":
                self.fail(
                    "`try` requires an enclosing Result return type",
                    expression.span,
                    "type-try-context",
                )
            self._expect(
                enclosing_result.arguments[1],
                value_type.arguments[1],
                expression.span,
                "propagated error",
            )
            type_ = value_type.arguments[0]
        elif isinstance(expression, SolveExpr):
            type_, resolution_effects = self._infer_resolution(
                expression.reasoning,
                expression.workflow,
                scope,
                enclosing_result,
                execute=False,
                span=expression.span,
            )
            effects.extend(resolution_effects)
        elif isinstance(expression, ExecuteExpr):
            type_, resolution_effects = self._infer_resolution(
                expression.reasoning,
                expression.workflow,
                scope,
                enclosing_result,
                execute=True,
                span=expression.span,
            )
            effects.extend(resolution_effects)
        elif isinstance(expression, MaterialInferenceExpr):
            evidence_type, left_effects = self._infer(
                expression.evidence, scope, enclosing_result
            )
            policy_type, policy_effects = self._infer(
                expression.policy, scope, enclosing_result
            )
            proposition_type, proposition_effects = self._infer(
                expression.proposition, scope, enclosing_result
            )
            effects.extend((*left_effects, *policy_effects, *proposition_effects))
            if evidence_type.name != "Evidence" or not evidence_type.arguments:
                self.fail(
                    "left side of `|~` must be Evidence",
                    expression.span,
                    "type-material-evidence",
                )
            if policy_type.name != "MaterialPolicy" or len(policy_type.arguments) < 3:
                self.fail(
                    "bracketed material rule must have MaterialPolicy type",
                    expression.span,
                    "type-material-policy",
                )
            error_type = policy_type.arguments[2]
            policy_row = tuple(item.name for item in policy_type.arguments[3:])
            unknown_policy_effects = set(policy_row) - SUPPORTED_EFFECTS
            if unknown_policy_effects:
                self.fail(
                    "material policy has unknown effects: "
                    + ", ".join(sorted(unknown_policy_effects)),
                    expression.span,
                    "type-unknown-effect",
                )
            effects.extend(policy_row)
            contract = MaterialPolicyContract(
                _expression_name(expression.policy),
                CoreType("Evidence", (policy_type.arguments[0],)),
                policy_type.arguments[1],
                error_type,
                policy_row,
            )
            try:
                type_ = check_material_inference(
                    evidence_type, proposition_type, contract
                )
            except MaterialInferenceError as exc:
                self.fail(str(exc), expression.span, "type-material-policy")
        elif isinstance(expression, UnaryExpr):
            operand, inner_effects = self._infer(
                expression.operand, scope, enclosing_result
            )
            effects.extend(inner_effects)
            type_ = CoreType("Bool") if expression.operator == "not" else operand
        elif isinstance(expression, ConditionalExpr):
            condition, condition_effects = self._infer(
                expression.condition,
                scope,
                enclosing_result,
                CoreType("Bool"),
            )
            self._expect(
                CoreType("Bool"), condition, expression.condition.span, "condition"
            )
            when_true, true_effects = self._infer(
                expression.when_true,
                scope,
                enclosing_result,
                expected_type,
            )
            when_false, false_effects = self._infer(
                expression.when_false,
                scope,
                enclosing_result,
                expected_type or when_true,
            )
            self._expect(
                when_true,
                when_false,
                expression.span,
                "conditional branches",
            )
            effects.extend((*condition_effects, *true_effects, *false_effects))
            type_ = when_true
        elif isinstance(expression, IndexExpr):
            collection, collection_effects = self._infer(
                expression.value, scope, enclosing_result
            )
            index, index_effects = self._infer(
                expression.index, scope, enclosing_result
            )
            effects.extend((*collection_effects, *index_effects))
            if collection.name != "List" or len(collection.arguments) != 1:
                self.fail(
                    "indexing requires a List value",
                    expression.value.span,
                    "type-list-index-owner",
                )
            if index.name not in {"Int", "Nat"}:
                self.fail(
                    "list index must be Int or Nat",
                    expression.index.span,
                    "type-list-index",
                )
            type_ = collection.arguments[0]
        elif isinstance(expression, BinaryExpr):
            if (
                isinstance(expression.left, LiteralExpr)
                and isinstance(expression.left.value, int)
                and expression.left.value >= 0
            ):
                right, right_effects = self._infer(
                    expression.right, scope, enclosing_result
                )
                left, left_effects = self._infer(
                    expression.left, scope, enclosing_result, right
                )
            else:
                left, left_effects = self._infer(
                    expression.left, scope, enclosing_result
                )
                right, right_effects = self._infer(
                    expression.right, scope, enclosing_result, left
                )
            effects.extend((*left_effects, *right_effects))
            if expression.operator == "==" and (
                enclosing_result is not None and enclosing_result.name == "Prop"
            ):
                self._expect(left, right, expression.span, "equality operands")
                type_ = _proposition_type(expression)
            elif expression.operator in {"and", "or"} and (
                enclosing_result is not None and enclosing_result.name == "Prop"
            ):
                self._expect(
                    CoreType("Prop"), left, expression.span, "left proposition"
                )
                self._expect(
                    CoreType("Prop"), right, expression.span, "right proposition"
                )
                type_ = _proposition_type(expression)
            elif expression.operator in {"==", "!=", "<", "<=", ">", ">=", "and", "or"}:
                type_ = CoreType("Bool")
            else:
                self._expect(left, right, expression.span, "binary operands")
                type_ = left
        else:
            self.fail("unsupported expression", expression.span, "type-expression")
        self.expression_types[id(expression)] = type_
        return type_, tuple(dict.fromkeys(effects))

    def _infer_resolution(
        self,
        reasoning: Expression | None,
        workflow: Expression,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        *,
        execute: bool,
        span: SourceSpan,
    ) -> tuple[CoreType, tuple[str, ...]]:
        reasoning_effects: tuple[str, ...] = ()
        reasoning_success: CoreType | None = None
        if reasoning is not None:
            reasoning_success, reasoning_effects = self._infer_reasoning_invocation(
                reasoning, scope, enclosing_result
            )
        workflow_type, construction_effects = self._infer(
            workflow, scope, enclosing_result
        )
        if workflow_type.name != "Workflow" or len(workflow_type.arguments) < 2:
            self.fail(
                "resolution requires a bound Workflow value after `using`",
                span,
                "type-solve-workflow",
            )
        workflow_success, failure = workflow_type.arguments[:2]
        success = reasoning_success or workflow_success
        if reasoning_success is not None:
            self._expect(
                reasoning_success,
                workflow_success,
                span,
                "reasoning materialization output",
            )

        workflow_effects = tuple(item.name for item in workflow_type.arguments[2:])
        result = (
            success
            if failure.name == "Never"
            else CoreType("Result", (success, failure))
        )
        if execute:
            result = CoreType("Execution", (success, failure))
        return (
            result,
            tuple(
                dict.fromkeys(
                    (*reasoning_effects, *construction_effects, *workflow_effects)
                )
            ),
        )

    def _infer_reasoning_invocation(
        self,
        expression: Expression,
        scope: BindingScope,
        enclosing_result: CoreType | None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        if not isinstance(expression, CallExpr):
            self.fail(
                "the left side of `using` must invoke a reasoning declaration",
                expression.span,
                "type-solve-reasoning",
            )
        reasoning_name = _expression_name(expression.callee)
        contract = self.callables.get(reasoning_name)
        if contract is None or contract.kind != "reasoning":
            self.fail(
                f"`{reasoning_name}` is not a reasoning declaration",
                expression.span,
                "type-solve-reasoning",
            )
        if expression.type_arguments and len(expression.type_arguments) != len(
            contract.type_parameters
        ):
            self.fail(
                f"`{reasoning_name}` expects {len(contract.type_parameters)} type "
                f"arguments, got {len(expression.type_arguments)}",
                expression.span,
                "type-call-type-arguments",
            )
        argument_types: list[tuple[str | None, CoreType]] = []
        effects: list[str] = []
        for argument in expression.arguments:
            type_, argument_effects = self._infer(
                argument.value, scope, enclosing_result
            )
            argument_types.append((argument.name, type_))
            effects.extend(argument_effects)
        substitutions = {
            parameter: self._type(argument)
            for parameter, argument in zip(
                contract.type_parameters,
                expression.type_arguments,
                strict=True,
            )
        }
        substitutions = self._check_arguments(
            contract.parameters,
            argument_types,
            expression.span,
            reasoning_name,
            substitutions,
        )
        result = _substitute(contract.result, substitutions)
        self.expression_types[id(expression)] = result
        return result, tuple(dict.fromkeys(effects))

    def _infer_call(
        self,
        expression: CallExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        callee_name = _expression_name(expression.callee)
        contract = self.callables.get(callee_name)
        accepts_type_arguments = bool(contract and contract.type_parameters)
        if (
            expression.type_arguments
            and not accepts_type_arguments
            and callee_name != "generate"
        ):
            self.fail(
                f"`{callee_name}` does not accept explicit type arguments",
                expression.span,
                "type-call-type-arguments",
            )
        argument_types: list[tuple[str | None, CoreType]] = []
        effects: list[str] = []
        for argument in expression.arguments:
            type_, item_effects = self._infer(argument.value, scope, enclosing_result)
            argument_types.append((argument.name, type_))
            effects.extend(item_effects)
        if callee_name in self.records:
            try:
                scope.resolve(callee_name)
            except BindingError:
                self.fail(
                    f"unknown record constructor `{callee_name}`",
                    expression.span,
                    "type-unknown-name",
                )
            record = self.records[callee_name]
            substitutions = self._check_record_arguments(
                record,
                argument_types,
                expression.span,
                expected_type,
            )
            result_type = CoreType(
                record.name,
                tuple(
                    substitutions.get(parameter, CoreType(parameter))
                    for parameter in record.type_parameters
                ),
            )
            return result_type, tuple(dict.fromkeys(effects))
        if (
            contract
            and expression.type_arguments
            and len(expression.type_arguments) != len(contract.type_parameters)
            and callee_name != "validate"
        ):
            self.fail(
                f"`{callee_name}` expects {len(contract.type_parameters)} type arguments, "
                f"got {len(expression.type_arguments)}",
                expression.span,
                "type-call-type-arguments",
            )
        if contract and contract.kind == "intrinsic":
            builtin = self._infer_builtin_call(
                callee_name,
                argument_types,
                expression,
                scope,
            )
            if builtin:
                result, builtin_effects = builtin
                effects.extend(builtin_effects)
                return result, tuple(dict.fromkeys(effects))
        if contract:
            if contract.kind == "relation":
                self.fail(
                    f"relation `{callee_name}` is a contract and is not callable",
                    expression.span,
                    "type-relation-not-callable",
                )
            if contract.kind == "reasoning":
                declaration = self._reasoning_declaration(
                    callee_name, scope, expression.span
                )
                return self._infer_reasoning_configuration(
                    callee_name,
                    contract,
                    declaration,
                    expression,
                    argument_types,
                )
            if contract.kind == "agent":
                invocation_arguments: list[tuple[str | None, CoreType]] = []
                local_capabilities: dict[str, CoreType] = {}
                for name, type_ in argument_types:
                    if name in {"tools", "skills", "hooks"}:
                        if name in local_capabilities:
                            self.fail(
                                f"duplicate agent invocation capability `{name}`",
                                expression.span,
                                "type-agent-invocation-capability",
                            )
                        local_capabilities[name] = type_
                    else:
                        invocation_arguments.append((name, type_))
                for name, type_ in local_capabilities.items():
                    expected_name = {
                        "tools": "Tools",
                        "skills": "Skills",
                        "hooks": "Hooks",
                    }[name]
                    if type_.name != expected_name:
                        self.fail(
                            f"agent invocation `{name}` must have type `{expected_name}[...]`",
                            expression.span,
                            "type-agent-invocation-capability",
                        )
                substitutions = self._check_arguments(
                    contract.parameters,
                    invocation_arguments,
                    expression.span,
                    callee_name,
                )
                effects.extend(contract.effects)
                return _substitute(contract.result, substitutions), tuple(
                    dict.fromkeys(effects)
                )
            explicit_substitutions = (
                {
                    parameter: self._type(argument)
                    for parameter, argument in zip(
                        contract.type_parameters,
                        expression.type_arguments,
                        strict=True,
                    )
                }
                if expression.type_arguments
                else {}
            )
            substitutions = self._check_arguments(
                contract.parameters,
                argument_types,
                expression.span,
                callee_name,
                explicit_substitutions,
            )
            result = _substitute(contract.result, substitutions)
            if contract.kind == "workflow":
                failure = _substitute(
                    contract.failure or CoreType("Never"), substitutions
                )
                result = CoreType(
                    "Workflow",
                    (
                        result,
                        failure,
                        *(CoreType(effect) for effect in contract.effects),
                    ),
                )
            else:
                effects.extend(contract.effects)
            if contract.kind != "workflow" and result.name == "Prop":
                result = _proposition_type(expression)
            return result, tuple(dict.fromkeys(effects))
        builtin = self._infer_builtin_call(
            callee_name,
            argument_types,
            expression,
            scope,
        )
        if builtin:
            result, builtin_effects = builtin
            effects.extend(builtin_effects)
            return result, tuple(dict.fromkeys(effects))
        callee_type, callee_effects = self._infer(
            expression.callee, scope, enclosing_result
        )
        effects.extend(callee_effects)
        if callee_type.name == "Tool" and len(callee_type.arguments) == 1:
            callee_type = self.aliases.get(
                callee_type.arguments[0].name, callee_type.arguments[0]
            )
        if callee_type.is_function:
            expected = tuple(
                CoreParameter(name or f"arg{index}", type_)
                for index, (name, type_) in enumerate(callee_type.parameters)
            )
            substitutions = self._check_arguments(
                expected, argument_types, expression.span, callee_name
            )
            effects.extend(callee_type.effects)
            return _substitute(
                callee_type.result or CoreType("Unit"), substitutions
            ), tuple(dict.fromkeys(effects))
        self.fail(
            f"`{callee_name}` is not callable", expression.span, "type-not-callable"
        )

    def _reasoning_configuration_names(
        self,
        reasoning_name: str,
        declaration: ReasoningDecl,
    ) -> tuple[str, ...]:
        occurrence_names = _composition_aliases(declaration.composition)
        method_contracts = self.reasoning_methods.get(reasoning_name, {})
        input_names = tuple(
            f"{node.alias}_input"
            for node in _composition_nodes(declaration.composition)
            if node.alias
            and self._reasoning_node_requires_input_adapter(node, method_contracts)
        )
        relation_names = tuple(
            f"{node.alias}_by"
            for node in _composition_nodes(declaration.composition)
            if node.alias and node.relation
        )
        switch_names = tuple(
            dict.fromkeys(
                exit_.target.rsplit(".", 1)[-1]
                for exit_ in declaration.exits
                if exit_.action == "switch" and exit_.target
            )
        )
        return (*occurrence_names, *input_names, *relation_names, *switch_names)

    def _reasoning_node_requires_input_adapter(
        self,
        node: NodeOccurrence,
        method_contracts: Mapping[str, CoreType],
    ) -> bool:
        if not node.alias or not isinstance(node.component, CallExpr):
            return False
        method_type = method_contracts.get(node.alias)
        if method_type is None or len(method_type.parameters) != 1:
            return False
        logical_input = node.component.arguments[0].value
        topology_input = self.expression_types.get(id(logical_input))
        if topology_input is None:
            return False
        semantic_input = method_type.parameters[0][1]
        return _expand_aliases(
            topology_input, self.aliases, self.type_parameters
        ) != _expand_aliases(semantic_input, self.aliases, self.type_parameters)

    def _infer_reasoning_configuration(
        self,
        reasoning_name: str,
        contract: CallableContract,
        declaration: ReasoningDecl,
        expression: CallExpr,
        argument_types: list[tuple[str | None, CoreType]],
    ) -> tuple[CoreType, tuple[str, ...]]:
        """Infer a configured reasoning value from ordinary named arguments.

        Occurrence aliases, related-edge aliases, and switch targets form the
        configuration schema.  Concrete workflow parameters not supplied by
        the abstract topology become parameters of the resulting callable.
        """

        if any(name is None for name, _ in argument_types):
            self.fail(
                f"reasoning configuration `{reasoning_name}` requires named bindings",
                expression.span,
                "type-reasoning-configuration-binding",
            )
        expected_order = self._reasoning_configuration_names(
            reasoning_name, declaration
        )
        if len(set(expected_order)) != len(expected_order):
            duplicates = sorted(
                name for name in set(expected_order) if expected_order.count(name) > 1
            )
            self.fail(
                f"reasoning `{reasoning_name}` has ambiguous configuration slots: "
                + ", ".join(duplicates),
                declaration.span,
                "type-reasoning-configuration-ambiguous",
            )
        expected = set(expected_order)
        supplied = {name for name, _ in argument_types if name is not None}
        if supplied != expected:
            missing = [name for name in expected_order if name not in supplied]
            extra = sorted(supplied - expected)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("extra " + ", ".join(extra))
            self.fail(
                f"reasoning configuration `{reasoning_name}` is not total: "
                + "; ".join(details),
                expression.span,
                "type-reasoning-configuration-total",
            )

        by_name = {name: type_ for name, type_ in argument_types if name is not None}
        occurrence_names = _composition_aliases(declaration.composition)
        method_contracts = self.reasoning_methods.get(reasoning_name, {})
        abstract_inputs = {item.name: item.type for item in contract.parameters}
        external_inputs: dict[str, CoreType] = {}
        occurrence_outputs: dict[str, CoreType] = {}
        failures: list[CoreType] = []
        implementation_effects: list[str] = []

        selected = declaration.result_alias
        if selected is None:
            terminals = _composition_aliases(
                declaration.composition, terminal_only=True
            )
            selected = terminals[0] if len(terminals) == 1 else None

        for occurrence in occurrence_names:
            value_type = by_name[occurrence]
            success, failure, row = _implementation_shape(value_type)
            if success is None:
                self.fail(
                    f"occurrence binding `{occurrence}` is not a callable or workflow",
                    expression.span,
                    "type-reasoning-configuration-callable",
                )

            method_type = method_contracts.get(occurrence)
            if method_type is None or len(method_type.parameters) != 1:
                self.fail(
                    f"occurrence `{occurrence}` has no specialized method contract",
                    expression.span,
                    "type-reasoning-configuration-contract",
                )
            node = next(
                item
                for item in _composition_nodes(declaration.composition)
                if item.alias == occurrence
            )
            if self._reasoning_node_requires_input_adapter(node, method_contracts):
                adapter_name = f"{occurrence}_input"
                adapter_type = by_name[adapter_name]
                if not adapter_type.is_function or not adapter_type.parameters:
                    self.fail(
                        f"input adapter `{adapter_name}` must be a callable whose first "
                        "parameter accepts the topology input",
                        expression.span,
                        "type-reasoning-configuration-input-adapter",
                    )
                if adapter_type.effects:
                    self.fail(
                        f"input adapter `{adapter_name}` must be pure",
                        expression.span,
                        "type-reasoning-configuration-input-adapter",
                    )
                if not isinstance(node.component, CallExpr):
                    self.fail(
                        f"input adapter `{adapter_name}` requires a called occurrence",
                        expression.span,
                        "type-reasoning-configuration-input-adapter",
                    )
                logical_input = node.component.arguments[0].value
                topology_input = self.expression_types[id(logical_input)]
                adapter_substitutions: dict[str, CoreType] = {}
                self._unify(
                    adapter_type.parameters[0][1],
                    topology_input,
                    adapter_substitutions,
                    expression.span,
                    f"input adapter `{adapter_name}` topology input",
                )
                for parameter_name, parameter_type in adapter_type.parameters[1:]:
                    if parameter_name is None:
                        self.fail(
                            f"additional inputs for adapter `{adapter_name}` must be named",
                            expression.span,
                            "type-reasoning-configuration-input-adapter",
                        )
                    inferred_parameter = _substitute(
                        parameter_type, adapter_substitutions
                    )
                    provided = abstract_inputs.get(parameter_name)
                    if provided is not None:
                        self._expect(
                            provided,
                            inferred_parameter,
                            expression.span,
                            f"input adapter parameter `{parameter_name}` of `{adapter_name}`",
                        )
                        continue
                    previous = external_inputs.get(parameter_name)
                    if previous is None:
                        external_inputs[parameter_name] = inferred_parameter
                    else:
                        self._expect(
                            previous,
                            inferred_parameter,
                            expression.span,
                            f"shared input adapter parameter `{parameter_name}`",
                        )
                adapter_result = _substitute(
                    adapter_type.result or CoreType("Unit"), adapter_substitutions
                )
                self._expect(
                    method_type.parameters[0][1],
                    adapter_result,
                    expression.span,
                    f"input adapter `{adapter_name}` result",
                )
            if not value_type.parameters:
                self.fail(
                    f"occurrence binding `{occurrence}` must accept the method's "
                    "logical input as its first parameter",
                    expression.span,
                    "type-reasoning-configuration-input",
                )
            substitutions: dict[str, CoreType] = {}
            self._unify(
                value_type.parameters[0][1],
                method_type.parameters[0][1],
                substitutions,
                expression.span,
                f"occurrence binding `{occurrence}` input",
            )
            for parameter_name, parameter_type in value_type.parameters[1:]:
                if parameter_name is None:
                    self.fail(
                        f"additional materializer inputs for `{occurrence}` must be named",
                        expression.span,
                        "type-reasoning-configuration-input",
                    )
                inferred_parameter = _substitute(parameter_type, substitutions)
                provided = abstract_inputs.get(parameter_name)
                if provided is not None:
                    self._expect(
                        provided,
                        inferred_parameter,
                        expression.span,
                        f"materializer input `{parameter_name}` of `{occurrence}`",
                    )
                    continue
                previous = external_inputs.get(parameter_name)
                if previous is None:
                    external_inputs[parameter_name] = inferred_parameter
                else:
                    self._expect(
                        previous,
                        inferred_parameter,
                        expression.span,
                        f"shared materializer input `{parameter_name}`",
                    )

            success = _substitute(success, substitutions)
            failure = _substitute(failure, substitutions) if failure else None
            expected_success = method_type.result or CoreType("Unit")
            self._expect(
                expected_success,
                success,
                expression.span,
                f"occurrence binding `{occurrence}` result",
            )
            occurrence_outputs[occurrence] = expected_success

            if occurrence == selected:
                self._expect(
                    contract.result,
                    expected_success,
                    expression.span,
                    f"reasoning occurrence `{occurrence}` output",
                )
            for guarded_exit in (
                item for item in declaration.exits if item.occurrence == occurrence
            ):
                selectors = self._disposition_selectors(expected_success)
                if guarded_exit.selector not in selectors:
                    available_selectors = (
                        f"; available dispositions: {', '.join(sorted(selectors))}"
                        if selectors
                        else ""
                    )
                    self.fail(
                        f"configured occurrence `{occurrence}` returns "
                        f"`{expected_success.render()}`, which has no disposition "
                        f"`{guarded_exit.selector}`{available_selectors}",
                        expression.span,
                        "type-reasoning-configuration-disposition",
                    )
            if failure is not None and failure.name != "Never":
                failures.append(failure)
            implementation_effects.extend(row)

        for node in _composition_nodes(declaration.composition):
            if not node.alias or not node.relation:
                continue
            field_name = f"{node.alias}_by"
            relation_type = by_name[field_name]
            if not relation_type.is_function or len(relation_type.parameters) != 2:
                self.fail(
                    f"`{field_name}` must be a pure two-input relation builder",
                    expression.span,
                    "type-reasoning-configuration-relation",
                )
            if relation_type.effects:
                self.fail(
                    f"relation builder `{field_name}` must be pure",
                    expression.span,
                    "type-reasoning-configuration-relation",
                )
            method_type = method_contracts[node.alias]
            source_type = method_type.parameters[0][1]
            target_type = method_type.result or CoreType("Unit")
            relation_contract = self._resolve_relation(node.relation, node.span)
            contract_substitutions: dict[str, CoreType] = {}
            self._unify(
                relation_contract.parameters[0].type,
                source_type,
                contract_substitutions,
                expression.span,
                f"relation builder `{field_name}` source",
            )
            self._unify(
                relation_contract.parameters[1].type,
                target_type,
                contract_substitutions,
                expression.span,
                f"relation builder `{field_name}` target",
            )
            expected_certificate = _substitute(
                relation_contract.result, contract_substitutions
            )
            builder_substitutions: dict[str, CoreType] = {}
            self._unify(
                relation_type.parameters[0][1],
                source_type,
                builder_substitutions,
                expression.span,
                f"relation builder `{field_name}` source",
            )
            self._unify(
                relation_type.parameters[1][1],
                target_type,
                builder_substitutions,
                expression.span,
                f"relation builder `{field_name}` target",
            )
            certificate, relation_failure, relation_effects = _implementation_shape(
                relation_type
            )
            if certificate is None:
                self.fail(
                    f"relation builder `{field_name}` must return a certificate",
                    expression.span,
                    "type-reasoning-configuration-relation",
                )
            if relation_effects:
                self.fail(
                    f"relation builder `{field_name}` must be pure",
                    expression.span,
                    "type-reasoning-configuration-relation",
                )
            self._expect(
                expected_certificate,
                _substitute(certificate, builder_substitutions),
                expression.span,
                f"relation builder `{field_name}` certificate",
            )
            if relation_failure is not None and relation_failure.name != "Never":
                failures.append(_substitute(relation_failure, builder_substitutions))

        switch_names = {
            exit_.target.rsplit(".", 1)[-1]
            for exit_ in declaration.exits
            if exit_.action == "switch" and exit_.target
        }
        for switch_name in switch_names:
            target_type = by_name[switch_name]
            success, failure, row = _implementation_shape(target_type)
            if success is None or not target_type.parameters:
                self.fail(
                    f"switch `{switch_name}` must accept the handoff as its first input",
                    expression.span,
                    "type-reasoning-configuration-switch",
                )
            handoff_types = {
                occurrence_outputs[exit_.occurrence]
                for exit_ in declaration.exits
                if exit_.action == "switch"
                and exit_.target
                and exit_.target.rsplit(".", 1)[-1] == switch_name
            }
            for handoff_type in handoff_types:
                self._expect(
                    target_type.parameters[0][1],
                    handoff_type,
                    expression.span,
                    f"switch `{switch_name}` handoff",
                )
            for parameter_name, parameter_type in target_type.parameters[1:]:
                if parameter_name is None:
                    self.fail(
                        f"additional inputs for switch `{switch_name}` must be named",
                        expression.span,
                        "type-reasoning-configuration-switch",
                    )
                provided = abstract_inputs.get(parameter_name)
                if provided is not None:
                    self._expect(
                        provided,
                        parameter_type,
                        expression.span,
                        f"switch input `{parameter_name}` of `{switch_name}`",
                    )
                    continue
                previous = external_inputs.get(parameter_name)
                if previous is None:
                    external_inputs[parameter_name] = parameter_type
                else:
                    self._expect(
                        previous,
                        parameter_type,
                        expression.span,
                        f"shared switch input `{parameter_name}`",
                    )
            self._expect(
                contract.result,
                success,
                expression.span,
                f"switch `{switch_name}` output",
            )
            if failure is not None and failure.name != "Never":
                failures.append(failure)
            implementation_effects.extend(row)

        if any(exit_.action == "stop" for exit_ in declaration.exits):
            failures.append(CoreType("ReasoningStopped", (CoreType(reasoning_name),)))
        failure = _failure_union(failures)
        effects = tuple(dict.fromkeys(implementation_effects))
        workflow_type = CoreType(
            "Workflow",
            (
                contract.result,
                failure,
                *(CoreType(item) for item in effects),
            ),
        )
        invocation_parameters = (
            *((item.name, item.type) for item in contract.parameters),
            *(
                (name, type_)
                for name, type_ in external_inputs.items()
                if name not in abstract_inputs
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

    def _reasoning_declaration(
        self, name: str, scope: BindingScope, span: SourceSpan
    ) -> ReasoningDecl:
        try:
            value = scope.resolve(name).value
        except BindingError:
            value = self.scope.resolve(name).value
        if isinstance(value, ReasoningDecl):
            return value
        self.fail(
            f"cannot inspect reasoning declaration `{name}`",
            span,
            "type-reasoning-declaration",
        )

    def _infer_builtin_call(self, name, arguments, expression, scope):
        positional = [type_ for arg_name, type_ in arguments if arg_name is None]
        named = {
            arg_name: type_ for arg_name, type_ in arguments if arg_name is not None
        }

        def require_positional(count: int) -> None:
            if len(positional) != count:
                self.fail(
                    f"`{name}` expects {count} positional arguments, got {len(positional)}",
                    expression.span,
                    "type-builtin-arity",
                )

        def expect_argument(index: int, expected: CoreType, label: str) -> None:
            self._expect(expected, positional[index], expression.span, label)

        if name in {"Ok", "Err"}:
            if len(arguments) != 1:
                self.fail(
                    f"`{name}` expects exactly one value",
                    expression.span,
                    "type-builtin-arity",
                )
            value = (
                positional[0]
                if positional
                else next((item for _, item in arguments), CoreType("Any"))
            )
            return CoreType(name, (value,)), ()
        if name == "length":
            require_positional(1)
            if named:
                self.fail(
                    "`length` accepts only one positional argument",
                    expression.span,
                    "type-builtin-argument",
                )
            if positional[0].name != "List":
                self.fail(
                    "length requires a List value",
                    expression.span,
                    "type-list-length",
                )
            return CoreType("Int"), ()
        if name == "Generated":
            self.fail(
                "Generated values can only be produced by a typed generation effect",
                expression.span,
                "type-provenance-construction",
            )
        if name == "Computed":
            self.fail(
                "Computed values can only be produced by `compute`",
                expression.span,
                "type-provenance-construction",
            )
        if name == "Validated":
            self.fail(
                "Validated values can only be produced by `validate`",
                expression.span,
                "type-assurance-construction",
            )
        if name == "embed":
            require_positional(1)
            expect_argument(0, CoreType("String"), "embedded resource path")
            return CoreType("Resource", (CoreType("Any"),)), ()
        if name == "inline_resource":
            require_positional(3)
            expect_argument(0, CoreType("String"), "inline resource logical path")
            expect_argument(1, CoreType("String"), "inline resource base64 content")
            expect_argument(2, CoreType("String"), "inline resource content hash")
            return CoreType("Resource", (CoreType("Bytes"),)), ()
        if name == "data_source":
            require_positional(1)
            expect_argument(0, CoreType("String"), "source identifier")
            return CoreType("Source", (CoreType("Any"),)), ()
        if name == "graph_source":
            require_positional(1)
            expect_argument(0, CoreType("String"), "graph source identifier")
            return CoreType("GraphSource", (CoreType("Any"),)), ()
        if name == "connect":
            require_positional(1)
            expect_argument(0, CoreType("String"), "connection identifier")
            return CoreType("Connection", (CoreType("Any"),)), ()
        if name == "skill_artifact":
            if len(expression.type_arguments) != 1:
                self.fail(
                    "skill_artifact requires one task contract",
                    expression.span,
                    "type-skill-artifact",
                )
            require_positional(6)
            for index, label in enumerate(
                (
                    "skill id",
                    "skill version",
                    "skill name",
                    "skill description",
                    "skill instructions",
                    "skill resources",
                )
            ):
                expect_argument(index, CoreType("String"), label)
            return CoreType("Skill", (self._type(expression.type_arguments[0]),)), ()
        if name == "hooks_artifact":
            if len(expression.type_arguments) != 1:
                self.fail(
                    "hooks_artifact requires Codex or Claude as its provider",
                    expression.span,
                    "type-hooks-artifact",
                )
            provider = self._type(expression.type_arguments[0])
            if provider.name not in {"Codex", "Claude"}:
                self.fail(
                    "hooks_artifact provider must be Codex or Claude",
                    expression.span,
                    "type-hooks-provider",
                )
            require_positional(1)
            expect_argument(0, CoreType("String"), "hook configuration")
            return CoreType("Hooks", (provider,)), ()
        if name == "material_policy":
            require_positional(1)
            expect_argument(0, CoreType("String"), "material policy identifier")
            unknown = set(named) - {"require"}
            if unknown:
                self.fail(
                    "`material_policy` has unknown named arguments: "
                    + ", ".join(sorted(unknown)),
                    expression.span,
                    "type-builtin-argument",
                )
            if "require" in named:
                self._expect(
                    CoreType("List", (CoreType("Bool"),)),
                    named["require"],
                    expression.span,
                    "material policy requirements",
                )
            return CoreType("Any"), ()
        if name == "refinement_policy":
            require_positional(1)
            unknown = set(named)
            if unknown:
                self.fail(
                    "`refinement_policy` has unknown named arguments: "
                    + ", ".join(sorted(unknown)),
                    expression.span,
                    "type-builtin-argument",
                )
            if positional[0].name not in {"Int", "Nat"}:
                self.fail(
                    "refinement_policy requires a positive static iteration bound",
                    expression.span,
                    "type-refinement-policy-bound",
                )
            value_expression = expression.arguments[0].value
            if not (
                isinstance(value_expression, LiteralExpr)
                and isinstance(value_expression.value, int)
                and value_expression.value > 0
            ):
                self.fail(
                    "refinement_policy requires a positive static iteration bound",
                    expression.span,
                    "type-refinement-policy-bound",
                )
            return CoreType("RefinementPolicy"), ()
        if name == "proposition":
            require_positional(1)
            expect_argument(0, CoreType("String"), "proposition text")
            return CoreType("Prop"), ()
        if name == "observe":
            require_positional(1)
            unknown = set(named) - {"source", "method"}
            if unknown:
                self.fail(
                    f"`observe` has unknown named arguments: {', '.join(sorted(unknown))}",
                    expression.span,
                    "type-builtin-argument",
                )
            for argument_name in ("source", "method"):
                if argument_name in named:
                    self._expect(
                        CoreType("String"),
                        named[argument_name],
                        expression.span,
                        f"observation {argument_name}",
                    )
            return (
                CoreType(
                    "Evidence", (positional[0] if positional else CoreType("Any"),)
                ),
                (),
            )
        if name == "map_evidence":
            require_positional(1)
            if positional[0].name != "Evidence":
                self.fail(
                    "map_evidence requires an Evidence input",
                    expression.span,
                    "type-evidence-input",
                )
            if set(named) != {"value", "transformation"}:
                self.fail(
                    "map_evidence requires named `value` and `transformation` arguments",
                    expression.span,
                    "type-builtin-argument",
                )
            self._expect(
                CoreType("String"),
                named["transformation"],
                expression.span,
                "evidence transformation",
            )
            value = next(
                (item for arg_name, item in arguments if arg_name == "value"),
                CoreType("Any"),
            )
            return CoreType("Evidence", (value,)), ()
        if name == "combine_evidence":
            if not positional or any(item.name != "Evidence" for item in positional):
                self.fail(
                    "combine_evidence requires one or more Evidence inputs",
                    expression.span,
                    "type-evidence-input",
                )
            if set(named) != {"value", "transformation"}:
                self.fail(
                    "combine_evidence requires named `value` and `transformation` arguments",
                    expression.span,
                    "type-builtin-argument",
                )
            self._expect(
                CoreType("String"),
                named["transformation"],
                expression.span,
                "evidence transformation",
            )
            value = next(
                (item for arg_name, item in arguments if arg_name == "value"),
                CoreType("Any"),
            )
            return CoreType("Evidence", (value,)), ()
        if name == "generate":
            if len(expression.type_arguments) != 1:
                self.fail(
                    "`generate` requires one explicit output type, for example "
                    "`generate[Assessment](request, model, model_access)`",
                    expression.span,
                    "type-generate-output",
                )
            require_positional(3)
            if named:
                self.fail(
                    f"`generate` has unknown named arguments: {', '.join(sorted(named))}",
                    expression.span,
                    "type-builtin-argument",
                )
            expect_argument(1, CoreType("Model"), "generation model")
            expect_argument(2, CoreType("ModelGenerate"), "generation permission")
            value = self._type(expression.type_arguments[0])
            protected = self._protected_type(value)
            if protected is not None:
                self.fail(
                    f"`generate` payloads cannot contain protected type `{protected}`",
                    expression.span,
                    "type-generate-protected-payload",
                )
            return CoreType(
                "Result", (CoreType("Generated", (value,)), CoreType("ModelFailure"))
            ), ("AI.Generate",)
        if name == "compute":
            require_positional(1)
            if set(named) != {"procedure"}:
                self.fail(
                    "`compute` requires a named `procedure` argument",
                    expression.span,
                    "type-builtin-argument",
                )
            self._expect(
                CoreType("String"),
                named["procedure"],
                expression.span,
                "computation procedure",
            )
            return CoreType("Computed", (positional[0],)), ()
        if name == "validate":
            require_positional(1)
            if len(expression.type_arguments) != 1:
                self.fail(
                    "`validate` requires one explicit specification proposition",
                    expression.span,
                    "type-validation-specification",
                )
            if set(named) != {"validator", "require"}:
                self.fail(
                    "`validate` requires named `validator` and `require` arguments",
                    expression.span,
                    "type-builtin-argument",
                )
            self._expect(
                CoreType("String"),
                named["validator"],
                expression.span,
                "validator identifier",
            )
            self._expect(
                CoreType("List", (CoreType("Bool"),)),
                named["require"],
                expression.span,
                "validation requirements",
            )
            proposition = self._type(expression.type_arguments[0])
            if not _is_proposition(proposition):
                self.fail(
                    "`validate` requires a native proposition",
                    expression.span,
                    "type-validation-proposition",
                )
            value_expression = next(
                (
                    argument.value
                    for argument in expression.arguments
                    if argument.name is None
                ),
                None,
            )
            value_name = (
                _render_expression(value_expression)
                if value_expression is not None
                else "<missing>"
            )
            proposition_arguments = _proposition_arguments(proposition.name)
            if not proposition_arguments or value_name not in proposition_arguments:
                self.fail(
                    "validate requires a specification that applies to the exact "
                    f"value `{value_name}`; got `{proposition.render()}`",
                    expression.span,
                    "type-validation-exact-value",
                )
            validated = CoreType(
                "Validated",
                (
                    CoreType(f"value: {positional[0].render()}"),
                    proposition,
                ),
            )
            return CoreType("Result", (validated, CoreType("ValidationError"))), ()
        if name == "query":
            require_positional(4)
            source = (
                positional[0] if positional else CoreType("Source", (CoreType("Any"),))
            )
            if source.name not in {"Source", "GraphSource"}:
                self.fail(
                    "query requires a Source or GraphSource",
                    expression.span,
                    "type-source-input",
                )
            expect_argument(2, CoreType("DataRead"), "source read permission")
            expect_argument(3, CoreType("ClockRead"), "source clock permission")
            payload = source.arguments[0] if source.arguments else CoreType("Any")
            return CoreType(
                "Result", (CoreType("Evidence", (payload,)), CoreType("SourceError"))
            ), ("Data.Read", "Clock.Read")
        if name == "resource_evidence":
            require_positional(3)
            resource = (
                positional[0]
                if positional
                else CoreType("Resource", (CoreType("Any"),))
            )
            if resource.name != "Resource":
                self.fail(
                    "resource_evidence requires a Resource",
                    expression.span,
                    "type-resource-input",
                )
            expect_argument(1, CoreType("FileRead"), "resource read permission")
            expect_argument(2, CoreType("ClockRead"), "resource clock permission")
            payload = resource.arguments[0] if resource.arguments else CoreType("Any")
            return CoreType(
                "Result", (CoreType("Evidence", (payload,)), CoreType("SourceError"))
            ), ("File.Read", "Clock.Read")
        if name == "python_call":
            require_positional(3)
            if len(expression.type_arguments) != 1:
                self.fail(
                    "python_call requires one result type argument",
                    expression.span,
                    "type-python-call-result",
                )
            expect_argument(0, CoreType("String"), "Python operation")
            expect_argument(2, CoreType("PythonCall"), "Python permission")
            result = self._type(expression.type_arguments[0])
            protected = self._protected_type(result)
            if protected is not None:
                self.fail(
                    "`python_call` cannot produce protected type "
                    f"`{protected}`; use its typed introduction operation",
                    expression.span,
                    "type-python-call-protected",
                )
            return CoreType("Result", (result, CoreType("PythonError"))), (
                "Python.Call",
            )
        if name == "tool_call":
            require_positional(4)
            if len(expression.type_arguments) != 1:
                self.fail(
                    "tool_call requires one result type argument",
                    expression.span,
                    "type-tool-call-result",
                )
            expect_argument(0, CoreType("String"), "tool operation")
            if positional[2].name != "Connection":
                self.fail(
                    "tool_call requires a typed Connection",
                    expression.span,
                    "type-tool-call-connection",
                )
            expect_argument(3, CoreType("ToolCall"), "tool permission")
            result = self._type(expression.type_arguments[0])
            protected = self._protected_type(result)
            if protected is not None:
                self.fail(
                    "`tool_call` cannot produce protected type "
                    f"`{protected}`; use its typed introduction operation",
                    expression.span,
                    "type-tool-call-protected",
                )
            return CoreType("Result", (result, CoreType("ToolError"))), ("Tool.Call",)
        if name == "elaborate_proof":
            require_positional(1)
            if len(expression.type_arguments) != 1:
                self.fail(
                    "elaborate_proof requires one caller-supplied proposition",
                    expression.span,
                    "type-elaborate-proof-goal",
                )
            expect_argument(0, CoreType("String"), "generated proof syntax")
            proposition = self._type(expression.type_arguments[0])
            if not _is_proposition(proposition):
                self.fail(
                    "elaborate_proof requires a native proposition",
                    expression.span,
                    "type-proof-proposition",
                )
            try:
                expected_term = self._elaborate_kernel_type(
                    expression.type_arguments[0]
                )
                kernel_check(
                    self.kernel_environment,
                    KernelContext(),
                    expected_term,
                    KERNEL_PROP,
                )
            except (KernelError, ValueError) as exc:
                self.fail(
                    f"elaborate_proof requires a checked native proposition: {exc}",
                    expression.span,
                    "type-elaborate-proof-kernel-goal",
                )
            self.expression_terms[id(expression)] = expected_term
            return (
                CoreType(
                    "Result",
                    (CoreType("CoreTerm", (proposition,)), CoreType("ProofError")),
                ),
                (),
            )
        if name == "kernel.check":
            require_positional(1)
            if not positional or positional[0].name != "CoreTerm":
                self.fail(
                    "kernel.check requires an elaborated CoreTerm",
                    expression.span,
                    "type-kernel-term",
                )
            proposition = positional[0].arguments[0]
            return (
                CoreType(
                    "Result",
                    (CoreType("Proof", (proposition,)), CoreType("ProofError")),
                ),
                (),
            )
        if name == "verify":
            require_positional(2)
            if len(positional) < 2 or positional[1].name != "Proof":
                self.fail(
                    "verify requires an accepted Proof",
                    expression.span,
                    "type-verify-proof",
                )
            proposition = positional[1].arguments[0]
            value_expression = next(
                (
                    argument.value
                    for argument in expression.arguments
                    if argument.name is None
                ),
                None,
            )
            value_name = (
                _render_expression(value_expression)
                if value_expression is not None
                else "<missing>"
            )
            proposition_arguments = _proposition_arguments(proposition.name)
            if not proposition_arguments or value_name not in proposition_arguments:
                self.fail(
                    "verify requires a Proof whose proposition applies to the exact "
                    f"value `{value_name}`; got `{proposition.render()}`",
                    expression.span,
                    "type-verify-exact-value",
                )
            return CoreType("Verified", (positional[0], positional[1].arguments[0])), ()
        return None

    def _field_type(self, owner: CoreType, field: str, span: SourceSpan) -> CoreType:
        if (
            owner.name in {"Computed", "Evidence", "Generated"}
            and field == "value"
            and owner.arguments
        ):
            return owner.arguments[0]
        if owner.name in {"Validated", "Verified"} and field == "value":
            dependent = _dependent_assurance_binding(owner)
            if dependent is not None:
                return dependent[1]
            if owner.arguments:
                return owner.arguments[0]
        record = self.records.get(owner.name)
        if record:
            substitutions = dict(
                zip(record.type_parameters, owner.arguments, strict=False)
            )
            for item in record.fields:
                if item.name == field:
                    return _substitute(item.type, substitutions)
            self.fail(
                f"record `{owner.name}` has no field `{field}`",
                span,
                "type-unknown-field",
            )
        if owner.name == "Module" and owner.arguments:
            members = self.module_members.get(owner.arguments[0].name, {})
            if field in members:
                return members[field]
            self.fail(
                f"module `{owner.arguments[0].name}` has no export `{field}`",
                span,
                "type-import-export",
            )
        self.fail(
            f"type `{owner.render()}` has no field `{field}`",
            span,
            "type-unknown-field",
        )

    def _disposition_selectors(self, type_: CoreType) -> set[str]:
        resolved = self.aliases.get(type_.name, type_)
        variants = self.variants.get(type_.name) or self.variants.get(resolved.name)
        selectors: set[str] = set(variants or ())
        record = self.records.get(type_.name) or self.records.get(resolved.name)
        if record is None:
            return selectors
        substitutions = dict(zip(record.type_parameters, type_.arguments, strict=False))
        selectors.update(
            field.name
            for field in record.fields
            if _substitute(field.type, substitutions).name == "Bool"
        )
        return selectors

    def _check_arguments(self, expected, supplied, span, owner, substitutions=None):
        if len(expected) != len(supplied):
            self.fail(
                f"`{owner}` expects {len(expected)} arguments, got {len(supplied)}",
                span,
                "type-call-arity",
            )
        by_name = {parameter.name: parameter for parameter in expected}
        matched: list[tuple[CoreParameter, CoreType]] = []
        seen_parameters: set[str] = set()
        positional_index = 0
        seen_named = False
        for index, (name, actual) in enumerate(supplied):
            if name is None:
                if seen_named:
                    self.fail(
                        "positional argument follows a named argument",
                        span,
                        "type-call-argument-order",
                    )
                parameter = expected[positional_index]
                positional_index += 1
            else:
                seen_named = True
                parameter = by_name.get(name)
                if parameter is None:
                    self.fail(
                        f"argument {index + 1} of `{owner}` has unknown name `{name}`",
                        span,
                        "type-call-named-argument",
                    )
            if parameter.name in seen_parameters:
                self.fail(
                    f"argument `{parameter.name}` of `{owner}` is supplied more than once",
                    span,
                    "type-call-named-argument",
                )
            seen_parameters.add(parameter.name)
            matched.append((parameter, actual))
        missing = [item.name for item in expected if item.name not in seen_parameters]
        if missing:
            self.fail(
                f"`{owner}` is missing arguments: {', '.join(missing)}",
                span,
                "type-call-arity",
            )
        substitutions = dict(substitutions or {})
        for parameter, actual in matched:
            self._unify(
                parameter.type,
                actual,
                substitutions,
                span,
                f"argument `{parameter.name}`",
            )
        return substitutions

    def _check_record_arguments(
        self,
        record: RecordContract,
        supplied: list[tuple[str | None, CoreType]],
        span: SourceSpan,
        expected_type: CoreType | None,
    ) -> dict[str, CoreType]:
        expected_names = tuple(item.name for item in record.fields)
        supplied_names = tuple(name for name, _ in supplied)
        if (
            None in supplied_names
            or len(set(supplied_names)) != len(supplied_names)
            or set(supplied_names) != set(expected_names)
        ):
            self.fail(
                f"`{record.name}` requires exact named fields {expected_names}, "
                f"got {supplied_names}",
                span,
                "type-constructor-fields",
            )
        substitutions: dict[str, CoreType] = {}
        if expected_type is not None and expected_type.name == record.name:
            if len(expected_type.arguments) != len(record.type_parameters):
                self.fail(
                    f"`{record.name}` expects {len(record.type_parameters)} type "
                    f"arguments, got {len(expected_type.arguments)}",
                    span,
                    "type-arity",
                )
            substitutions.update(
                zip(
                    record.type_parameters,
                    expected_type.arguments,
                    strict=True,
                )
            )
        supplied_types = {name: type_ for name, type_ in supplied if name is not None}
        for field in record.fields:
            self._unify(
                field.type,
                supplied_types[field.name],
                substitutions,
                span,
                f"field `{field.name}`",
            )
        return substitutions

    def _unify(self, expected, actual, substitutions, span, context):
        if expected.name == "Any":
            return
        if (
            expected.name not in self.known_types
            and not expected.arguments
            and not expected.is_function
        ):
            previous = substitutions.get(expected.name)
            if previous is None:
                substitutions[expected.name] = actual
            else:
                self._expect(previous, actual, span, context)
            return
        substituted = _substitute(expected, substitutions)
        if (
            not substituted.is_function
            and not actual.is_function
            and substituted.name == actual.name
            and len(substituted.arguments) == len(actual.arguments)
        ):
            for expected_arg, actual_arg in zip(
                substituted.arguments, actual.arguments, strict=True
            ):
                self._unify(
                    expected_arg,
                    actual_arg,
                    substitutions,
                    span,
                    context,
                )
            return
        self._expect(substituted, actual, span, context)

    def _expect(
        self, expected: CoreType, actual: CoreType, span: SourceSpan, context: str
    ) -> None:
        expected = self.aliases.get(expected.name, expected)
        actual = self.aliases.get(actual.name, actual)
        if expected.name == "Any":
            return
        if actual.name == "Any":
            protected = self._protected_type(expected)
            if protected is not None:
                self.fail(
                    f"{context} cannot promote Any to protected type `{protected}`",
                    span,
                    "type-protected-any-promotion",
                )
            return
        if expected.name == "Prop" and _is_proposition(actual):
            return
        dependent = _dependent_assurance_binding(expected)
        if dependent is not None:
            binder, value_type, proposition = dependent
            if actual.name != expected.name or len(actual.arguments) != 2:
                self.fail(
                    f"{context} expects {expected.render()}, got {actual.render()}",
                    span,
                    "type-mismatch",
                )
            actual_dependent = _dependent_assurance_binding(actual)
            actual_value_type = (
                actual_dependent[1]
                if actual_dependent is not None
                else actual.arguments[0]
            )
            actual_proposition = (
                actual_dependent[2]
                if actual_dependent is not None
                else actual.arguments[1]
            )
            self._expect(value_type, actual_value_type, span, context)
            if not _dependent_proposition_matches(
                proposition,
                actual_proposition,
                binder,
            ):
                self.fail(
                    f"{context} expects {expected.render()}, got {actual.render()}",
                    span,
                    "type-mismatch",
                )
            return
        if expected.name in {"Skills", "Tools"} and actual.name == expected.name:
            if not expected.arguments:
                self.fail(
                    f"{expected.name} requires at least one allowed contract type",
                    span,
                    "type-capability-collection",
                )
            for actual_contract in actual.arguments:
                if not any(
                    allowed.is_assignable_from(actual_contract)
                    for allowed in expected.arguments
                ):
                    self.fail(
                        f"{context} rejects {expected.name[:-1].lower()} contract {actual_contract.render()}",
                        span,
                        "type-capability-collection-element",
                    )
            return
        if actual.name in self.variants.get(expected.name, ()):
            return
        if (
            expected.name in self.variants
            and actual.name in self.variants
            and set(self.variants[actual.name]).issubset(self.variants[expected.name])
        ):
            return
        if expected.name == "Result" and actual.name in {"Ok", "Err"}:
            if actual.name == "Ok":
                self._expect(expected.arguments[0], actual.arguments[0], span, context)
            else:
                self._expect(expected.arguments[1], actual.arguments[0], span, context)
            return
        if expected.name != actual.name or len(expected.arguments) != len(
            actual.arguments
        ):
            self.fail(
                f"{context} expects {expected.render()}, got {actual.render()}",
                span,
                "type-mismatch",
            )
        for expected_arg, actual_arg in zip(
            expected.arguments, actual.arguments, strict=True
        ):
            self._expect(expected_arg, actual_arg, span, context)
        if expected.is_function and expected != actual:
            self.fail(
                f"{context} expects complete function type {expected.render()}, got {actual.render()}",
                span,
                "type-function-mismatch",
            )

    def _type(self, syntax: TypeExpr, local_names: set[str] | None = None) -> CoreType:
        try:
            type_ = parse_type(syntax.text, syntax.span)
        except ValueError as exc:
            self.fail(str(exc), syntax.span, "type-syntax")
        self._validate_type(type_, syntax.span, local_names or set())
        return _expand_aliases(type_, self.aliases, self.type_parameters)
