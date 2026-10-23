# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Call argument matching and field access."""

from __future__ import annotations

from prism.language.core import (
    CoreType,
    RecordContract,
)
from prism.language.core import Parameter as CoreParameter

from ...diagnostics import SourceSpan
from ..base import _CheckerPhase
from ..helpers import (
    _dependent_assurance_binding,
    _substitute,
)


class _ArgumentCheckingMixin(_CheckerPhase):
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
        if owner.name == "Assessment" and field in {
            "disposition",
            "explanation",
            "policy",
            "policy_identity",
            "policy_hash",
        }:
            return CoreType("String")
        record = self.records.get(owner.name)
        if record:
            return self._record_field_type(record, owner, field, span)
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

    def _record_field_type(self, record, owner, field, span):
        substitutions = dict(zip(record.type_parameters, owner.arguments, strict=False))
        for item in record.fields:
            if item.name == field:
                return _substitute(item.type, substitutions)
        self.fail(
            f"record `{owner.name}` has no field `{field}`",
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
