# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Built-in proofs operations."""

from __future__ import annotations

import ast
from dataclasses import replace

from prism.language.core import CoreType
from prism.language.core.indices import ValueIndex
from prism.language.kernel import PROP as KERNEL_PROP
from prism.language.kernel import Const, InductiveRef, KernelError, Local, apps
from prism.language.kernel import Context as KernelContext
from prism.language.kernel import check as kernel_check

from ...core_elaboration import elaborate_expression
from ...syntax.ast import LiteralExpr
from ..base import _CheckerPhase
from ..helpers import (
    _is_proposition,
    _render_expression,
)
from .builtin_context import _BuiltinCall


class _BuiltinProofsMixin(_CheckerPhase):
    def _builtin_elaborate_proof(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        if len(call.expression.type_arguments) != 1:
            self.fail(
                "elaborate_proof requires one caller-supplied proposition",
                call.expression.span,
                "type-elaborate-proof-goal",
            )
        call.expect_argument(0, CoreType("String"), "generated proof syntax")
        proposition = self._type(call.expression.type_arguments[0])
        if not _is_proposition(proposition):
            self.fail(
                "elaborate_proof requires a native proposition",
                call.expression.span,
                "type-proof-proposition",
            )
        self._prepare_proof_target(call, proposition)
        return (
            CoreType(
                "Result",
                (CoreType("CoreTerm", (proposition,)), CoreType("ProofError")),
            ),
            (),
        )

    def _builtin_kernel_check(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        if not call.positional or call.positional[0].name != "CoreTerm":
            self.fail(
                "kernel.check requires an elaborated CoreTerm",
                call.expression.span,
                "type-kernel-term",
            )
        proposition = call.positional[0].arguments[0]
        self._prepare_proof_target(call, proposition)
        return (
            CoreType(
                "Result",
                (CoreType("Proof", (proposition,)), CoreType("ProofError")),
            ),
            (),
        )

    def _builtin_verify(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(2)
        if len(call.positional) < 2 or call.positional[1].name != "Proof":
            self.fail(
                "verify requires an accepted Proof",
                call.expression.span,
                "type-verify-proof",
            )
        proposition = call.positional[1].arguments[0]
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
        application = proposition.proposition
        if (
            application is None
            or application.kind != "apply"
            or value_index not in application.children[1:]
        ):
            self.fail(
                "verify requires a Proof whose proposition applies to the exact "
                f"value `{value_name}`; got `{proposition.render()}`",
                call.expression.span,
                "type-verify-exact-value",
            )
        self._prepare_proof_target(call, proposition)
        return CoreType(
            "Verified", (call.positional[0], call.positional[1].arguments[0])
        ), ()

    def _prepare_proof_target(self, call, proposition):
        bindings = [
            ValueIndex("reference", binding.identity, label=name, type=binding.type)
            for name, binding in call.scope.snapshot().items()
            if binding.type.name in {"Nat", "Bool"} and binding.identity is not None
        ]

        if call.name == "verify":
            value = replace(
                self._value_index(call.expression.arguments[0].value, call.scope),
                type=call.positional[0],
            )
            # The paired value occupies slot zero; runtime binds it from the
            # evaluated argument, independently of the surrounding environment.
            bindings = [value, *(item for item in bindings if item != value)]

        # Collect first, then assign de Bruijn offsets in the complete context.
        try:
            template = self._lower_proof_target(proposition.proposition, call, bindings)
            template = self._proof_template_locals(template, len(bindings))
            context = KernelContext()
            for binding in bindings:
                assert binding.type is not None
                context = context.push(
                    binding.render(), InductiveRef(binding.type.name)
                )
            kernel_check(self.kernel_environment, context, template, KERNEL_PROP)
        except (KernelError, ValueError) as exc:
            self.fail(
                f"proof requires a checked native proposition: {exc}",
                call.expression.span,
                "type-elaborate-proof-kernel-goal",
            )
        self.expression_terms[id(call.expression)] = template
        self.expression_proof_bindings[id(call.expression)] = tuple(bindings)

    def _lower_proof_target(self, index, call, bindings):
        if index.kind == "apply":
            function = index.children[0]
            if function.kind != "reference":
                raise ValueError("proof targets require a resolved native callable")
            name = function.symbol
            arguments = tuple(
                self._lower_proof_target(child, call, bindings)
                for child in index.children[1:]
            )
            self.kernel_environment.get(name)
            return apps(Const(name), *arguments)
        if index.kind == "literal":
            return elaborate_expression(
                LiteralExpr(ast.literal_eval(index.symbol), call.expression.span),
                self.kernel_environment,
            )
        resolved, type_ = self._resolve_index(
            index, call.expression.span, set(), call.scope
        )
        if type_.name not in {"Nat", "Bool"}:
            raise ValueError(
                f"runtime value {index.render()} of type {type_.render()} is not representable in the proof fragment"
            )
        resolved = replace(resolved, type=type_)
        if resolved not in bindings:
            if any(item.render() == resolved.render() for item in bindings):
                resolved = replace(resolved, label=f"__proof_target_{len(bindings)}")
            bindings.append(resolved)
        return Local(bindings.index(resolved))

    def _proof_template_locals(self, term, count):
        from prism.language.kernel import App

        if isinstance(term, Local):
            return Local(count - 1 - term.index)
        if isinstance(term, App):
            return App(
                self._proof_template_locals(term.function, count),
                self._proof_template_locals(term.argument, count),
            )
        return term
