# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Statement checking and local bindings."""

from __future__ import annotations

from typing import Any

from prism.language.core import (
    BindingScope,
    CoreType,
)

from ...syntax.ast import (
    Binding,
    ExpressionStatement,
    Return,
)
from ..base import _CheckerPhase


class _StatementCheckingMixin(_CheckerPhase):
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
            self._type(declaration.annotation, scope=scope)
            if declaration.annotation
            else None
        )
        inferred, effects = self._infer(
            declaration.value,
            scope,
            enclosing_result,
            expected,
        )
        if expected is not None:
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
