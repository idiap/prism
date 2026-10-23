# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Registration and definition of aliases, records, and variants."""

from __future__ import annotations

import re
from dataclasses import replace

from prism.language.core import (
    Binding,
    BindingScope,
    CoreType,
    RecordContract,
)
from prism.language.core import Parameter as CoreParameter

from ...syntax.ast import (
    TypeDecl,
    TypeExpr,
)
from ...type_syntax import _find_top_level, _split_top_level, parse_type
from ..base import _CheckerPhase


class _TypeDeclarationMixin(_CheckerPhase):
    def _declare_types(self) -> None:
        declarations = [
            item for item in self.program.declarations if isinstance(item, TypeDecl)
        ]
        for declaration in declarations:
            self._register_type(declaration)
        for declaration in declarations:
            self._define_type(declaration)

    def _register_type(self, declaration: TypeDecl) -> None:
        if declaration.name in self.visible_types:
            self.fail(
                f"duplicate type `{declaration.name}`",
                declaration.span,
                "type-duplicate",
            )
        self._validate_type_parameter_declarations(
            declaration.type_parameters, declaration.span, declaration.name
        )
        self.known_types.add(declaration.name)
        self.visible_types.add(declaration.name)
        self.type_parameters[declaration.name] = declaration.type_parameters
        self._bind(declaration.name, CoreType("Type"), declaration, declaration.span)

    def _define_type(self, declaration: TypeDecl) -> None:
        if declaration.alias:
            alias = self._type(declaration.alias, set(declaration.type_parameters))
            if parse_type(declaration.alias.text).is_function:
                alias = replace(
                    alias,
                    binding_identity=self.scope.resolve(declaration.name).identity,
                )
            if declaration.metadata is not None:
                from ..classification import method_classification

                if not parse_type(declaration.alias.text).is_function:
                    self.fail(
                        "metadata requires a direct function-type method declaration",
                        declaration.span,
                        "type-method-metadata",
                    )
                self.method_classifications[alias.binding_identity] = (
                    method_classification(self, declaration.metadata)
                )
            self.aliases[declaration.name] = alias
        elif declaration.fields:
            self._declare_record(declaration)
        elif declaration.alternatives:
            self.variants[declaration.name] = tuple(
                self._declare_variant_constructor(declaration, alternative)
                for alternative in declaration.alternatives
            )

    def _declare_record(self, declaration: TypeDecl) -> None:
        fields: list[CoreParameter] = []
        seen: set[str] = set()
        field_scope = BindingScope(self.scope.snapshot())
        for field in declaration.fields:
            if field.name in seen:
                self.fail(
                    f"duplicate field `{field.name}` in `{declaration.name}`",
                    field.span,
                    "type-record-duplicate-field",
                )
            seen.add(field.name)
            type_ = self._type(
                field.type, set(declaration.type_parameters), scope=field_scope
            )
            identity = self._symbol_identity(
                f"{declaration.name}.{field.name}", declaration.span
            )
            fields.append(CoreParameter(field.name, type_, identity))
            bindings = field_scope.snapshot()
            bindings[field.name] = Binding(field.name, type_, identity=identity)
            field_scope = BindingScope(bindings)
        self.records[declaration.name] = RecordContract(
            declaration.name,
            tuple(fields),
            declaration.type_parameters,
            self.scope.resolve(declaration.name).identity,
        )

    def _declare_variant_constructor(
        self, declaration: TypeDecl, alternative: str
    ) -> str:
        match = re.fullmatch(r"([A-Za-z_]\w*)(?:\((.*)\))?", alternative)
        if match is None:
            self.fail(
                f"invalid variant constructor `{alternative}`",
                declaration.span,
                "type-variant-constructor",
            )
        constructor = match.group(1)
        if match.group(2) is None and (
            constructor in self.visible_types or constructor in self.scope.snapshot()
        ):
            # A bare existing type is a failure-union member, not a
            # new nullary data constructor.
            return constructor
        fields = self._variant_fields(declaration, match.group(2), constructor)
        if constructor in self.records:
            self.fail(
                f"duplicate constructor `{constructor}`",
                declaration.span,
                "type-duplicate",
            )
        self.records[constructor] = RecordContract(
            constructor,
            tuple(fields),
            declaration.type_parameters,
            self._symbol_identity(constructor),
        )
        self.known_types.add(constructor)
        self.visible_types.add(constructor)
        self._bind(
            constructor,
            CoreType("Type"),
            declaration,
            declaration.span,
        )
        return constructor

    def _variant_fields(
        self, declaration: TypeDecl, text: str | None, constructor: str
    ) -> list[CoreParameter]:
        fields: list[CoreParameter] = []
        scope = BindingScope(self.scope.snapshot())
        if text:
            for item in _split_top_level(text):
                colon = _find_top_level(item, ":")
                if colon < 1:
                    self.fail(
                        f"variant field `{item}` requires `name: Type`",
                        declaration.span,
                        "type-variant-field",
                    )
                name = item[:colon].strip()
                type_ = self._type(
                    TypeExpr(item[colon + 1 :].strip(), declaration.span),
                    set(declaration.type_parameters),
                    scope=scope,
                )
                identity = self._symbol_identity(
                    f"{constructor}.{name}", declaration.span
                )
                fields.append(CoreParameter(name, type_, identity))
                bindings = scope.snapshot()
                bindings[name] = Binding(name, type_, identity=identity)
                scope = BindingScope(bindings)
        return fields
