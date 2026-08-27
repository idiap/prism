# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Untrusted elaboration goals and proof-generation interchange."""

from .ast import ProofPremise, Theorem
from .ir import (
    ProofSyntax,
    RawProofTerm,
    TacticInput,
    TacticOutput,
    VerifiedConstruction,
)
from .obligations import ProofElaborationError, ProofGoal

__all__ = [
    "ProofElaborationError",
    "ProofGoal",
    "ProofPremise",
    "ProofSyntax",
    "RawProofTerm",
    "TacticInput",
    "TacticOutput",
    "Theorem",
    "VerifiedConstruction",
]
