# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Local contexts and capture-avoiding de Bruijn operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from .diagnostics import KernelError
from .substitution import shift as shift
from .substitution import substitute as substitute
from .terms import (
    Term,
)


@dataclass(frozen=True, slots=True)
class LocalDeclaration:
    name: str
    type: Term
    value: Term | None = None


@dataclass(frozen=True, slots=True)
class Context:
    """Declarations are stored oldest first; local index zero is the last item."""

    declarations: tuple[LocalDeclaration, ...] = ()

    def push(self, name: str, type: Term, value: Term | None = None) -> "Context":
        return Context((*self.declarations, LocalDeclaration(name, type, value)))

    def lookup(self, index: int) -> LocalDeclaration:
        if index < 0 or index >= len(self.declarations):
            raise KernelError(
                f"escaping local #{index} in context of size {len(self.declarations)}",
                code="kernel-unknown-local",
            )
        declaration = self.declarations[-1 - index]
        # Stored types were valid before later binders were introduced.
        return LocalDeclaration(
            declaration.name,
            cast(Term, shift(declaration.type, index + 1)),
            (
                shift(declaration.value, index + 1)
                if declaration.value is not None
                else None
            ),
        )

    def __len__(self) -> int:
        return len(self.declarations)


EMPTY_CONTEXT = Context()
