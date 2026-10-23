# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Resolve and typecheck structural proposition indices in lexical scopes."""

from __future__ import annotations

import ast
from dataclasses import replace

from prism.language.core import Binding, BindingError, BindingScope, CoreType
from prism.language.core import Parameter as CoreParameter
from prism.language.core.indices import ValueIndex

from ..syntax.ast import Binding as SourceBinding
from ..syntax.ast import FunctionDecl, NameExpr
from ..type_syntax import index_from_expression, parse_type
from .base import _CheckerPhase
from .helpers import _expand_aliases, _substitute, _substitute_indices


class _PropositionCheckingMixin(_CheckerPhase):
    def _symbol_identity(self, name, span=None):
        owner = self.program.path or "Main"
        return (
            f"{owner}::{name}"
            if span is None
            else f"{owner}:{span.line}:{span.column}::{name}"
        )

    def _parameter_scope(self, parameters, span, type_names):
        names = {item.name for item in parameters}
        scope = BindingScope(
            {
                name: binding
                for name, binding in self.scope.snapshot().items()
                if name not in names
            }
        )
        for parameter in parameters:
            type_ = self._type(parameter.type, type_names, scope=scope)
            scope.bind(
                Binding(
                    parameter.name,
                    type_,
                    identity=self._symbol_identity(parameter.name, span),
                )
            )
        return scope

    def _resolve_type_indices(self, type_, span, type_names, scope, depth=0):
        self._check_assurance_tree(type_, span, type_names)
        if type_.proposition is not None:
            index, kind = self._resolve_index(
                type_.proposition, span, type_names, scope
            )
            if kind.name != "Prop":
                self.fail(
                    f"assurance index must return Prop, got {kind.render()}",
                    span,
                    "type-proposition-kind",
                )
            return replace(type_, proposition=index)
        if type_.is_function:
            local = BindingScope(scope.snapshot())
            parameters = []
            identities = []
            for position, (name, value) in enumerate(type_.parameters):
                value = self._resolve_type_indices(
                    value, span, type_names, local, depth + 1
                )
                parameters.append((name, value))
                identity = (
                    type_.parameter_bindings[position]
                    if type_.parameter_bindings
                    else self._symbol_identity(f"function:{depth}:{position}", span)
                )
                identities.append(identity)
                if name:
                    bindings = local.snapshot()
                    bindings[name] = Binding(name, value, identity=identity)
                    local = BindingScope(bindings)
            result = self._resolve_type_indices(
                type_.result, span, type_names, local, depth + 1
            )
            return replace(
                type_,
                parameters=tuple(parameters),
                result=result,
                parameter_bindings=tuple(identities),
            )
        if (
            type_.name in {"Validated", "Verified", "Validator"}
            and len(type_.arguments) == 2
            and type_.arguments[0].binder is not None
        ):
            binding, proposition = type_.arguments
            value = self._resolve_type_indices(
                binding.arguments[0], span, type_names, scope, depth + 1
            )
            bindings = scope.snapshot()
            identity = binding.binding_identity or self._symbol_identity(
                f"value:{depth}", span
            )
            bindings[binding.binder] = Binding(binding.binder, value, identity=identity)
            proposition = self._resolve_type_indices(
                proposition,
                span,
                type_names | {binding.binder},
                BindingScope(bindings),
                depth + 1,
            )
            return replace(
                type_,
                arguments=(
                    replace(binding, arguments=(value,), binding_identity=identity),
                    proposition,
                ),
            )
        return replace(
            type_,
            arguments=tuple(
                self._resolve_type_indices(item, span, type_names, scope, depth + 1)
                for item in type_.arguments
            ),
        )

    def _index_binding(self, name, span, type_names, scope):
        try:
            return scope.resolve(name)
        except BindingError:
            pass
        if name in type_names or name in self.visible_types:
            return Binding(name, CoreType("Type"), identity=name)
        declaration = next(
            (
                item
                for item in self.program.declarations
                if getattr(item, "name", None) == name
            ),
            None,
        )
        if isinstance(declaration, FunctionDecl):
            parameters = tuple(
                (
                    item.name,
                    _expand_aliases(
                        parse_type(item.type.text), self.aliases, self.type_parameters
                    ),
                )
                for item in declaration.parameters
            )
            return Binding(
                name,
                CoreType(
                    "Function",
                    parameters=parameters,
                    result=parse_type(declaration.result.text),
                    effects=declaration.effects,
                ),
                declaration,
                self._symbol_identity(name),
            )
        if isinstance(declaration, SourceBinding):
            pending = getattr(self, "index_pending", set())
            if name in pending:
                self.fail(
                    f"cyclic value index `{name}`", span, "type-proposition-scope"
                )
            self.index_pending = pending | {name}
            try:
                if isinstance(declaration.value, NameExpr):
                    target = self._index_binding(
                        declaration.value.name, span, type_names, scope
                    )
                    return Binding(name, target.type, declaration, target.identity)
                type_ = (
                    self._type(declaration.annotation, scope=scope)
                    if declaration.annotation
                    else self._infer(declaration.value, scope, None)[0]
                )
            finally:
                self.index_pending = pending
            return Binding(name, type_, declaration, self._symbol_identity(name))
        self.fail(
            f"unknown value `{name}` in proposition", span, "type-proposition-scope"
        )

    def _resolve_reference(self, index, span, type_names, scope):
        # A resolved index retains its originating module and binding identity.
        if index.type is not None:
            return index, index.type
        name = index.label or index.symbol
        binding = self._index_binding(name, span, type_names, scope)
        return replace(
            index,
            symbol=binding.identity or self._symbol_identity(name),
            label=name,
            type=binding.type,
        ), binding.type

    def _resolve_index(self, index, span, type_names, scope):
        if index.type is not None:
            return index, index.type
        if index.kind == "reference":
            return self._resolve_reference(index, span, type_names, scope)
        if index.kind == "literal":
            value = ast.literal_eval(index.symbol)
            kind = {
                bool: "Bool",
                int: "Int",
                str: "String",
                float: "Float",
                bytes: "Bytes",
                type(None): "Unit",
            }[type(value)]
            return index, CoreType(kind)
        if index.kind == "apply":
            return self._resolve_index_call(index, span, type_names, scope)
        if index.kind == "field" and index.render() in scope.snapshot():
            return self._resolve_reference(
                ValueIndex("reference", index.render()), span, type_names, scope
            )
        children = tuple(
            self._resolve_index(child, span, type_names, scope)
            for child in index.children
        )
        resolved = replace(index, children=tuple(child for child, _ in children))
        if index.kind == "field":
            field_type = self._field_type(children[0][1], index.symbol, span)
            return resolved, self._project_field_type(
                children[0][0], children[0][1], field_type
            )
        if index.kind == "index":
            return self._resolve_collection_index(resolved, children, span)
        if index.kind == "binary":
            return self._resolve_binary_index(resolved, children, span)
        return resolved, children[0][1]

    def _resolve_collection_index(self, resolved, children, span):
        self._expect(CoreType("Int"), children[1][1], span, "proposition index")
        collection = children[0][1]
        if collection.name != "List":
            self.fail(
                "proposition indexing requires List", span, "type-proposition-index"
            )
        return resolved, collection.arguments[0]

    def _resolve_index_call(self, index, span, type_names, scope):
        callee, callable_type = self._resolve_index(
            index.children[0], span, type_names, scope
        )
        if not callable_type.is_function or callable_type.effects:
            self.fail(
                f"proposition index requires a pure callable `{callee.render()}`",
                span,
                "type-proposition-callable",
            )
        children = tuple(
            self._resolve_index(child, span, type_names, scope)
            for child in index.children[1:]
        )
        parameters = tuple(
            CoreParameter(name or f"arg{position}", type_)
            for position, (name, type_) in enumerate(callable_type.parameters)
        )
        declaration = self._index_binding(
            callee.label or callee.symbol, span, type_names, scope
        ).value
        generic_parameters = getattr(declaration, "type_parameters", ())
        if index.type_arguments and len(index.type_arguments) != len(
            generic_parameters
        ):
            self.fail(
                f"{callee.render()} expects {len(generic_parameters)} type arguments",
                span,
                "type-proposition-specialization",
            )
        explicit: dict[str, CoreType] = dict(
            zip(generic_parameters, index.type_arguments, strict=False)
        )
        for value in explicit.values():
            self._validate_type(value, span, type_names)
        children = tuple(
            self._contextual_index_literal(
                child,
                type_,
                _substitute(
                    next(
                        (
                            parameter.type
                            for parameter in parameters
                            if parameter.name == name
                        ),
                        type_,
                    )
                    if name
                    else (
                        parameters[position].type
                        if position < len(parameters)
                        else type_
                    ),
                    explicit,
                ),
            )
            for position, (name, (child, type_)) in enumerate(
                zip(index.argument_names, children, strict=True)
            )
        )
        substitutions = self._check_arguments(
            parameters,
            list(
                zip(index.argument_names, (type_ for _, type_ in children), strict=True)
            ),
            span,
            callee.render(),
            explicit,
        )
        supplied = {
            name or parameters[position].name: replace(child, type=type_)
            for position, (name, (child, type_)) in enumerate(
                zip(index.argument_names, children, strict=True)
            )
        }
        result = _substitute(callable_type.result, substitutions)
        return replace(
            index,
            children=(callee, *(supplied[item.name] for item in parameters)),
            argument_names=(None,) * len(parameters),
            type_arguments=tuple(
                substitutions.get(name, CoreType(name)) for name in generic_parameters
            ),
            type=result,
        ), result

    def _resolved_proposition(self, expression, scope):
        index = index_from_expression(expression)
        resolved, _ = self._resolve_index(index, expression.span, set(), scope)
        return CoreType("Proposition", proposition=resolved)

    def _value_index(self, expression, scope):
        return self._resolve_index(
            index_from_expression(expression), expression.span, set(), scope
        )[0]

    def _check_assurance_index_kind(self, type_, span, type_names):
        position = {
            "Proof": 0,
            "CoreTerm": 0,
            "Supported": 0,
            "Assessment": 0,
            "Verified": 1,
            "Validated": 1,
            "Validator": 1,
            "MaterialPolicy": 1,
        }.get(type_.name)
        if position is None:
            return
        arity = 3 if type_.name == "MaterialPolicy" else position + 1
        if len(type_.arguments) != arity:
            self.fail(
                f"{type_.name} expects {arity} type arguments",
                span,
                "type-assurance-arity",
            )
        claim = type_.arguments[position]
        if claim.proposition is None and claim.name not in type_names:
            self.fail(
                f"{type_.name} requires a proposition, got {claim.render()}",
                span,
                "type-proposition-kind",
            )

    def _binding_identity(self, name, value, scope, span=None):
        expression = value.value if isinstance(value, SourceBinding) else value
        if isinstance(expression, NameExpr):
            return scope.resolve(expression.name).identity
        return self._symbol_identity(name, span)

    def _project_field_type(self, index, owner, field_type):
        record = self.records.get(owner.name)
        if record is None:
            return field_type
        bindings = {
            field.identity: ValueIndex("field", field.name, (index,))
            for field in record.fields
            if field.identity
        }
        return _substitute_indices(field_type, bindings)

    def _check_assurance_tree(self, type_, span, type_names, seen=frozenset()):
        self._check_assurance_index_kind(type_, span, type_names)
        for argument in type_.arguments:
            self._check_assurance_tree(argument, span, type_names, seen)
        record = self.records.get(type_.name)
        if record is None or type_.name in seen:
            return
        substitutions = dict(zip(record.type_parameters, type_.arguments, strict=False))
        for field in record.fields:
            self._check_assurance_tree(
                _substitute(field.type, substitutions),
                span,
                type_names,
                seen | {type_.name},
            )

    @staticmethod
    def _contextual_index_literal(index, type_, expected):
        if (
            index.kind == "literal"
            and type_.name == "Int"
            and expected.name == "Nat"
            and ast.literal_eval(index.symbol) >= 0
        ):
            return index, CoreType("Nat")
        return index, type_

    def _resolve_binary_index(self, index, children, span):
        left, right = children
        left = self._contextual_index_literal(left[0], left[1], right[1])
        right = self._contextual_index_literal(right[0], right[1], left[1])
        self._expect(left[1], right[1], span, "proposition operands")
        return index, CoreType("Bool") if index.symbol in {
            "==",
            "!=",
            "<",
            ">",
            "<=",
            ">=",
        } else left[1]
