# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Formal-verification declarations after native elaboration."""

from __future__ import annotations

from dataclasses import dataclass

from prism.language.core.declarations import Parameter
from prism.language.kernel import Term


@dataclass(frozen=True, slots=True)
class ProofPremise:
    name: str
    proposition: Term


@dataclass(frozen=True, slots=True)
class Theorem:
    name: str
    parameters: tuple[Parameter, ...]
    premises: tuple[ProofPremise, ...]
    conclusion: Term
    proof: Term
