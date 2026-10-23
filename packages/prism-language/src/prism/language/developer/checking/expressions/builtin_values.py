# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Built-in values operations."""

from __future__ import annotations

from prism.language.core import CoreType

from ...syntax.ast import LiteralExpr
from ..base import _CheckerPhase
from .builtin_context import _BuiltinCall


class _BuiltinValuesMixin(_CheckerPhase):
    def _builtin_result(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        if len(call.arguments) != 1:
            self.fail(
                f"`{call.name}` expects exactly one value",
                call.expression.span,
                "type-builtin-arity",
            )
        value = (
            call.positional[0]
            if call.positional
            else next((item for _, item in call.arguments), CoreType("Any"))
        )
        return CoreType(call.name, (value,)), ()

    def _builtin_length(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        if call.named:
            self.fail(
                "`length` accepts only one positional argument",
                call.expression.span,
                "type-builtin-argument",
            )
        if call.positional[0].name != "List":
            self.fail(
                "length requires a List value",
                call.expression.span,
                "type-list-length",
            )
        return CoreType("Int"), ()

    def _builtin_generated(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        self.fail(
            "Generated values can only be produced by a typed generation effect",
            call.expression.span,
            "type-provenance-construction",
        )

    def _builtin_computed(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        self.fail(
            "Computed values can only be produced by `compute`",
            call.expression.span,
            "type-provenance-construction",
        )

    def _builtin_validated(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        self.fail(
            "Validated values can only be produced by `validate`",
            call.expression.span,
            "type-assurance-construction",
        )

    def _contextual_resource_type(self, call: _BuiltinCall, kind: str) -> CoreType:
        if call.expression.type_arguments:
            return CoreType(kind, (self._type(call.expression.type_arguments[0]),))
        if call.expected_type is not None and call.expected_type.name == kind:
            return call.expected_type
        self.fail(
            f"{call.name} requires an explicit or contextual {kind} payload type",
            call.expression.span,
            "type-resource-inference",
        )

    def _builtin_embed(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        call.expect_argument(0, CoreType("String"), "embedded resource path")
        return self._contextual_resource_type(call, "Resource"), ()

    def _builtin_inline_resource(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(3)
        call.expect_argument(0, CoreType("String"), "inline resource logical path")
        call.expect_argument(1, CoreType("String"), "inline resource base64 content")
        call.expect_argument(2, CoreType("String"), "inline resource content hash")
        return CoreType("Resource", (CoreType("Bytes"),)), ()

    def _builtin_data_source(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        call.expect_argument(0, CoreType("String"), "source identifier")
        return self._contextual_resource_type(call, "Source"), ()

    def _builtin_graph_source(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        call.expect_argument(0, CoreType("String"), "graph source identifier")
        return self._contextual_resource_type(call, "GraphSource"), ()

    def _builtin_connect(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        call.expect_argument(0, CoreType("String"), "connection identifier")
        return self._contextual_resource_type(call, "Connection"), ()

    def _builtin_skill_artifact(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        if len(call.expression.type_arguments) != 1:
            self.fail(
                "skill_artifact requires one task contract",
                call.expression.span,
                "type-skill-artifact",
            )
        call.require_positional(6)
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
            call.expect_argument(index, CoreType("String"), label)
        return CoreType("Skill", (self._type(call.expression.type_arguments[0]),)), ()

    def _builtin_hooks_artifact(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        if len(call.expression.type_arguments) != 1:
            self.fail(
                "hooks_artifact requires Codex or Claude as its provider",
                call.expression.span,
                "type-hooks-artifact",
            )
        provider = self._type(call.expression.type_arguments[0])
        if provider.name not in {"Codex", "Claude"}:
            self.fail(
                "hooks_artifact provider must be Codex or Claude",
                call.expression.span,
                "type-hooks-provider",
            )
        call.require_positional(1)
        call.expect_argument(0, CoreType("String"), "hook configuration")
        return CoreType("Hooks", (provider,)), ()

    def _builtin_refinement_policy(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(1)
        unknown = set(call.named)
        if unknown:
            self.fail(
                "`refinement_policy` has unknown named arguments: "
                + ", ".join(sorted(unknown)),
                call.expression.span,
                "type-builtin-argument",
            )
        if call.positional[0].name not in {"Int", "Nat"}:
            self.fail(
                "refinement_policy requires a positive integer iteration bound",
                call.expression.span,
                "type-refinement-policy-bound",
            )
        value_expression = call.expression.arguments[0].value
        if isinstance(value_expression, LiteralExpr) and (
            type(value_expression.value) is not int or value_expression.value <= 0
        ):
            self.fail(
                "refinement_policy requires a positive integer iteration bound",
                call.expression.span,
                "type-refinement-policy-bound",
            )
        return CoreType("RefinementPolicy"), ()
