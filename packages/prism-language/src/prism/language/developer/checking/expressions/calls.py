# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Record, declared callable, agent, and function-value calls."""

from __future__ import annotations

from dataclasses import replace

from prism.language.core import (
    BindingError,
    BindingScope,
    CoreType,
)
from prism.language.core import Parameter as CoreParameter

from ...syntax.ast import CallExpr
from ..base import _CheckerPhase
from ..helpers import (
    _expression_name,
    _index_symbols,
    _substitute,
    _substitute_indices,
)


class _CallCheckingMixin(_CheckerPhase):
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
            return self._infer_record_call(
                callee_name, expression, scope, argument_types, expected_type, effects
            )
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
                expected_type,
            )
            if builtin:
                result, builtin_effects = builtin
                effects.extend(builtin_effects)
                return result, tuple(dict.fromkeys(effects))
        if contract:
            return self._infer_contract_call(
                contract,
                callee_name,
                expression,
                scope,
                argument_types,
                effects,
                expected_type,
            )
        builtin = self._infer_builtin_call(
            callee_name,
            argument_types,
            expression,
            scope,
            expected_type,
        )
        if builtin:
            result, builtin_effects = builtin
            effects.extend(builtin_effects)
            return result, tuple(dict.fromkeys(effects))
        return self._infer_function_call(
            callee_name, expression, scope, enclosing_result, argument_types, effects
        )

    def _infer_record_call(
        self, callee_name, expression, scope, argument_types, expected_type, effects
    ):
        try:
            scope.resolve(callee_name)
        except BindingError:
            self.fail(
                f"unknown record constructor `{callee_name}`",
                expression.span,
                "type-unknown-name",
            )
        record = self.records[callee_name]
        referenced = set().union(*(_index_symbols(item.type) for item in record.fields))
        bindings = {
            field.identity: self._value_index(argument.value, scope)
            for argument in expression.arguments
            for field in record.fields
            if field.name == argument.name and field.identity in referenced
        }
        record = replace(
            record,
            fields=tuple(
                replace(field, type=_substitute_indices(field.type, bindings))
                for field in record.fields
            ),
        )
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

    def _infer_contract_call(
        self,
        contract,
        callee_name,
        expression,
        scope,
        argument_types,
        effects,
        expected_type=None,
    ):
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
            return self._infer_agent_call(
                contract, callee_name, expression, argument_types, effects
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
        bindings = self._invocation_index_bindings(contract, expression, scope)
        substitutions = self._check_arguments(
            tuple(
                CoreParameter(
                    item.name, _substitute_indices(item.type, bindings), item.identity
                )
                for item in contract.parameters
            ),
            argument_types,
            expression.span,
            callee_name,
            explicit_substitutions,
        )
        missing = set(contract.type_parameters) - substitutions.keys()
        if missing and expected_type is not None:
            self._unify(
                contract.result,
                expected_type,
                substitutions,
                expression.span,
                "call result",
            )
            missing -= substitutions.keys()
        if missing:
            self.fail(
                f"`{callee_name}` cannot infer type arguments: {', '.join(sorted(missing))}",
                expression.span,
                "type-call-inference",
            )
        result = _substitute(contract.result, substitutions)
        result = _substitute_indices(result, bindings)
        if contract.kind == "workflow":
            failure = _substitute(contract.failure or CoreType("Never"), substitutions)
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
            result = self._resolved_proposition(expression, scope)
        return result, tuple(dict.fromkeys(effects))

    def _invocation_index_bindings(self, contract, expression, scope):
        indexed_types = (contract.result, *(item.type for item in contract.parameters))
        referenced = set().union(*(_index_symbols(item) for item in indexed_types))
        bindings = {}
        for position, argument in enumerate(expression.arguments):
            parameter = (
                next(
                    (
                        item
                        for item in contract.parameters
                        if item.name == argument.name
                    ),
                    None,
                )
                if argument.name
                else (
                    contract.parameters[position]
                    if position < len(contract.parameters)
                    else None
                )
            )
            if parameter is not None and parameter.identity in referenced:
                bindings[parameter.identity] = self._value_index(argument.value, scope)
        return bindings

    def _infer_agent_call(
        self, contract, callee_name, expression, argument_types, effects
    ):
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

    def _infer_function_call(
        self, callee_name, expression, scope, enclosing_result, argument_types, effects
    ):
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
