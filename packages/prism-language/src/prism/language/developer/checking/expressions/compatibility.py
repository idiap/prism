# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Type unification, assignability, and annotation checking."""

from __future__ import annotations

from prism.language.core import CoreType
from prism.language.core.indices import ValueIndex
from prism.language.kernel import Context as KernelContext

from ...core_elaboration import CoreLocal
from ...diagnostics import SourceSpan
from ...syntax.ast import TypeExpr
from ...type_syntax import parse_type
from ..base import _CheckerPhase
from ..helpers import (
    _dependent_assurance_binding,
    _dependent_proposition_matches,
    _expand_aliases,
    _is_proposition,
    _substitute,
    _substitute_indices,
)


class _TypeCompatibilityMixin(_CheckerPhase):
    def _unify(self, expected, actual, substitutions, span, context):
        if expected.name == "Any":
            return
        if (
            expected.name not in self.known_types
            and not expected.arguments
            and not expected.is_function
            and expected.proposition is None
        ):
            previous = substitutions.get(expected.name)
            if previous is None or previous.name == "Never":
                substitutions[expected.name] = actual
            else:
                self._expect(previous, actual, span, context)
            return
        substituted = _substitute(expected, substitutions)
        dependent = _dependent_assurance_binding(substituted)
        actual_dependent = _dependent_assurance_binding(actual)
        if dependent is not None and actual_dependent is not None:
            self._unify(dependent[1], actual_dependent[1], substitutions, span, context)
            self._expect(_substitute(expected, substitutions), actual, span, context)
            return
        if substituted.proposition is not None or actual.proposition is not None:
            self._expect(substituted, actual, span, context)
            return
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
        if expected.name == "Any" or actual.name == "Never":
            return
        if actual.name == "Any":
            protected = self._protected_type(expected)
            if protected is not None:
                self.fail(
                    f"{context} cannot promote Any to protected type `{protected}`",
                    span,
                    "type-protected-any-promotion",
                )
            self.fail(
                f"{context} cannot promote unresolved Any to `{expected.render()}`",
                span,
                "type-any-promotion",
            )
        if expected.name == "Prop" and _is_proposition(actual):
            return
        dependent = _dependent_assurance_binding(expected)
        if dependent is not None:
            self._expect_dependent_assurance(expected, actual, span, context, dependent)
            return
        if expected.name in {"Skills", "Tools"} and actual.name == expected.name:
            self._expect_capability_collection(expected, actual, span, context)
            return
        if self._accepts_variant(expected, actual):
            return
        if expected.name == "Result" and actual.name in {"Ok", "Err"}:
            payload = expected.arguments[0 if actual.name == "Ok" else 1]
            self._expect(payload, actual.arguments[0], span, context)
            return
        self._expect_structure(expected, actual, span, context)

    def _expect_dependent_assurance(self, expected, actual, span, context, dependent):
        binder, value_type, proposition = dependent
        if actual.name != expected.name or len(actual.arguments) != 2:
            self.fail(
                f"{context} expects {expected.render()}, got {actual.render()}",
                span,
                "type-mismatch",
            )
        actual_dependent = _dependent_assurance_binding(actual)
        actual_value_type = (
            actual_dependent[1] if actual_dependent is not None else actual.arguments[0]
        )
        actual_proposition = (
            actual_dependent[2] if actual_dependent is not None else actual.arguments[1]
        )
        self._expect(value_type, actual_value_type, span, context)
        expected_identity = expected.arguments[0].binding_identity or binder
        matches = _dependent_proposition_matches(
            proposition, actual_proposition, expected_identity
        )
        if expected.name == "Validator":
            actual_identity = actual.arguments[0].binding_identity
            normalized = _substitute_indices(
                actual_proposition,
                {actual_identity: ValueIndex("reference", expected_identity)},
            )
            matches = normalized.proposition == proposition.proposition
        if not matches:
            self.fail(
                f"{context} expects {expected.render()}, got {actual.render()}",
                span,
                "type-mismatch",
            )
        return

    def _expect_capability_collection(self, expected, actual, span, context):
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

    def _expect_structure(self, expected, actual, span, context):
        if (
            expected.name != actual.name
            or (
                expected.name == "MaterialPolicy" and expected.effects != actual.effects
            )
            or len(expected.arguments) != len(actual.arguments)
            or expected.proposition != actual.proposition
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
        if expected.is_function:
            self._expect_function(expected, actual, span, context)

    def _expect_function(self, expected, actual, span, context):
        if (
            len(expected.parameters) != len(actual.parameters)
            or expected.effects != actual.effects
        ):
            self.fail(
                f"{context} expects complete function type {expected.render()}, got {actual.render()}",
                span,
                "type-function-mismatch",
            )
        bindings = {
            actual_id: ValueIndex("reference", expected_id)
            for expected_id, actual_id in zip(
                expected.parameter_bindings, actual.parameter_bindings, strict=False
            )
        }
        actual = _substitute_indices(actual, bindings)
        for (_, expected_parameter), (_, actual_parameter) in zip(
            expected.parameters, actual.parameters, strict=True
        ):
            self._expect(expected_parameter, actual_parameter, span, context)
        self._expect(
            expected.result or CoreType("Unit"),
            actual.result or CoreType("Unit"),
            span,
            context,
        )

    def _accepts_variant(self, expected, actual) -> bool:
        if actual.name in self.variants.get(expected.name, ()):
            return True
        if (
            expected.name in self.variants
            and actual.name in self.variants
            and set(self.variants[actual.name]).issubset(self.variants[expected.name])
        ):
            return True

        return False

    def _type(
        self, syntax: TypeExpr, local_names: set[str] | None = None, scope=None
    ) -> CoreType:
        try:
            type_ = parse_type(syntax.text, syntax.span)
        except ValueError as exc:
            self.fail(str(exc), syntax.span, "type-syntax")
        self._validate_type(type_, syntax.span, local_names or set())
        type_ = _expand_aliases(type_, self.aliases, self.type_parameters)
        type_ = self._resolve_type_indices(
            type_,
            syntax.span,
            local_names or set(),
            scope or getattr(self, "index_scope", None) or self.scope,
        )
        return type_

    @staticmethod
    def _kernel_context(locals_: tuple[CoreLocal, ...]) -> KernelContext:
        context = KernelContext()
        for local in locals_:
            context = context.push(local.name, local.type)
        return context
