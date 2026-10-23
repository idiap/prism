# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Expression dispatch and scalar expression inference."""

from __future__ import annotations

from prism.language.core import (
    BindingError,
    BindingScope,
    CoreType,
)
from prism.language.effects import SUPPORTED_EFFECTS
from prism.language.evidence import (
    MaterialInferenceError,
    MaterialPolicyContract,
    check_material_inference,
)

from ...syntax.ast import (
    BinaryExpr,
    CallExpr,
    ConditionalExpr,
    ExecuteExpr,
    Expression,
    FieldExpr,
    IndexExpr,
    ListExpr,
    LiteralExpr,
    MapExpr,
    MaterialInferenceExpr,
    NameExpr,
    SolveExpr,
    TryExpr,
    TupleExpr,
    UnaryExpr,
)
from ..base import _CheckerPhase
from ..helpers import (
    _expression_name,
    _index_symbols,
)

_EXPRESSION_HANDLERS = (
    (LiteralExpr, "_infer_literal"),
    (NameExpr, "_infer_name"),
    (ListExpr, "_infer_list"),
    (TupleExpr, "_infer_tuple"),
    (MapExpr, "_infer_map"),
    (FieldExpr, "_infer_field"),
    (CallExpr, "_infer_call"),
    (TryExpr, "_infer_try"),
    (SolveExpr, "_infer_solve"),
    (ExecuteExpr, "_infer_execute"),
    (MaterialInferenceExpr, "_infer_material_inference"),
    (UnaryExpr, "_infer_unary"),
    (ConditionalExpr, "_infer_conditional"),
    (IndexExpr, "_infer_index"),
    (BinaryExpr, "_infer_binary"),
)


class _InferenceMixin(_CheckerPhase):
    def _infer(
        self,
        expression: Expression,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        for kind, handler_name in _EXPRESSION_HANDLERS:
            if isinstance(expression, kind):
                previous_scope = getattr(self, "index_scope", None)
                self.index_scope = scope
                try:
                    type_, effects = getattr(self, handler_name)(
                        expression, scope, enclosing_result, expected_type
                    )
                finally:
                    self.index_scope = previous_scope
                self.expression_types[id(expression)] = type_
                return type_, tuple(dict.fromkeys(effects))
        self.fail("unsupported expression", expression.span, "type-expression")

    def _infer_literal(
        self,
        expression: LiteralExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
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

        return type_, ()

    def _infer_name(
        self,
        expression: NameExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        try:
            type_ = scope.resolve(expression.name).type
        except BindingError:
            self.fail(
                f"unknown name `{expression.name}`",
                expression.span,
                "type-unknown-name",
            )

        return type_, ()

    def _infer_field(
        self,
        expression: FieldExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        qualified = _expression_name(expression)
        if qualified in self.callables:
            type_ = self.callables[qualified].type
        else:
            owner, owner_effects = self._infer(
                expression.value, scope, enclosing_result
            )
            effects.extend(owner_effects)
            type_ = self._field_type(owner, expression.field, expression.span)
            if _index_symbols(type_):
                type_ = self._project_field_type(
                    self._value_index(expression.value, scope), owner, type_
                )

        return type_, tuple(effects)

    def _infer_try(
        self,
        expression: TryExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
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

        return type_, tuple(effects)

    def _infer_solve(
        self,
        expression: SolveExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        type_, resolution_effects = self._infer_resolution(
            expression.reasoning,
            expression.workflow,
            scope,
            enclosing_result,
            execute=False,
            span=expression.span,
        )
        effects.extend(resolution_effects)

        return type_, tuple(effects)

    def _infer_execute(
        self,
        expression: ExecuteExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        type_, resolution_effects = self._infer_resolution(
            expression.reasoning,
            expression.workflow,
            scope,
            enclosing_result,
            execute=True,
            span=expression.span,
        )
        effects.extend(resolution_effects)

        return type_, tuple(effects)

    def _infer_material_inference(
        self,
        expression: MaterialInferenceExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
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
        policy_row = policy_type.effects
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
            type_ = check_material_inference(evidence_type, proposition_type, contract)
        except MaterialInferenceError as exc:
            self.fail(str(exc), expression.span, "type-material-policy")

        return type_, tuple(effects)

    def _infer_unary(
        self,
        expression: UnaryExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        operand, inner_effects = self._infer(
            expression.operand, scope, enclosing_result
        )
        effects.extend(inner_effects)
        type_ = CoreType("Bool") if expression.operator == "not" else operand

        return type_, tuple(effects)

    def _infer_conditional(
        self,
        expression: ConditionalExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
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

        return type_, tuple(effects)

    def _infer_binary(
        self,
        expression: BinaryExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
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
            left, left_effects = self._infer(expression.left, scope, enclosing_result)
            right, right_effects = self._infer(
                expression.right, scope, enclosing_result, left
            )
        effects.extend((*left_effects, *right_effects))
        if expression.operator == "==" and (
            enclosing_result is not None and enclosing_result.name == "Prop"
        ):
            self._expect(left, right, expression.span, "equality operands")
            type_ = self._resolved_proposition(expression, scope)
        elif expression.operator in {"and", "or"} and (
            enclosing_result is not None and enclosing_result.name == "Prop"
        ):
            self._expect(CoreType("Prop"), left, expression.span, "left proposition")
            self._expect(CoreType("Prop"), right, expression.span, "right proposition")
            type_ = self._resolved_proposition(expression, scope)
        elif expression.operator in {"==", "!=", "<", "<=", ">", ">=", "and", "or"}:
            type_ = CoreType("Bool")
        else:
            self._expect(left, right, expression.span, "binary operands")
            type_ = left

        return type_, tuple(effects)
