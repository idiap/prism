# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Object-oriented facade over the one native kernel judgment."""

from __future__ import annotations

from collections.abc import Sequence

from .context import EMPTY_CONTEXT, Context
from .declarations import check_declaration, check_module
from .diagnostics import KernelError
from .environment import CheckedModule, CheckedTerm, Declaration, Environment
from .equality import is_def_eq
from .prelude import prelude_environment
from .terms import Term
from .typing import check, infer


class Kernel:
    """Check raw core terms under one exact environment.

    Tactics and providers can construct :class:`Term` values, but only this
    judgment creates checked handles. A checked handle is audit metadata; its
    logical authority remains reproducible kernel checking.
    """

    def __init__(self, environment: Environment | None = None) -> None:
        self.environment = environment or prelude_environment()

    def infer(self, term: Term, *, context: Context = EMPTY_CONTEXT) -> Term:
        return infer(self.environment, context, term)

    def check(
        self,
        term: Term,
        expected_type: Term,
        *,
        context: Context = EMPTY_CONTEXT,
    ) -> CheckedTerm:
        return check(self.environment, context, term, expected_type)

    def is_def_eq(
        self,
        left: Term,
        right: Term,
        *,
        context: Context = EMPTY_CONTEXT,
        max_steps: int = 20_000,
    ) -> bool:
        return is_def_eq(self.environment, context, left, right, max_steps=max_steps)

    def recheck(self, checked: CheckedTerm) -> CheckedTerm:
        """Recheck a host handle and all of its content-addressed identity."""

        if not isinstance(checked, CheckedTerm):
            raise KernelError(
                "only a checked-term artifact can be rechecked",
                code="kernel-checked-term-artifact",
            )
        if checked.environment_hash != self.environment.hash:
            raise KernelError(
                "checked term belongs to a different environment",
                code="kernel-environment-hash",
            )
        rechecked = check(self.environment, EMPTY_CONTEXT, checked.term, checked.type)
        if rechecked != checked:
            raise KernelError(
                "checked-term identity does not match kernel recomputation",
                code="kernel-checked-term-hash",
            )
        return rechecked

    def admit(self, declaration: Declaration) -> Declaration:
        self.environment = check_declaration(self.environment, declaration)
        return self.environment.get(declaration.name)

    def module(
        self,
        name: str,
        declarations: Sequence[Declaration],
        imports: Sequence[CheckedModule] = (),
    ) -> CheckedModule:
        checked = check_module(name, imports, declarations)
        self.environment = checked.environment
        return checked
