# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Elaboration-facing native proof goals."""

from __future__ import annotations

from dataclasses import dataclass

from prism.language.kernel import Context, Term, pretty


@dataclass(frozen=True, slots=True)
class ProofGoal:
    proposition: Term
    context: Context
    origin: str

    def render(self) -> str:
        return pretty(
            self.proposition, (item.name for item in self.context.declarations)
        )


class ProofElaborationError(ValueError):
    pass
