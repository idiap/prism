# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Arguments and diagnostics shared by built-in calls."""

from __future__ import annotations

from prism.language.core import BindingScope, CoreType

from ...syntax.ast import CallExpr
from ..base import _CheckerPhase


class _BuiltinCall:
    def __init__(
        self,
        checker: _CheckerPhase,
        name: str,
        arguments: list[tuple[str | None, CoreType]],
        expression: CallExpr,
        expected_type: CoreType | None = None,
        scope: BindingScope | None = None,
    ) -> None:
        self.checker = checker
        self.name = name
        self.arguments = arguments
        self.expression = expression
        self.expected_type = expected_type
        self.scope = scope
        self.positional = [type_ for name, type_ in arguments if name is None]
        self.named = {name: type_ for name, type_ in arguments if name is not None}

    def require_positional(self, count: int) -> None:
        if len(self.positional) != count:
            self.checker.fail(
                f"`{self.name}` expects {count} positional arguments, got {len(self.positional)}",
                self.expression.span,
                "type-builtin-arity",
            )

    def expect_argument(self, index: int, expected: CoreType, label: str) -> None:
        self.checker._expect(
            expected, self.positional[index], self.expression.span, label
        )
