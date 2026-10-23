# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Built-in evidence operations."""

from __future__ import annotations

from dataclasses import replace

from prism.language.core import CoreType, Parameter, substitute_type
from prism.language.core.indices import ValueIndex

from ...syntax.ast import FieldExpr, TypeExpr
from ..base import _CheckerPhase
from ..helpers import (
    _index_symbols,
    _is_proposition,
    _render_expression,
    _substitute_indices,
)
from .builtin_context import _BuiltinCall


class _BuiltinEvidenceMixin(_CheckerPhase):
    def _builtin_material_policy(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        call.expect_argument(0, CoreType("String"), "material policy identifier")
        policy = (
            CoreType(
                "MaterialPolicy",
                tuple(self._type(item) for item in call.expression.type_arguments),
            )
            if call.expression.type_arguments
            else call.expected_type
        )
        if (
            policy is None
            or policy.name != "MaterialPolicy"
            or len(policy.arguments) != 3
        ):
            self.fail(
                "material_policy requires a MaterialPolicy input, proposition, and failure contract",
                call.expression.span,
                "type-material-policy-contract",
            )
        application = policy.arguments[1].proposition
        evaluator = call.named.get("evaluator")
        if (
            application is None
            or application.kind != "apply"
            or evaluator is None
            or not evaluator.is_function
        ):
            self.fail(
                "material_policy requires a typed evaluator and an applied claim",
                call.expression.span,
                "type-material-policy-evaluator",
            )
        inputs = (
            CoreType("Evidence", (policy.arguments[0],)),
            *(item.type for item in application.children[1:]),
        )
        if len(evaluator.parameters) < len(inputs):
            self.fail(
                "policy evaluator must accept evidence and every claim argument",
                call.expression.span,
                "type-material-policy-evaluator",
            )
        for expected, (_, actual) in zip(inputs, evaluator.parameters, strict=False):
            self._expect(
                expected, actual, call.expression.span, "policy evaluator input"
            )
        captured = {
            name: type_
            for name, type_ in evaluator.parameters[len(inputs) :]
            if name is not None
        }
        if set(call.named) != {"evaluator", *captured}:
            self.fail(
                "policy evaluator requires exactly its named operational inputs",
                call.expression.span,
                "type-material-policy-inputs",
            )
        for name, expected in captured.items():
            self._expect(
                expected,
                call.named[name],
                call.expression.span,
                "policy operational input",
            )
        expected_result = CoreType(
            "Result", (CoreType("PolicyDecision"), policy.arguments[2])
        )
        result = evaluator.result
        if result != CoreType("PolicyDecision") or policy.arguments[2].name != "Never":
            self._expect(
                expected_result, result, call.expression.span, "policy evaluator result"
            )
        return replace(policy, effects=evaluator.effects), ()

    def _builtin_policy_decision(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        call.expect_argument(0, CoreType("String"), "assessment explanation")
        if call.named:
            self.fail(
                "assessment decisions accept only an explanation",
                call.expression.span,
                "type-builtin-argument",
            )
        return CoreType("PolicyDecision"), ()

    def _builtin_accept_support(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        assessment = call.positional[0]
        if (
            call.named
            or assessment.name != "Assessment"
            or len(assessment.arguments) != 1
        ):
            self.fail(
                "accept_support requires an Assessment",
                call.expression.span,
                "type-support-assessment",
            )
        return CoreType(
            "Result",
            (CoreType("Supported", assessment.arguments), CoreType("SupportError")),
        ), ()

    def _builtin_proposition(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        call.expect_argument(0, CoreType("String"), "proposition text")
        return CoreType("Prop"), ()

    def _builtin_observe(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        unknown = set(call.named) - {"source", "method"}
        if unknown:
            self.fail(
                f"`observe` has unknown named arguments: {', '.join(sorted(unknown))}",
                call.expression.span,
                "type-builtin-argument",
            )
        for argument_name in ("source", "method"):
            if argument_name in call.named:
                self._expect(
                    CoreType("String"),
                    call.named[argument_name],
                    call.expression.span,
                    f"observation {argument_name}",
                )
        return (
            CoreType(
                "Evidence",
                (call.positional[0] if call.positional else CoreType("Any"),),
            ),
            (),
        )

    def _builtin_map_evidence(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        if not call.positional or call.positional[0].name != "Evidence":
            self.fail(
                "map_evidence requires an Evidence input",
                call.expression.span,
                "type-evidence-input",
            )
        inputs = (call.positional[0].arguments[0], *call.positional[1:])
        output = self._pure_transformation(call, "transformation", inputs, unwrap=1)
        return CoreType("Evidence", (output,)), ()

    def _builtin_combine_evidence(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        if not call.positional or any(
            item.name != "Evidence" for item in call.positional
        ):
            self.fail(
                "combine_evidence requires one or more Evidence inputs",
                call.expression.span,
                "type-evidence-input",
            )
        output = self._pure_transformation(
            call,
            "transformation",
            tuple(item.arguments[0] for item in call.positional),
            unwrap=len(call.positional),
        )
        return CoreType("Evidence", (output,)), ()

    def _builtin_compute(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        output = self._pure_transformation(call, "procedure", call.positional)
        return CoreType("Computed", (output,)), ()

    def _pure_transformation(self, call, argument, inputs, *, unwrap=0):
        if set(call.named) != {argument}:
            self.fail(
                f"`{argument}` requires only a named `{argument}` callable",
                call.expression.span,
                "type-builtin-argument",
            )
        function = call.named[argument]
        if not function.is_function or function.effects or function.result is None:
            self.fail(
                "transformation requires a pure infallible callable",
                call.expression.span,
                "type-transformation-purity",
            )
        bindings = self._transformation_bindings(call, function, unwrap)
        substitutions = self._check_arguments(
            tuple(
                Parameter(name, _substitute_indices(type_, bindings))
                for name, type_ in function.parameters
            ),
            tuple((None, item) for item in inputs),
            call.expression.span,
            argument,
        )
        output = _substitute_indices(
            substitute_type(function.result, substitutions), bindings
        )
        if output.name in {"Result", "Err", "Workflow"}:
            self.fail(
                "transformation requires a pure infallible callable",
                call.expression.span,
                "type-transformation-purity",
            )
        return output

    def _transformation_bindings(self, call, function, unwrap):
        referenced = _index_symbols(function)
        expressions = tuple(
            item.value for item in call.expression.arguments if item.name is None
        )
        bindings = {}
        for position, (identity, expression) in enumerate(
            zip(function.parameter_bindings, expressions, strict=False)
        ):
            if identity in referenced:
                if position < unwrap:
                    expression = FieldExpr(expression, "value", expression.span)
                bindings[identity] = self._value_index(expression, call.scope)
        return bindings

    def _builtin_validator(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        if call.named or len(call.expression.type_arguments) != 2:
            self.fail(
                "validator requires a value binder, specification, and pure check",
                call.expression.span,
                "type-validator-contract",
            )
        contract = self._type(
            TypeExpr(
                "Validator["
                + ", ".join(item.text for item in call.expression.type_arguments)
                + "]",
                call.expression.span,
            ),
            scope=call.scope,
        )
        binding, specification = contract.arguments
        application = specification.proposition
        if (
            application is None
            or application.kind != "apply"
            or ValueIndex("reference", binding.binding_identity)
            not in application.children[1:]
        ):
            self.fail(
                "validator specification must apply to its exact value binder",
                call.expression.span,
                "type-validator-exact-value",
            )
        check = call.positional[0]
        expected = CoreType(
            "Function",
            parameters=(("value", binding.arguments[0]),),
            result=CoreType("Bool"),
        )
        self._expect(expected, check, call.expression.span, "pure infallible validator")
        if not check.is_function or check.effects:
            self.fail(
                "validator requires a pure infallible callable",
                call.expression.span,
                "type-validator-purity",
            )
        return contract, ()

    def _builtin_validate(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        if len(call.expression.type_arguments) != 1:
            self.fail(
                "`validate` requires one explicit specification proposition",
                call.expression.span,
                "type-validation-specification",
            )
        if set(call.named) != {"validator"}:
            self.fail(
                "validate requires a registered typed validator",
                call.expression.span,
                "type-builtin-argument",
            )
        validator = call.named["validator"]
        if validator.name != "Validator" or len(validator.arguments) != 2:
            self.fail(
                "validate requires a registered typed validator",
                call.expression.span,
                "type-validator-contract",
            )
        binding, specification = validator.arguments
        self._expect(
            binding.arguments[0],
            call.positional[0],
            call.expression.span,
            "validator input",
        )
        proposition = self._type(call.expression.type_arguments[0])
        if not _is_proposition(proposition):
            self.fail(
                "`validate` requires a native proposition",
                call.expression.span,
                "type-validation-proposition",
            )
        value_expression = next(
            (
                argument.value
                for argument in call.expression.arguments
                if argument.name is None
            ),
            None,
        )
        value_name = (
            _render_expression(value_expression)
            if value_expression is not None
            else "<missing>"
        )
        value_index = self._value_index(value_expression, call.scope)
        instantiated = _substitute_indices(
            specification, {binding.binding_identity: value_index}
        )
        if instantiated.proposition != proposition.proposition:
            self.fail(
                "validate requires the registered specification for the exact "
                f"value `{value_name}`; got `{proposition.render()}`",
                call.expression.span,
                "type-validation-exact-value",
            )
        validated = CoreType(
            "Validated",
            (
                CoreType("ValueBinder", (call.positional[0],), binder="value"),
                proposition,
            ),
        )
        return CoreType("Result", (validated, CoreType("ValidationError"))), ()
